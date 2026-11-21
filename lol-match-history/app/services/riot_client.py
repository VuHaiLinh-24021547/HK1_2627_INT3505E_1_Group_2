"""HTTP client for the Riot Games API with token-bucket rate limiting and 429 handling."""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Callable
from urllib.parse import quote

import httpx

from . import routing

log = logging.getLogger(__name__)


class RiotApiError(Exception):
    http_status = 502
    code = "RIOT_UPSTREAM_ERROR"

    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.upstream_status = upstream_status


class RiotUpstreamError(RiotApiError):
    """Riot returned 5xx / unexpected status, or the network failed."""


class RiotAuthError(RiotApiError):
    code = "RIOT_API_KEY_REJECTED"


class RiotNotConfiguredError(RiotApiError):
    http_status = 503
    code = "RIOT_API_KEY_MISSING"


class RiotRateLimitError(RiotApiError):
    http_status = 429
    code = "RIOT_RATE_LIMITED"

    def __init__(self, message: str, retry_after: int):
        super().__init__(message, 429)
        self.retry_after = max(1, int(math.ceil(retry_after)))


class TokenBucketLimiter:
    """Multi-window token bucket shared through Redis (or a local dict fallback).

    Each routing host has one bucket per (capacity, period) window. A request needs one token
    from every bucket; tokens refill continuously at ``capacity / period`` per second.
    """

    def __init__(
        self,
        limits: list[tuple[int, int]],
        redis=None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        max_wait: float = 30,
    ):
        self.limits = [(int(c), float(p)) for c, p in limits]
        self.redis = redis
        self.clock = clock
        self.sleep = sleep
        self.max_wait = max_wait
        self._local: dict[str, dict[str, float]] = {}

    def _key(self, host: str, capacity: int, period: float) -> str:
        return f"riot:bucket:{host}:{capacity}:{int(period)}"

    def _refill(self, state: dict | None, capacity: int, period: float, now: float) -> float:
        if not state:
            return float(capacity)
        tokens = float(state.get("tokens", capacity))
        ts = float(state.get("ts", now))
        return min(float(capacity), tokens + max(0.0, now - ts) * capacity / period)

    def try_acquire(self, host: str) -> float:
        """Take one token from every bucket. Returns 0 on success, else seconds to wait."""
        now = self.clock()
        keys = [self._key(host, c, p) for c, p in self.limits]
        if self.redis is None:
            states = [self._local.get(k) for k in keys]
            tokens = [self._refill(s, c, p, now) for s, (c, p) in zip(states, self.limits)]
            wait = self._wait_time(tokens)
            if wait > 0:
                return wait
            for k, t in zip(keys, tokens):
                self._local[k] = {"tokens": t - 1, "ts": now}
            return 0.0

        from redis.exceptions import WatchError

        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(*keys)
                    states = [pipe.hgetall(k) for k in keys]
                    tokens = [self._refill(s, c, p, now) for s, (c, p) in zip(states, self.limits)]
                    wait = self._wait_time(tokens)
                    if wait > 0:
                        pipe.unwatch()
                        return wait
                    pipe.multi()
                    for k, t, (_, p) in zip(keys, tokens, self.limits):
                        pipe.hset(k, mapping={"tokens": t - 1, "ts": now})
                        pipe.expire(k, int(p) + 5)
                    pipe.execute()
                    return 0.0
                except WatchError:  # pragma: no cover - concurrent writers
                    continue

    def _wait_time(self, tokens: list[float]) -> float:
        wait = 0.0
        for t, (c, p) in zip(tokens, self.limits):
            if t < 1:
                wait = max(wait, (1 - t) * p / c)
        return wait

    def acquire(self, host: str) -> None:
        waited = 0.0
        while True:
            wait = self.try_acquire(host)
            if wait <= 0:
                return
            if waited + wait > self.max_wait:
                raise RiotRateLimitError("Local Riot API rate limit budget exhausted", retry_after=wait)
            self.sleep(wait)
            waited += wait


