"""In-memory mock/seed data store for the Week 12 API scaffold."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json

DEMO_PUUID = "demo-puuid-player1-vn2-00000000000000000000000000000000000000000001"

PLAYERS: dict[str, dict] = {}
MATCHES: list[dict] = []
COOLDOWNS: dict[str, float] = {}
IDEMPOTENCY_STORE: dict[str, dict] = {}
SYNC_JOBS: dict[str, dict] = {}


def _build_demo_matches() -> list[dict]:
    base_ts = 1763700000000
    champs = [157, 266, 64, 222, 412]
    out = []
    # Ordered newest first (-gameCreation)
    for i in range(9, -1, -1):
        win = i % 2 == 0
        duration = 1620 + i * 95
        champ_id = champs[i % len(champs)]
        kills = 8 + (i % 5)
        deaths = 2 + (i % 3)
        assists = 6 + (i % 4)
        cs_total = 210 + i * 8
        out.append(
            {
                "matchId": f"VN2_492817{260 + i}",
                "queueId": 420 if i < 8 else 440,
                "gameCreation": base_ts + i * 3_600_000,
                "gameDuration": duration,
                "patch": "16.23",
                "player": {
                    "puuid": DEMO_PUUID,
                    "riotId": "Player1#VN2",
                    "teamId": 100,
                    "teamPosition": "MIDDLE",
                    "championId": champ_id,
                    "win": win,
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "kda": round((kills + assists) / max(deaths, 1), 2),
                    "csTotal": cs_total,
                    "csPerMin": round(cs_total / (duration / 60), 2),
                    "goldEarned": 12400 + i * 320,
                    "damageToChamps": 24500 + i * 900,
                    "visionScore": 24 + i,
                    "items": [3153, 3031, 6673, 3006, 3026, 0, 3363],
                    "spells": [4, 14],
                    "keystoneId": 8008,
                },
                "participants": [
                    {
                        "puuid": DEMO_PUUID,
                        "teamId": 100,
                        "championId": champ_id,
                        "teamPosition": "MIDDLE",
                        "riotId": "Player1#VN2",
                    },
                    {
                        "puuid": f"bot-enemy-{i}",
                        "teamId": 200,
                        "championId": 103,
                        "teamPosition": "MIDDLE",
                        "riotId": "EnemyMid#VN2",
                    },
                ],
            }
        )
    return out


def reset_mock_store() -> None:
    PLAYERS.clear()
    PLAYERS[DEMO_PUUID] = {"puuid": DEMO_PUUID, "region": "vn2", "riotId": "Player1#VN2"}
    MATCHES.clear()
    MATCHES.extend(_build_demo_matches())
    COOLDOWNS.clear()
    IDEMPOTENCY_STORE.clear()
    SYNC_JOBS.clear()


def encode_cursor(game_creation: int, match_id: str, secret: str) -> str:
    payload = json.dumps({"gc": int(game_creation), "id": match_id}, separators=(",", ":")).encode()
    b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()[:12]).rstrip(b"=").decode()
    return f"{b64}.{sig}"


def decode_cursor(cursor: str, secret: str) -> tuple[int, str]:
    try:
        body, sig = cursor.split(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed cursor") from exc
    expected = base64.urlsafe_b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()[:12]).rstrip(b"=").decode()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Cursor signature mismatch")
    data = json.loads(payload)
    gc, mid = data.get("gc"), data.get("id")
    if not isinstance(gc, int) or isinstance(gc, bool) or not isinstance(mid, str):
        raise ValueError("Malformed cursor payload")
    return gc, mid
