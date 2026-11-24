import uuid

from app.api.mock_data import DEMO_PUUID


def test_swagger_ui_and_openapi_spec(client):
    r_spec = client.get("/api/v1/openapi.yaml")
    assert r_spec.status_code == 200
    assert "openapi: 3.0.3" in r_spec.get_data(as_text=True)

    r_docs = client.get("/api/v1/docs/")
    assert r_docs.status_code == 200
    assert r_docs.mimetype == "text/html"
    assert "/api/v1/openapi.yaml" in r_docs.get_data(as_text=True)

    r_redir = client.get("/docs")
    assert r_redir.status_code == 302
    assert r_redir.headers["Location"].endswith("/api/v1/docs/")


def test_oauth_token_operation_and_errors(client):
    r_tok = client.post(
        "/api/v1/oauth/tokens",
        json={"grant_type": "client_credentials", "client_id": "demo-client", "client_secret": "demo-secret"},
    )
    assert r_tok.status_code == 200
    assert r_tok.headers["Cache-Control"] == "no-store"
    body = r_tok.get_json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]

    # Wrong client_secret -> 401 RFC 9457 + WWW-Authenticate
    r_bad = client.post(
        "/api/v1/oauth/tokens",
        json={"grant_type": "client_credentials", "client_id": "demo-client", "client_secret": "wrong"},
    )
    assert r_bad.status_code == 401
    assert r_bad.mimetype == "application/problem+json"
    assert r_bad.get_json()["code"] == "INVALID_CLIENT"
    assert "Basic" in r_bad.headers["WWW-Authenticate"]


def test_get_player_matches_cursor_pagination_and_filters(client, auth_headers):
    headers = auth_headers(["matches:read"])

    r1 = client.get(f"/api/v1/players/{DEMO_PUUID}/matches?limit=5", headers=headers)
    assert r1.status_code == 200
    b1 = r1.get_json()
    assert len(b1["data"]) == 5
    assert b1["summary"]["games"] == 10
    assert b1["pagination"]["hasMore"] is True
    cursor = b1["pagination"]["nextCursor"]
    assert cursor

    r2 = client.get(f"/api/v1/players/{DEMO_PUUID}/matches?limit=5&cursor={cursor}", headers=headers)
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert len(b2["data"]) == 5
    assert b2["pagination"]["hasMore"] is False
    assert b2["pagination"]["nextCursor"] is None
    assert {m["matchId"] for m in b1["data"]}.isdisjoint({m["matchId"] for m in b2["data"]})

    # Unknown query param & tampered cursor -> 400 RFC 9457
    r_bad_q = client.get(f"/api/v1/players/{DEMO_PUUID}/matches?foo=bar", headers=headers)
    assert r_bad_q.status_code == 400
    assert r_bad_q.mimetype == "application/problem+json"
    assert r_bad_q.get_json()["code"] == "UNSUPPORTED_QUERY_PARAMETER"

    r_bad_c = client.get(f"/api/v1/players/{DEMO_PUUID}/matches?cursor=tampered", headers=headers)
    assert r_bad_c.status_code == 400
    assert r_bad_c.get_json()["code"] == "INVALID_CURSOR"


def test_post_sync_jobs_idempotency_and_cooldown(client, auth_headers):
    headers = auth_headers(["players:sync"])
    idem_key = str(uuid.uuid4())

    r1 = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs",
        json={"region": "vn2", "count": 20},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r1.status_code == 202
    assert r1.headers["Location"].startswith("/api/v1/sync-jobs/")
    job_id = r1.get_json()["jobId"]

    # Replay same key + same body -> 202 Idempotent-Replayed
    r_rep = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs",
        json={"region": "vn2", "count": 20},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r_rep.status_code == 202
    assert r_rep.headers.get("Idempotent-Replayed") == "true"
    assert r_rep.get_json()["jobId"] == job_id

    # Same key + different body -> 422 RFC 9457
    r_reuse = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs",
        json={"region": "vn2", "count": 10},
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r_reuse.status_code == 422
    assert r_reuse.mimetype == "application/problem+json"
    assert r_reuse.get_json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    # New key immediately -> 429 cooldown RFC 9457 + Retry-After
    r_429 = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs",
        json={"region": "vn2", "count": 20},
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_429.status_code == 429
    assert r_429.mimetype == "application/problem+json"
    assert int(r_429.headers["Retry-After"]) > 0
    assert r_429.get_json()["code"] == "SYNC_COOLDOWN_ACTIVE"
    assert r_429.get_json()["retryAfterSeconds"] > 0


def test_auth_and_rfc9457_errors(app, client, auth_headers):
    # Missing token -> 401 + WWW-Authenticate
    r_missing = client.get(f"/api/v1/players/{DEMO_PUUID}/matches")
    assert r_missing.status_code == 401
    assert r_missing.mimetype == "application/problem+json"
    assert "Bearer" in r_missing.headers["WWW-Authenticate"]
    assert r_missing.get_json()["traceId"]

    # Token in query string -> 401
    r_qs = client.get(f"/api/v1/players/{DEMO_PUUID}/matches?access_token=abc")
    assert r_qs.status_code == 401
    assert r_qs.get_json()["code"] == "TOKEN_IN_QUERY_FORBIDDEN"

    # Insufficient scope -> 403
    r_403 = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs",
        json={"region": "vn2"},
        headers=auth_headers(["matches:read"]),
    )
    assert r_403.status_code == 403
    assert r_403.get_json()["code"] == "INSUFFICIENT_SCOPE"

    headers = auth_headers(["players:sync"])

    # Wrong Content-Type -> 415
    r_415 = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs", data="region=vn2", content_type="text/plain", headers=headers
    )
    assert r_415.status_code == 415
    assert r_415.mimetype == "application/problem+json"

    # Malformed JSON -> 400
    r_400 = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs", data="{broken", content_type="application/json", headers=headers
    )
    assert r_400.status_code == 400
    assert r_400.get_json()["code"] == "MALFORMED_JSON"

    # Schema validation failure -> 422 with field-level errors
    r_422 = client.post(
        f"/api/v1/players/{DEMO_PUUID}/sync-jobs", json={"count": 999, "extraField": True}, headers=headers
    )
    assert r_422.status_code == 422
    err_422 = r_422.get_json()
    assert err_422["code"] == "VALIDATION_FAILED"
    assert len(err_422["errors"]) >= 2


def test_unhandled_500_returns_rfc9457_without_stack_trace(app, client):
    @app.get("/api/v1/_boom")
    def _boom():
        raise RuntimeError("secret-db-password-leak")

    app.config["PROPAGATE_EXCEPTIONS"] = False
    r_500 = client.get("/api/v1/_boom")
    assert r_500.status_code == 500
    assert r_500.mimetype == "application/problem+json"
    text = r_500.get_data(as_text=True)
    assert "secret-db-password-leak" not in text
    assert "Traceback" not in text
    assert r_500.get_json()["traceId"]
