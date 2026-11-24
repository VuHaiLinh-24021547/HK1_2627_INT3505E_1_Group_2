"""OAuth 2.0 Client Credentials token endpoint (Week 12 mock/seed)."""
from __future__ import annotations

import hmac
from typing import Literal

from flask import current_app, jsonify, request
from pydantic import BaseModel, ConfigDict

from . import api_v1
from .auth import issue_access_token
from .errors import ApiError


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grant_type: str
    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None


@api_v1.post("/oauth/tokens")
def create_token():
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "MALFORMED_JSON", "Request body is not a valid JSON object.", error="invalid_request")
    elif request.mimetype == "application/x-www-form-urlencoded":
        data = request.form.to_dict()
    else:
        raise ApiError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Use application/x-www-form-urlencoded or application/json.",
            error="invalid_request",
        )

    req = TokenRequest.model_validate(data)
    if req.grant_type != "client_credentials":
        raise ApiError(
            400,
            "UNSUPPORTED_GRANT_TYPE",
            "Only grant_type=client_credentials is supported.",
            error="unsupported_grant_type",
        )

    client_id, secret = req.client_id, req.client_secret
    if request.authorization and request.authorization.type == "basic":
        client_id = request.authorization.username
        secret = request.authorization.password

    clients = current_app.config.get("OAUTH_CLIENTS") or {}
    client = clients.get(client_id or "")
    if not client or secret is None or not hmac.compare_digest(str(secret), str(client.get("secret", ""))):
        raise ApiError(
            401,
            "INVALID_CLIENT",
            "Client authentication failed.",
            headers={"WWW-Authenticate": 'Basic realm="lol-match-history"'},
            error="invalid_client",
        )

    allowed = set(client.get("scopes") or [])
    requested = set(req.scope.split()) if req.scope else allowed
    if not requested <= allowed:
        raise ApiError(
            400,
            "INVALID_SCOPE",
            f"Scope(s) not allowed for this client: {' '.join(sorted(requested - allowed))}.",
            error="invalid_scope",
        )

    token, ttl = issue_access_token(client_id, sorted(requested))
    resp = jsonify(
        {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": ttl,
            "scope": " ".join(sorted(requested)),
        }
    )
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    return resp, 200
