import httpx
import respx

from app.services.match_parser import save_match


def test_match_review_lazy_fetches_timeline_once_then_uses_db(app, client, auth_headers, sample_match, sample_timeline):
    match_id = sample_match["metadata"]["matchId"]
    focus = "test-puuid-player1-vn2-00000000000000000000000000000000000000000001"
    with app.app_context():
        save_match(sample_match, "vn2")

    headers = auth_headers(["matches:read"])
    with respx.mock:
        tl_route = respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline").mock(
            return_value=httpx.Response(200, json=sample_timeline)
        )

        # First call lazy-fetches timeline from Riot and persists it
        r1 = client.get(f"/api/v1/matches/{match_id}/review?focusPuuid={focus}", headers=headers)
        assert r1.status_code == 200
        body = r1.get_json()
        assert len(body["teams"]) == 2
        assert len(body["participants"]) == 10
        assert sum(1 for p in body["participants"] if p["isFocus"]) == 1
        assert body["timeline"]["frames"][0]["blueGoldDiff"] == 850
        assert body["timeline"]["frames"][1]["blueXpDiff"] == 1150
        assert len(body["timeline"]["keyEvents"]) == 2
        assert tl_route.call_count == 1

        # Second call reads entirely from DB (0 Riot calls)
        r2 = client.get(f"/api/v1/matches/{match_id}/review", headers=headers)
        assert r2.status_code == 200
        assert tl_route.call_count == 1


def test_match_review_errors(client, auth_headers):
    headers = auth_headers(["matches:read"])
    assert client.get("/api/v1/matches/bad-id/review", headers=headers).status_code == 400

    with respx.mock:
        respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/VN2_999999").mock(return_value=httpx.Response(404))
        r404 = client.get("/api/v1/matches/VN2_999999/review", headers=headers)
        assert r404.status_code == 404
        assert r404.get_json()["code"] == "MATCH_NOT_FOUND"

        respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/VN2_888888").mock(return_value=httpx.Response(503))
        r502 = client.get("/api/v1/matches/VN2_888888/review", headers=headers)
        assert r502.status_code == 502
        assert r502.mimetype == "application/problem+json"
