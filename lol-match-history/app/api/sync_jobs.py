"""Mock/seed endpoint: POST /api/v1/players/<puuid>/sync-jobs (Idempotency-Key + Cooldown 120s)."""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone

from flask import Response, current_app, g, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import api_v1
from .auth import require_scopes
from .errors import ApiError
from .mock_data import COOLDOWNS, IDEMPOTENCY_STORE, PLAYERS, SYNC_JOBS

SUPPORTED_REGIONS = {"vn2", "sg2", "tw2", "oc1", "kr", "jp1", "euw1", "eun1", "tr1", "ru", "na1", "br1", "la1", "la2"}


class SyncJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region: str | None = Field(default=None, max_length=10)
    count: int = Field(default=20, ge=1, le=100, strict=True)
    queueId: int | None = Field(default=None, ge=0, strict=True)

    @field_validator("region")
    @classmethod
    def _region(cls, v):
        if v is None:
            return v
        norm = v.strip().lower()
        if norm not in SUPPORTED_REGIONS:
            raise ValueError(f"Unsupported region '{v}'.")
        return norm


def _request_hash(raw: bytes) -> str:
    try:
        canonical = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")).encode() if raw.strip() else b""
    except (json.JSONDecodeError, UnicodeDecodeError):
        canonical = raw
    return hashlib.sha256(request.method.encode() + b" " + request.path.encode() + b"\n" + canonical).hexdigest()


@api_v1.post("/players/<puuid>/sync-jobs")
@require_scopes("players:sync")
def create_sync_job(puuid: str):
    raw = request.get_data(cache=True)
    if raw.strip() and not request.is_json:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Request body must be sent as Content-Type: application/json.")

    idem_header = request.headers.get("Idempotency-Key")
    store_key = None
    req_hash = _request_hash(raw)
    if idem_header:
        try:
            parsed = uuid.UUID(idem_header.strip())
            if parsed.version != 4:
                raise ValueError
        except ValueError:
            raise ApiError(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key must be a UUID v4.") from None
        store_key = f"{g.auth['sub']}:{parsed}"
        existing = IDEMPOTENCY_STORE.get(store_key)
        if existing:
            if existing["hash"] != req_hash:
                raise ApiError(
                    422,
                    "IDEMPOTENCY_KEY_REUSED",
                    "This Idempotency-Key was already used with a different request payload.",
                )
            resp = Response(existing["body"], status=existing["status"], mimetype="application/json")
            for k, v in existing["headers"].items():
                resp.headers[k] = v
            resp.headers["Idempotent-Replayed"] = "true"
            return resp

    if not raw.strip():
        data = {}
    else:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "MALFORMED_JSON", "Request body is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ApiError(400, "MALFORMED_JSON", "Request body must be a JSON object.")

    req = SyncJobRequest.model_validate(data)

    player = PLAYERS.get(puuid)
    if player is None:
        raise ApiError(404, "PLAYER_NOT_FOUND", f"Player '{puuid}' does not exist.")
    if req.region and req.region != player["region"]:
        raise ApiError(
            422,
            "REGION_MISMATCH",
            f"Player belongs to region '{player['region']}', not '{req.region}'.",
            errors=[{"field": "region", "code": "mismatch", "message": f"Expected '{player['region']}'."}],
        )

    cooldown_sec = int(current_app.config["SYNC_COOLDOWN_SEC"])
    last_ts = COOLDOWNS.get(puuid)
    if last_ts is not None:
        remaining = int(math.ceil(cooldown_sec - (time.time() - last_ts)))
        if remaining > 0:
            raise ApiError(
                429,
                "SYNC_COOLDOWN_ACTIVE",
                f"Vui lòng đợi thêm {remaining} giây trước khi đồng bộ lại.",
                headers={"Retry-After": str(remaining)},
                retryAfterSeconds=remaining,
            )

    COOLDOWNS[puuid] = time.time()
    job_id = uuid.uuid4().hex
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    job = {
        "jobId": job_id,
        "status": "queued",
        "puuid": puuid,
        "region": player["region"],
        "count": req.count,
        "queueId": req.queueId,
        "createdAt": now_iso,
        "startedAt": None,
        "finishedAt": None,
        "result": None,
        "error": None,
    }
    SYNC_JOBS[job_id] = job
    location = f"/api/v1/sync-jobs/{job_id}"

    resp = jsonify(job)
    resp.status_code = 202
    resp.headers["Location"] = location
    if store_key:
        IDEMPOTENCY_STORE[store_key] = {
            "hash": req_hash,
            "status": 202,
            "body": resp.get_data(as_text=True),
            "headers": {"Location": location},
        }
    return resp
