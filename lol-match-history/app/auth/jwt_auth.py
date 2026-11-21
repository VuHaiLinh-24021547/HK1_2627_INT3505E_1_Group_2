"""JWT issuing (built-in client-credentials server) and verification (resource server)."""
from __future__ import annotations

import time
import uuid
from functools import wraps

import jwt
from flask import current_app, g, request

from ..api.errors import ApiError
from ..extensions import redis_client


def _www_auth(error: str, description: str, scope: str | None = None) -> dict[str, str]:
    value = f'Bearer realm="lol-match-history", error="{error}", error_description="{description}"'
    if scope:
        value += f', scope="{scope}"'
    return {"WWW-Authenticate": value}


def _unauthorized(code: str, detail: str, error: str = "invalid_token") -> ApiError:
    return ApiError(401, code, detail, headers=_www_auth(error, detail))


# ----------------------------------------------------------------- issue
def issue_access_token(subject: str, scopes: list[str]) -> tuple[str, int]:
    cfg = current_app.config
    private_key = cfg.get("JWT_PRIVATE_KEY_PEM")
    if not private_key:
        raise ApiError(503, "TOKEN_SIGNER_UNAVAILABLE", "Token signing key is not configured.")
    ttl = int(cfg["JWT_ACCESS_TTL_SEC"])
    now = int(time.time())
    claims = {
        "iss": cfg["JWT_ISSUER"],
        "aud": cfg["JWT_AUDIENCE"],
        "sub": subject,
        "client_id": subject,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
        "scope": " ".join(sorted(set(scopes))),
    }
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": cfg.get("JWT_KID")})
    return token, ttl


# ----------------------------------------------------------------- verify
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def _verification_key(token: str):
    cfg = current_app.config
    url = cfg.get("JWT_JWKS_URL")
    if url:
        client = _jwks_clients.setdefault(url, jwt.PyJWKClient(url))
        return client.get_signing_key_from_jwt(token).key
    key = cfg.get("JWT_PUBLIC_KEY_PEM")
    if not key:
        raise ApiError(503, "TOKEN_VERIFIER_UNAVAILABLE", "Token verification key is not configured.")
    return key


def decode_token(token: str, verify_exp: bool = True) -> dict:
    cfg = current_app.config
    allowed = cfg["JWT_ALGORITHMS"]
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise _unauthorized("INVALID_TOKEN", "The access token is malformed.") from None
    if header.get("alg") not in allowed:
        raise _unauthorized("INVALID_TOKEN", "The token signing algorithm is not allowed.")
    try:
        return jwt.decode(
            token,
            _verification_key(token),
            algorithms=allowed,
            audience=cfg["JWT_AUDIENCE"],
            issuer=cfg["JWT_ISSUER"],
            options={"require": ["exp", "nbf", "iat", "iss", "aud", "sub", "jti"], "verify_exp": verify_exp},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("TOKEN_EXPIRED", "The access token has expired.") from None
    except jwt.ImmatureSignatureError:
        raise _unauthorized("INVALID_TOKEN", "The access token is not valid yet.") from None
    except jwt.InvalidAudienceError:
        raise _unauthorized("INVALID_TOKEN", "The access token audience is invalid.") from None
    except jwt.InvalidIssuerError:
        raise _unauthorized("INVALID_TOKEN", "The access token issuer is invalid.") from None
    except jwt.MissingRequiredClaimError as exc:
        raise _unauthorized("INVALID_TOKEN", f"The access token is missing the '{exc.claim}' claim.") from None
    except jwt.PyJWTError:
        raise _unauthorized("INVALID_TOKEN", "The access token signature is invalid.") from None


def revoke_jti(jti: str, exp: int) -> None:
    ttl = max(1, int(exp - time.time()))
    redis_client.set(f"jwt:revoked:{jti}", "1", ex=ttl)


def is_revoked(jti: str) -> bool:
    return bool(redis_client.exists(f"jwt:revoked:{jti}"))


def authenticate_request() -> dict:
    if "access_token" in request.args:
        raise _unauthorized(
            "TOKEN_IN_QUERY_FORBIDDEN", "Access tokens must be sent in the Authorization header.", "invalid_request"
        )
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if not header:
        raise ApiError(
            401,
            "AUTHENTICATION_REQUIRED",
            "Missing Authorization: Bearer <token> header.",
            headers={"WWW-Authenticate": 'Bearer realm="lol-match-history"'},
        )
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("INVALID_TOKEN", "Authorization header must use the Bearer scheme.", "invalid_request")
    claims = decode_token(token.strip())
    if is_revoked(claims["jti"]):
        raise _unauthorized("TOKEN_REVOKED", "The access token has been revoked.")
    return claims


def require_scopes(*required: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = authenticate_request()
            granted = set((claims.get("scope") or "").split())
            missing = [s for s in required if s not in granted]
            if missing:
                detail = f"Missing required scope(s): {' '.join(missing)}."
                raise ApiError(
                    403,
                    "INSUFFICIENT_SCOPE",
                    detail,
                    headers=_www_auth("insufficient_scope", detail, " ".join(required)),
                    requiredScopes=list(required),
                )
            g.auth = claims
            return fn(*args, **kwargs)

        return wrapper

    return decorator
