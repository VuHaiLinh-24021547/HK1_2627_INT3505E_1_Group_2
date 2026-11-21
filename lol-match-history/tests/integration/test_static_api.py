from app.services import ddragon_service


def test_static_catalog_latest_specific_404_and_caching(app, client, auth_headers, sample_ddragon):
    with app.app_context():
        ddragon_service.upsert_static_asset(
            "16.23.1",
            "vi_VN",
            {
                "champions": sample_ddragon["champion"]["data"],
                "items": sample_ddragon["item"]["data"],
                "runes": sample_ddragon["runes"],
                "spells": sample_ddragon["summoner"]["data"],
            },
        )

    headers = auth_headers(["static:read"])
    r_latest = client.get("/api/v1/static-catalogs/latest?lang=vi_VN", headers=headers)
    assert r_latest.status_code == 200
    assert "max-age=86400" in r_latest.headers["Cache-Control"]
    etag = r_latest.headers["ETag"]
    body = r_latest.get_json()
    assert body["patch"] == "16.23.1"
    assert set(body.keys()) >= {"champions", "items", "runes", "spells"}

    # Conditional GET returns 304 Not Modified
    r_304 = client.get("/api/v1/static-catalogs/latest?lang=vi_VN", headers={**headers, "If-None-Match": etag})
    assert r_304.status_code == 304

    # Specific patch
    r_exact = client.get("/api/v1/static-catalogs/16.23.1?lang=vi_VN", headers=headers)
    assert r_exact.status_code == 200

    # Non-existent patch -> 404
    r_404 = client.get("/api/v1/static-catalogs/99.99?lang=vi_VN", headers=headers)
    assert r_404.status_code == 404
    assert r_404.mimetype == "application/problem+json"
    assert r_404.get_json()["code"] == "PATCH_NOT_FOUND"

    # Bad patch format -> 400
    assert client.get("/api/v1/static-catalogs/not-a-patch", headers=headers).status_code == 400
