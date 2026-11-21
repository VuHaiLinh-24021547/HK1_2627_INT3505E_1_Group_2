"""Minimal OAuth 2.0 authorization server (client credentials) for dev/test environments."""
from __future__ import annotations

import hashlib
import hmac

from flask import current_app, jsonify, request

from ..auth.jwt_auth import decode_token, issue_access_token, revoke_jti
from .errors import ApiError
from . import api_v1
from .schemas import RevocationRequest, TokenRequest


def _ensure_enabled():
    if not current_app.config.get("ENABLE_TOKEN_ENDPOINT"):
        raise ApiError(404, "NOT_FOUND", "The built-in token endpoint is disabled in this environment.")


def _form_or_json() -> dict:
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "MALFORMED_JSON", "Request body is not a valid JSON object.", error="invalid_request")
        return data
    if request.mimetype == "application/x-www-form-urlencoded":
        return request.form.to_dict()
    raise ApiError(
        415,
        "UNSUPPORTED_MEDIA_TYPE",
        "Use application/x-www-form-urlencoded or application/json.",
        error="invalid_request",
    )


def _authenticate_client(data: dict) -> tuple[str, dict]:
    client_id, secret = data.pop("client_id", None), data.pop("client_secret", None)
    if request.authorization and request.authorization.type == "basic":
        client_id = request.authorization.username
        secret = request.authorization.password
    clients = current_app.config.get("OAUTH_CLIENTS") or {}
    client = clients.get(client_id or "")
    valid = False
    if client and secret is not None:
        if "secret_sha256" in client:
            valid = hmac.compare_digest(hashlib.sha256(secret.encode()).hexdigest(), client["secret_sha256"])
        else:
            valid = hmac.compare_digest(str(secret), str(client.get("secret", "")))
    if not valid:
        raise ApiError(
            401,
            "INVALID_CLIENT",
            "Client authentication failed.",
            headers={"WWW-Authenticate": 'Basic realm="lol-match-history"'},
            error="invalid_client",
        )
    return client_id, client


@api_v1.post("/oauth/tokens")
def create_token():
    _ensure_enabled()
    data = _form_or_json()
    req = TokenRequest.model_validate(data)
    if req.grant_type != "client_credentials":
        raise ApiError(400, "UNSUPPORTED_GRANT_TYPE", "Only grant_type=client_credentials is supported.",
                       error="unsupported_grant_type")
    client_id, client = _authenticate_client(req.model_dump())
    allowed = set(client.get("scopes") or [])
    requested = set(req.scope.split()) if req.scope else allowed
    if not requested <= allowed:
        raise ApiError(400, "INVALID_SCOPE", f"Scope(s) not allowed for this client: {' '.join(sorted(requested - allowed))}.",
                       error="invalid_scope")
    token, ttl = issue_access_token(client_id, sorted(requested))
    resp = jsonify({"access_token": token, "token_type": "Bearer", "expires_in": ttl, "scope": " ".join(sorted(requested))})
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    return resp, 200


@api_v1.post("/oauth/revocations")
def revoke_token():
    """RFC 7009 token revocation (only tokens issued to the calling client are revoked)."""
    _ensure_enabled()
    data = _form_or_json()
    req = RevocationRequest.model_validate(data)
    client_id, _ = _authenticate_client(req.model_dump())
    revoked = False
    try:
        claims = decode_token(req.token, verify_exp=False)
    except ApiError:
        claims = None  # RFC 7009: invalid tokens do not cause an error response
    if claims and claims.get("sub") == client_id:
        revoke_jti(claims["jti"], claims["exp"])
        revoked = True
    return jsonify({"revoked": revoked, "jti": claims.get("jti") if revoked else None}), 200
