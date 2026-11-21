"""Locust load test for LoL Match History API v1 (~80% reads, ~20% writes) with SLO enforcement."""
from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, events, task

CLIENT_ID = os.getenv("LOCUST_CLIENT_ID", "demo-client")
CLIENT_SECRET = os.getenv("LOCUST_CLIENT_SECRET", "demo-secret")
SLO_MAX_ERROR_RATE = float(os.getenv("SLO_MAX_ERROR_RATE", "0.01"))
SLO_P95_MS = float(os.getenv("SLO_P95_MS", "300"))
SLO_P99_MS = float(os.getenv("SLO_P99_MS", "800"))


class MatchHistoryUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        resp = self.client.post(
            "/api/v1/oauth/tokens",
            json={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
            name="/api/v1/oauth/tokens",
        )
        resp.raise_for_status()
        self.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        self.puuid = None
        self.latest_match_id = None
        self.replay_key = str(uuid.uuid4())

        # Resolve demo player once per virtual user
        r = self.client.get("/api/v1/regions/vn2/players/Player1/VN2", headers=self.headers, name="/api/v1/regions/:r/players/:name/:tag")
        if r.status_code == 200:
            self.puuid = r.json()["puuid"]
            m = self.client.get(
                f"/api/v1/players/{self.puuid}/matches?limit=5",
                headers=self.headers,
                name="/api/v1/players/:puuid/matches",
            )
            if m.status_code == 200 and m.json().get("data"):
                self.latest_match_id = m.json()["data"][0]["matchId"]

    @task(25)
    def read_player_profile(self):
        with self.client.get(
            "/api/v1/regions/vn2/players/Player1/VN2",
            headers=self.headers,
            name="/api/v1/regions/:r/players/:name/:tag",
            catch_response=True,
        ) as res:
            if res.status_code != 200 or not res.json().get("puuid"):
                res.failure(f"Unexpected status/body: {res.status_code}")

    @task(30)
    def read_match_history_paginated(self):
        if not self.puuid:
            return
        with self.client.get(
            f"/api/v1/players/{self.puuid}/matches?limit=5",
            headers=self.headers,
            name="/api/v1/players/:puuid/matches",
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Page 1 failed: {res.status_code}")
                return
            body = res.json()
            cursor = (body.get("pagination") or {}).get("nextCursor")
        if cursor:
            with self.client.get(
                f"/api/v1/players/{self.puuid}/matches?limit=5&cursor={cursor}",
                headers=self.headers,
                name="/api/v1/players/:puuid/matches?cursor",
                catch_response=True,
            ) as res2:
                if res2.status_code != 200 or not isinstance(res2.json().get("data"), list):
                    res2.failure(f"Page 2 failed: {res2.status_code}")

    @task(15)
    def read_match_review(self):
        if not self.latest_match_id:
            return
        with self.client.get(
            f"/api/v1/matches/{self.latest_match_id}/review?focusPuuid={self.puuid}",
            headers=self.headers,
            name="/api/v1/matches/:matchId/review",
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Review failed: {res.status_code}")
                return
            body = res.json()
            if len(body.get("teams") or []) != 2 or len(body.get("participants") or []) != 10:
                res.failure("Incomplete match review payload")

    @task(10)
    def read_static_catalog(self):
        with self.client.get(
            "/api/v1/static-catalogs/latest?lang=vi_VN",
            headers=self.headers,
            name="/api/v1/static-catalogs/latest",
            catch_response=True,
        ) as res:
            if res.status_code != 200 or "champions" not in res.json():
                res.failure(f"Catalog failed: {res.status_code}")

    @task(15)
    def write_sync_job_fresh_key(self):
        if not self.puuid:
            return
        headers = {**self.headers, "Idempotency-Key": str(uuid.uuid4())}
        with self.client.post(
            f"/api/v1/players/{self.puuid}/sync-jobs",
            json={"region": "vn2", "count": 20},
            headers=headers,
            name="/api/v1/players/:puuid/sync-jobs",
            catch_response=True,
        ) as res:
            # Both 202 (accepted) and 429 (cooldown active) are expected valid outcomes under load
            if res.status_code in (202, 429):
                res.success()
            else:
                res.failure(f"Unexpected sync status: {res.status_code}")

    @task(5)
    def write_sync_job_idempotency_replay(self):
        if not self.puuid:
            return
        headers = {**self.headers, "Idempotency-Key": self.replay_key}
        with self.client.post(
            f"/api/v1/players/{self.puuid}/sync-jobs",
            json={"region": "vn2", "count": 20},
            headers=headers,
            name="/api/v1/players/:puuid/sync-jobs (idempotent)",
            catch_response=True,
        ) as res:
            if res.status_code in (202, 409, 429):
                res.success()
            else:
                res.failure(f"Unexpected idempotent sync status: {res.status_code}")


@events.quitting.add_listener
def _enforce_slos(environment, **_kwargs):
    total = environment.stats.total
    if total.num_requests == 0:
        return
    error_rate = total.fail_ratio
    p95 = total.get_response_time_percentile(0.95) or 0
    p99 = total.get_response_time_percentile(0.99) or 0
    failed = []
    if error_rate > SLO_MAX_ERROR_RATE:
        failed.append(f"error_rate={error_rate:.4f} > {SLO_MAX_ERROR_RATE}")
    if p95 > SLO_P95_MS:
        failed.append(f"p95={p95:.1f}ms > {SLO_P95_MS}ms")
    if p99 > SLO_P99_MS:
        failed.append(f"p99={p99:.1f}ms > {SLO_P99_MS}ms")
    if failed:
        print("SLO CHECK FAILED:", "; ".join(failed))
        environment.process_exit_code = 1
    else:
        print(f"SLO CHECK PASSED: error_rate={error_rate:.4f}, p95={p95:.1f}ms, p99={p99:.1f}ms")
