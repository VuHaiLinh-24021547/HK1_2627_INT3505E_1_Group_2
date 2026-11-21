"""Idempotency-Key support for non-idempotent POST endpoints (stored in Redis)."""
from __future__ import annotations

import hashlib
import json
import uuid
from functools import wraps

from flask import Response, current_app, g, make_response, request

from ..extensions import redis_client
from .errors import ApiError

REPLAYED_HEADERS = ("Location", "Content-Type", "Retry-After")
LOCK_TTL_SEC = 60


def _request_hash() -> str:
    raw = request.get_data(cache=True)
    try:
        canonical = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")).encode() if raw.strip() else b""
    except (json.JSONDecodeError, UnicodeDecodeError):
        canonical = raw
    h = hashlib.sha256()
    h.update(request.method.encode() + b" " + request.path.encode() + b"\n" + canonical)
    return h.hexdigest()


def _validate_key(key: str) -> str:
    try:
        parsed = uuid.UUID(key)
    except (ValueError, AttributeError):
        parsed = None
    if parsed is None or parsed.version != 4:
        raise ApiError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key must be a UUID v4.")
    return str(parsed)


def idempotent(required: bool = False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = request.headers.get("Idempotency-Key")
            if not key:
                if required:
                    raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "This endpoint requires an Idempotency-Key header.")
                return fn(*args, **kwargs)

            key = _validate_key(key.strip())
            scope = (getattr(g, "auth", None) or {}).get("sub", "anonymous")
            store_key = f"idem:{scope}:{key}"
            req_hash = _request_hash()

            acquired = redis_client.set(
                store_key, json.dumps({"state": "processing", "hash": req_hash}), nx=True, ex=LOCK_TTL_SEC
            )
            if not acquired:
                raw = redis_client.get(store_key)
                record = json.loads(raw) if raw else None
                if record is None:  # expired between calls - treat as fresh
                    return wrapper(*args, **kwargs)
                if record["hash"] != req_hash:
                    raise ApiError(
                        422,
                        "IDEMPOTENCY_KEY_REUSED",
                        "This Idempotency-Key was already used with a different request payload.",
                    )
                if record["state"] == "processing":
                    raise ApiError(
                        409, "IDEMPOTENCY_KEY_IN_PROGRESS", "A request with this Idempotency-Key is still being processed."
                    )
                resp = Response(record["body"], status=record["status"])
                for name, value in record["headers"].items():
                    resp.headers[name] = value
                resp.headers["Idempotent-Replayed"] = "true"
                return resp

            try:
                resp = make_response(fn(*args, **kwargs))
            except Exception:
                redis_client.delete(store_key)  # errors are not cached; the client may retry
                raise
            if 200 <= resp.status_code < 300:
                record = {
                    "state": "done",
                    "hash": req_hash,
                    "status": resp.status_code,
                    "body": resp.get_data(as_text=True),
                    "headers": {h: resp.headers[h] for h in REPLAYED_HEADERS if h in resp.headers},
                }
                redis_client.set(store_key, json.dumps(record), ex=current_app.config["IDEMPOTENCY_TTL_SEC"])
            else:
                redis_client.delete(store_key)
            return resp

        return wrapper

    return decorator
