import httpx
import pytest
import respx

from app.services.riot_client import (
    RiotAuthError,
    RiotClient,
    RiotNotConfiguredError,
    RiotRateLimitError,
    RiotUpstreamError,
    TokenBucketLimiter,
)


def _client(slept: list[float], max_retries: int = 2, limits=None, max_wait: float = 30) -> RiotClient:
    limiter = TokenBucketLimiter(limits or [(20, 1), (100, 120)], sleep=slept.append, max_wait=max_wait)
    return RiotClient("RGAPI-secret-123", limiter=limiter, max_retries=max_retries, sleep=slept.append)


def test_attaches_riot_token_and_never_leaks_in_repr():
    slept = []
    client = _client(slept)
    assert "RGAPI-secret-123" not in repr(client)

    with respx.mock:
        route = respx.get("https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Player1/VN2").mock(
            return_value=httpx.Response(200, json={"puuid": "p1", "gameName": "Player1", "tagLine": "VN2"})
        )
        res = client.get_account_by_riot_id("vn2", "Player1", "VN2")
        assert res["puuid"] == "p1"
        assert route.calls[0].request.headers["X-Riot-Token"] == "RGAPI-secret-123"


def test_404_returns_none():
    client = _client([])
    with respx.mock:
        respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/VN2_999").mock(return_value=httpx.Response(404))
        assert client.get_match("vn2", "VN2_999") is None


def test_429_reads_retry_after_and_retries_successfully():
    slept = []
    client = _client(slept, max_retries=2)
    with respx.mock:
        route = respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/by-puuid/p1/ids").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "3"}),
                httpx.Response(200, json=["VN2_1", "VN2_2"]),
            ]
        )
        ids = client.get_match_ids("vn2", "p1", start=0, count=20)
        assert ids == ["VN2_1", "VN2_2"]
        assert route.call_count == 2
        assert slept == [3]


def test_429_exhausting_retries_raises_rate_limit_error():
    slept = []
    client = _client(slept, max_retries=2)
    with respx.mock:
        respx.get("https://sea.api.riotgames.com/lol/match/v5/matches/VN2_1").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "5"})
        )
        with pytest.raises(RiotRateLimitError) as exc_info:
            client.get_match("vn2", "VN2_1")
        assert exc_info.value.retry_after == 5
        assert slept == [5, 5]


def test_missing_api_key_raises_not_configured():
    client = RiotClient("", sleep=lambda _: None)
    with pytest.raises(RiotNotConfiguredError):
        client.get_match("vn2", "VN2_1")


def test_auth_and_upstream_errors():
    client = _client([])
    with respx.mock:
        respx.get("https://vn2.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/p1").mock(
            return_value=httpx.Response(403)
        )
        with pytest.raises(RiotAuthError):
            client.get_summoner_by_puuid("vn2", "p1")

        respx.get("https://vn2.api.riotgames.com/lol/league/v4/entries/by-puuid/p1").mock(
            return_value=httpx.Response(503)
        )
        with pytest.raises(RiotUpstreamError):
            client.get_league_entries("vn2", "p1")


def test_token_bucket_blocks_when_budget_exhausted():
    now = [1000.0]
    slept = []
    limiter = TokenBucketLimiter([(1, 10)], clock=lambda: now[0], sleep=slept.append, max_wait=2)
    limiter.acquire("sea.api.riotgames.com")
    with pytest.raises(RiotRateLimitError) as exc_info:
        limiter.acquire("sea.api.riotgames.com")
    assert exc_info.value.retry_after == 10
