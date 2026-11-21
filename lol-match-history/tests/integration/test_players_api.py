import copy
import uuid

import httpx
import respx

from app.extensions import db
from app.services.match_parser import save_match


def _clone_match(sample_match, match_id: str, game_creation: int, queue_id: int = 420, champ_id: int = 157):
    m = copy.deepcopy(sample_match)
    m["metadata"]["matchId"] = match_id
    m["info"]["gameCreation"] = game_creation
    m["info"]["queueId"] = queue_id
    for p in m["info"]["participants"]:
        if p["riotIdGameName"] == "Player1":
            p["championId"] = champ_id
    return m


def test_player_lookup_saves_to_db_and_caches(client, auth_headers, sample_account, sample_summoner, sample_league):
    puuid = sample_account["puuid"]
    headers = auth_headers(["players:read"])
    with respx.mock:
        acc = respx.get("https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Player1/VN2").mock(
            return_value=httpx.Response(200, json=sample_account)
        )
        respx.get(f"https://vn2.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}").mock(
            return_value=httpx.Response(200, json=sample_summoner)
        )
        respx.get(f"https://vn2.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}").mock(
            return_value=httpx.Response(200, json=sample_league)
        )

        r1 = client.get("/api/v1/regions/vn2/players/Player1/VN2", headers=headers)
        assert r1.status_code == 200
        body = r1.get_json()
        assert body["puuid"] == puuid
        assert body["soloTier"] == "DIAMOND"
        assert body["soloRank"] == "II"
        assert body["canSync"] is True
        assert body["cooldownRemainingSec"] == 0
        assert acc.call_count == 1

        # Second call hits Redis/DB without calling Riot again
        r2 = client.get("/api/v1/regions/vn2/players/player1/vn2", headers=headers)
        assert r2.status_code == 200
        assert acc.call_count == 1


def test_player_lookup_404_and_invalid_region(client, auth_headers):
    headers = auth_headers(["players:read"])
    r_bad = client.get("/api/v1/regions/mars1/players/Player1/VN2", headers=headers)
    assert r_bad.status_code == 400
    assert r_bad.mimetype == "application/problem+json"
    assert r_bad.get_json()["code"] == "INVALID_REGION"

    with respx.mock:
        respx.get("https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Ghost/VN2").mock(
            return_value=httpx.Response(404)
        )
        r_404 = client.get("/api/v1/regions/vn2/players/Ghost/VN2", headers=headers)
        assert r_404.status_code == 404
        assert r_404.get_json()["code"] == "PLAYER_NOT_FOUND"


