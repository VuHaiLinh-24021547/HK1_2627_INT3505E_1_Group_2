"""Opaque, tamper-evident keyset cursors (URL-safe Base64 JSON + HMAC)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json


class InvalidCursor(ValueError):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: bytes, secret: str) -> str:
    return _b64e(hmac.new(secret.encode(), payload, hashlib.sha256).digest()[:12])


def encode_cursor(game_creation: int, match_id: str, secret: str) -> str:
    payload = json.dumps({"gc": int(game_creation), "id": match_id}, separators=(",", ":")).encode()
    return f"{_b64e(payload)}.{_sign(payload, secret)}"


def decode_cursor(cursor: str, secret: str) -> tuple[int, str]:
    try:
        body, sig = cursor.split(".", 1)
        payload = _b64d(body)
    except (ValueError, TypeError) as exc:
        raise InvalidCursor("Malformed cursor") from exc
    if not hmac.compare_digest(sig, _sign(payload, secret)):
        raise InvalidCursor("Cursor signature mismatch")
    try:
        data = json.loads(payload)
        gc, mid = data["gc"], data["id"]
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidCursor("Malformed cursor payload") from exc
    if not isinstance(gc, int) or isinstance(gc, bool) or not isinstance(mid, str):
        raise InvalidCursor("Malformed cursor payload")
    return gc, mid