class RiotClient:
    def __init__(
        self,
        api_key: str,
        limiter: TokenBucketLimiter | None = None,
        max_retries: int = 2,
        timeout: float = 10,
        sleep: Callable[[float], None] = time.sleep,
        http: httpx.Client | None = None,
    ):
        self._api_key = api_key or ""
        self.limiter = limiter or TokenBucketLimiter([(20, 1), (100, 120)], sleep=sleep)
        self.max_retries = max_retries
        self.sleep = sleep
        self.http = http or httpx.Client(timeout=timeout)

    def __repr__(self) -> str:  # never leak the key
        return f"<RiotClient key={'set' if self._api_key else 'missing'}>"

    # ------------------------------------------------------------------ core
    def _request(self, host: str, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self._api_key:
            raise RiotNotConfiguredError("RIOT_API_KEY is not configured on the server")
        url = f"https://{host}{path}"
        params = {k: v for k, v in (params or {}).items() if v is not None}
        attempt = 0
        while True:
            self.limiter.acquire(host)
            try:
                resp = self.http.get(url, params=params, headers={"X-Riot-Token": self._api_key})
            except httpx.HTTPError as exc:
                log.warning("Riot request failed host=%s path=%s err=%s", host, path, type(exc).__name__)
                raise RiotUpstreamError("Could not reach Riot API") from None

            status = resp.status_code
            if status == 200:
                try:
                    return resp.json()
                except (json.JSONDecodeError, ValueError):
                    raise RiotUpstreamError("Riot API returned invalid JSON", status) from None
            if status == 404:
                return None
            if status == 429:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                if attempt < self.max_retries:
                    attempt += 1
                    log.info("Riot 429 on %s, retry %s after %ss", host, attempt, retry_after)
                    self.sleep(retry_after)
                    continue
                raise RiotRateLimitError("Riot API rate limit exceeded", retry_after=retry_after)
            if status in (401, 403):
                log.warning("Riot auth rejected host=%s path=%s status=%s", host, path, status)
                raise RiotAuthError("Riot API rejected the server API key", status)
            log.warning("Riot unexpected status host=%s path=%s status=%s", host, path, status)
            raise RiotUpstreamError(f"Riot API returned HTTP {status}", status)

    # ------------------------------------------------------------- endpoints
    def get_account_by_riot_id(self, region: str, game_name: str, tag_line: str) -> dict | None:
        r = routing.resolve(region)
        path = f"/riot/account/v1/accounts/by-riot-id/{quote(game_name, safe='')}/{quote(tag_line, safe='')}"
        return self._request(r.account_host, path)

    def get_summoner_by_puuid(self, region: str, puuid: str) -> dict | None:
        r = routing.resolve(region)
        return self._request(r.platform_host, f"/lol/summoner/v4/summoners/by-puuid/{quote(puuid, safe='')}")

    def get_league_entries(self, region: str, puuid: str) -> list | None:
        r = routing.resolve(region)
        return self._request(r.platform_host, f"/lol/league/v4/entries/by-puuid/{quote(puuid, safe='')}")

    def get_apex_league(self, region: str, tier: str = "master", queue: str = "RANKED_SOLO_5x5") -> dict | None:
        """Fetch Challenger / Grandmaster / Master league entries (contains PUUIDs for crawling)."""
        tier = tier.strip().lower()
        if tier not in ("challenger", "grandmaster", "master"):
            raise ValueError("tier must be one of: challenger, grandmaster, master")
        r = routing.resolve(region)
        return self._request(r.platform_host, f"/lol/league/v4/{tier}leagues/by-queue/{quote(queue, safe='')}")

    def get_match_ids(
        self, region: str, puuid: str, start: int = 0, count: int = 20, queue: int | None = None
    ) -> list[str]:
        r = routing.resolve(region)
        data = self._request(
            r.match_host,
            f"/lol/match/v5/matches/by-puuid/{quote(puuid, safe='')}/ids",
            {"start": start, "count": count, "queue": queue},
        )
        return list(data or [])

    def get_match(self, region: str, match_id: str) -> dict | None:
        r = routing.resolve(region)
        return self._request(r.match_host, f"/lol/match/v5/matches/{quote(match_id, safe='')}")

    def get_timeline(self, region: str, match_id: str) -> dict | None:
        r = routing.resolve(region)
        return self._request(r.match_host, f"/lol/match/v5/matches/{quote(match_id, safe='')}/timeline")


def _parse_retry_after(value: str | None) -> int:
    try:
        return max(1, int(math.ceil(float(value))))
    except (TypeError, ValueError):
        return 1


def get_riot_client() -> RiotClient:
    """Build a client from the current Flask app configuration."""
    from flask import current_app

    cfg = current_app.config
    sleep = current_app.extensions.get("riot_sleep", time.sleep)
    limiter = TokenBucketLimiter(
        cfg["RIOT_RATE_LIMITS"],
        redis=current_app.extensions.get("redis"),
        sleep=sleep,
        max_wait=cfg["RIOT_LIMITER_MAX_WAIT_SEC"],
    )
    return RiotClient(
        cfg.get("RIOT_API_KEY", ""),
        limiter=limiter,
        max_retries=cfg["RIOT_MAX_RETRIES"],
        timeout=cfg["RIOT_HTTP_TIMEOUT"],
        sleep=sleep,
    )