def test_sync_deduplication_cooldown_and_idempotency(
    app, client, auth_headers, sample_account, sample_summoner, sample_league, sample_match
):
    puuid = sample_account["puuid"]
    headers = auth_headers(["players:read", "players:sync"])

    # Pre-seed player and one existing match VN2_492817261
    with respx.mock:
        respx.get("https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Player1/VN2").mock(
            return_value=httpx.Response(200, json=sample_account)
        )
        respx.get(f"https://vn2.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}").mock(
            return_value=httpx.Response(200, json=sample_summoner)
        )
        respx.get(f"https://vn2.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}").mock(
            return_value=httpx.Response(200, json=sample_league)
        )
        assert client.get("/api/v1/regions/vn2/players/Player1/VN2", headers=headers).status_code == 200

    with app.app_context():
        save_match(sample_match, "vn2")

    new_match = _clone_match(sample_match, "VN2_492817262", 1763715600000)

    idem_key = str(uuid.uuid4())
    with respx.mock:
        respx.get(f"https://vn2.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}").mock(
            return_value=httpx.Response(200, json=sample_summoner)
        )
        respx.get(f"https://vn2.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}").mock(
            return_value=httpx.Response(200, json=sample_league)
        )
        respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids").mock(
            return_value=httpx.Response(200, json=["VN2_492817261", "VN2_492817262"])
        )
        existing_route = respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/VN2_492817261").mock(
            return_value=httpx.Response(200, json=sample_match)
        )
        new_route = respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/VN2_492817262").mock(
            return_value=httpx.Response(200, json=new_match)
        )

        # 1st sync -> 202, skips existing match
        r1 = client.post(
            f"/api/v1/players/{puuid}/sync-jobs",
            json={"region": "vn2", "count": 20, "queueId": 420},
            headers={**headers, "Idempotency-Key": idem_key},
        )
        assert r1.status_code == 202
        assert "Location" in r1.headers
        job1 = r1.get_json()
        assert job1["status"] == "finished"
        assert job1["result"]["newMatches"] == 1
        assert job1["result"]["skippedExisting"] == 1
        assert existing_route.call_count == 0
        assert new_route.call_count == 1

        # Replay with same Idempotency-Key + same payload -> replays 202 without hitting cooldown
        r_replay = client.post(
            f"/api/v1/players/{puuid}/sync-jobs",
            json={"region": "vn2", "count": 20, "queueId": 420},
            headers={**headers, "Idempotency-Key": idem_key},
        )
        assert r_replay.status_code == 202
        assert r_replay.headers.get("Idempotent-Replayed") == "true"
        assert r_replay.get_json()["jobId"] == job1["jobId"]

        # Same Idempotency-Key + different payload -> 422
        r_reuse = client.post(
            f"/api/v1/players/{puuid}/sync-jobs",
            json={"region": "vn2", "count": 10},
            headers={**headers, "Idempotency-Key": idem_key},
        )
        assert r_reuse.status_code == 422
        assert r_reuse.get_json()["code"] == "IDEMPOTENCY_KEY_REUSED"

        # New Idempotency-Key immediately -> 429 cooldown
        r2 = client.post(
            f"/api/v1/players/{puuid}/sync-jobs",
            json={"region": "vn2", "count": 20},
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert r2.status_code == 429
        assert r2.mimetype == "application/problem+json"
        assert int(r2.headers["Retry-After"]) > 0
        err = r2.get_json()
        assert err["code"] == "SYNC_COOLDOWN_ACTIVE"
        assert err["retryAfterSeconds"] > 0

        # GET sync-job: owner sees 200, different client gets 404 (BOLA protection)
        r_job = client.get(r1.headers["Location"], headers=headers)
        assert r_job.status_code == 200
        assert r_job.get_json()["jobId"] == job1["jobId"]

        other_headers = auth_headers(["players:sync"], sub="other-client")
        assert client.get(r1.headers["Location"], headers=other_headers).status_code == 404


def test_match_history_cursor_pagination_and_filters(app, client, auth_headers, sample_account, sample_match):
    from app.models import Player

    puuid = sample_account["puuid"]
    with app.app_context():
        db.session.add(Player(puuid=puuid, region="vn2", game_name="Player1", tag_line="VN2"))
        save_match(_clone_match(sample_match, "VN2_1001", 1763700000000, queue_id=420, champ_id=157), "vn2", commit=False)
        save_match(_clone_match(sample_match, "VN2_1002", 1763703600000, queue_id=420, champ_id=266), "vn2", commit=False)
        save_match(_clone_match(sample_match, "VN2_1003", 1763707200000, queue_id=440, champ_id=157), "vn2", commit=False)
        db.session.commit()

    headers = auth_headers(["matches:read"])
    # Page 1 (limit=2)
    r1 = client.get(f"/api/v1/players/{puuid}/matches?limit=2", headers=headers)
    assert r1.status_code == 200
    b1 = r1.get_json()
    assert [m["matchId"] for m in b1["data"]] == ["VN2_1003", "VN2_1002"]
    assert b1["pagination"]["hasMore"] is True
    assert b1["pagination"]["nextCursor"] is not None
    assert b1["summary"]["games"] == 3

    # Page 2
    cursor = b1["pagination"]["nextCursor"]
    r2 = client.get(f"/api/v1/players/{puuid}/matches?limit=2&cursor={cursor}", headers=headers)
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert [m["matchId"] for m in b2["data"]] == ["VN2_1001"]
    assert b2["pagination"]["hasMore"] is False
    assert b2["pagination"]["nextCursor"] is None

    # Filter by queueId and championId
    rf = client.get(f"/api/v1/players/{puuid}/matches?queueId=420&championId=157", headers=headers)
    assert rf.status_code == 200
    assert [m["matchId"] for m in rf.get_json()["data"]] == ["VN2_1001"]

    # Reject unknown query parameter, invalid limit, tampered cursor
    assert client.get(f"/api/v1/players/{puuid}/matches?foo=bar", headers=headers).status_code == 400
    assert client.get(f"/api/v1/players/{puuid}/matches?limit=0", headers=headers).status_code == 400
    assert client.get(f"/api/v1/players/{puuid}/matches?limit=51", headers=headers).status_code == 400
    assert client.get(f"/api/v1/players/{puuid}/matches?cursor=tampered", headers=headers).status_code == 400
