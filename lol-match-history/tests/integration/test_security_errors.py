def test_health_endpoint(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["redis"] == "up"
    assert "X-Trace-Id" in r.headers


def test_oauth_token_issue_and_revocation_flow(client):
    r_tok = client.post(
        "/api/v1/oauth/tokens",
        json={"grant_type": "client_credentials", "client_id": "demo-client", "client_secret": "demo-secret"},
    )
    assert r_tok.status_code == 200
    token = r_tok.get_json()["access_token"]
    assert r_tok.headers["Cache-Control"] == "no-store"

    # Revoke token, then verify it is rejected
    r_rev = client.post(
        "/api/v1/oauth/revocations",
        json={"token": token, "client_id": "demo-client", "client_secret": "demo-secret"},
    )
    assert r_rev.status_code == 200
    assert r_rev.get_json()["revoked"] is True

    r_after = client.get("/api/v1/static-catalogs/latest", headers={"Authorization": f"Bearer {token}"})
    assert r_after.status_code == 401
    assert r_after.get_json()["code"] == "TOKEN_REVOKED"


def test_auth_error_cases(client, auth_headers):
    # Missing token -> 401 + WWW-Authenticate
    r_missing = client.get("/api/v1/static-catalogs/latest")
    assert r_missing.status_code == 401
    assert r_missing.mimetype == "application/problem+json"
    assert "Bearer" in r_missing.headers["WWW-Authenticate"]
    assert r_missing.get_json()["traceId"]

    # Token in query string -> 401
    r_qs = client.get("/api/v1/static-catalogs/latest?access_token=abc")
    assert r_qs.status_code == 401
    assert r_qs.get_json()["code"] == "TOKEN_IN_QUERY_FORBIDDEN"

    # Insufficient scope -> 403
    r_403 = client.post(
        "/api/v1/players/some-puuid/sync-jobs",
        json={"region": "vn2"},
        headers=auth_headers(["static:read"]),
    )
    assert r_403.status_code == 403
    assert r_403.get_json()["code"] == "INSUFFICIENT_SCOPE"


def test_global_exception_handler_formats(app, client, auth_headers):
    headers = auth_headers(["players:sync"])

    # Wrong Content-Type -> 415
    r_415 = client.post("/api/v1/players/p1/sync-jobs", data="region=vn2", content_type="text/plain", headers=headers)
    assert r_415.status_code == 415
    assert r_415.mimetype == "application/problem+json"

    # Malformed JSON -> 400
    r_400 = client.post(
        "/api/v1/players/p1/sync-jobs", data="{broken", content_type="application/json", headers=headers
    )
    assert r_400.status_code == 400
    assert r_400.get_json()["code"] == "MALFORMED_JSON"

    # Schema validation failure -> 422 with field-level errors
    r_422 = client.post(
        "/api/v1/players/p1/sync-jobs", json={"count": 999, "extraField": True}, headers=headers
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
