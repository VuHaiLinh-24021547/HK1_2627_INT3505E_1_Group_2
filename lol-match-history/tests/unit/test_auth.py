import time

import jwt
import pytest

from app.api.errors import ApiError
from app.auth.jwt_auth import decode_token, issue_access_token, revoke_jti
from app.auth.keys import generate_rsa_keypair


def test_valid_token_and_revocation(app):
    with app.app_context():
        token, ttl = issue_access_token("demo-client", ["players:read"])
        assert ttl == 900
        claims = decode_token(token)
        assert claims["sub"] == "demo-client"
        assert claims["scope"] == "players:read"
        revoke_jti(claims["jti"], claims["exp"])
        from app.auth.jwt_auth import is_revoked

        assert is_revoked(claims["jti"]) is True


def test_rejects_alg_none_and_tampered_signature(app):
    now = int(time.time())
    payload = {
        "iss": app.config["JWT_ISSUER"],
        "aud": app.config["JWT_AUDIENCE"],
        "sub": "demo-client",
        "iat": now,
        "nbf": now,
        "exp": now + 60,
        "jti": "j1",
        "scope": "players:read",
    }
    alg_none = jwt.encode(payload, key=None, algorithm="none")
    other_priv, _ = generate_rsa_keypair()
    wrong_key = jwt.encode(payload, other_priv, algorithm="RS256")
    expired = jwt.encode({**payload, "exp": now - 10}, app.config["JWT_PRIVATE_KEY_PEM"], algorithm="RS256")
    immature = jwt.encode({**payload, "nbf": now + 300}, app.config["JWT_PRIVATE_KEY_PEM"], algorithm="RS256")
    wrong_aud = jwt.encode({**payload, "aud": "other-api"}, app.config["JWT_PRIVATE_KEY_PEM"], algorithm="RS256")
    wrong_iss = jwt.encode({**payload, "iss": "https://evil.example"}, app.config["JWT_PRIVATE_KEY_PEM"], algorithm="RS256")

    with app.app_context():
        for bad in (alg_none, wrong_key, expired, immature, wrong_aud, wrong_iss, "not-a-jwt"):
            with pytest.raises(ApiError) as exc_info:
                decode_token(bad)
            assert exc_info.value.status == 401
