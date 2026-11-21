"""Flask CLI commands: seed-demo, gen-keys, issue-token, sync-ddragon."""
from __future__ import annotations

import click
from flask import current_app

from .auth.jwt_auth import issue_access_token
from .auth.keys import write_keypair
from .config import DEFAULT_SCOPES
from .extensions import db, redis_client
from .models import Match, MatchParticipant, MatchTimeline, Player, StaticAsset
from .services import ddragon_service
from .services.match_parser import save_match, save_timeline
from .services.timeutil import utcnow

DEMO_PUUID = "demo-puuid-player1-vn2-00000000000000000000000000000000000000000001"
DEMO_PATCH = "16.23.1"

_POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
_CHAMPIONS_BLUE = [266, 64, 157, 222, 412]
_CHAMPIONS_RED = [122, 121, 103, 51, 111]


def _demo_match_payload(index: int, base_ts: int) -> dict:
    match_id = f"VN2_492817{260 + index}"
    win_blue = index % 2 == 0
    duration = 1620 + index * 95
    participants = []
    for slot in range(10):
        is_blue = slot < 5
        is_player = slot == 2  # MIDDLE
        team_id = 100 if is_blue else 200
        champ = _CHAMPIONS_BLUE[slot] if is_blue else _CHAMPIONS_RED[slot - 5]
        if is_player:
            puuid = DEMO_PUUID
            name, tag = "Player1", "VN2"
            kills, deaths, assists = 8 + (index % 5), 2 + (index % 3), 6 + (index % 4)
            cs = 210 + index * 8
        else:
            puuid = f"demo-puuid-bot-{slot:02d}-0000000000000000000000000000000000000000000"
            name, tag = f"Summoner{slot + 1}", "VN2"
            kills, deaths, assists = 4 + (slot % 4), 4 + ((slot + index) % 3), 5 + (slot % 5)
            cs = 160 + slot * 7
        participants.append(
            {
                "puuid": puuid,
                "riotIdGameName": name,
                "riotIdTagline": tag,
                "teamId": team_id,
                "teamPosition": _POSITIONS[slot % 5],
                "championId": champ,
                "win": win_blue if is_blue else not win_blue,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "totalMinionsKilled": cs,
                "neutralMinionsKilled": 18 if slot % 5 == 1 else 4,
                "goldEarned": 11500 + kills * 400 + index * 120,
                "totalDamageDealtToChampions": 18000 + kills * 1500,
                "visionScore": 18 + slot * 2,
                "item0": 3153,
                "item1": 3031,
                "item2": 6673,
                "item3": 3006,
                "item4": 3026,
                "item5": 0,
                "item6": 3363,
                "summoner1Id": 4,
                "summoner2Id": 14 if is_player else 12,
                "perks": {
                    "statPerks": {"defense": 5002, "flex": 5008, "offense": 5005},
                    "styles": [
                        {
                            "style": 8000,
                            "selections": [
                                {"perk": 8008},
                                {"perk": 9111},
                                {"perk": 9104},
                                {"perk": 8014},
                            ],
                        },
                        {"style": 8400, "selections": [{"perk": 8473}, {"perk": 8453}]},
                    ],
                },
            }
        )

    teams = [
        {
            "teamId": 100,
            "win": win_blue,
            "bans": [{"championId": 7}, {"championId": 238}],
            "objectives": {
                "champion": {"kills": 32 if win_blue else 18},
                "baron": {"kills": 1 if win_blue else 0},
                "dragon": {"kills": 3 if win_blue else 1},
                "riftHerald": {"kills": 1},
                "horde": {"kills": 3},
                "tower": {"kills": 8 if win_blue else 3},
                "inhibitor": {"kills": 2 if win_blue else 0},
            },
        },
        {
            "teamId": 200,
            "win": not win_blue,
            "bans": [{"championId": 157}, {"championId": 64}],
            "objectives": {
                "champion": {"kills": 18 if win_blue else 32},
                "baron": {"kills": 0 if win_blue else 1},
                "dragon": {"kills": 1 if win_blue else 3},
                "riftHerald": {"kills": 0},
                "horde": {"kills": 0},
                "tower": {"kills": 3 if win_blue else 8},
                "inhibitor": {"kills": 0 if win_blue else 2},
            },
        },
    ]
    return {
        "metadata": {"matchId": match_id, "participants": [p["puuid"] for p in participants]},
        "info": {
            "queueId": 420 if index < 8 else 440,
            "gameCreation": base_ts + index * 3_600_000,
            "gameDuration": duration,
            "gameEndTimestamp": base_ts + index * 3_600_000 + duration * 1000,
            "gameVersion": DEMO_PATCH,
            "teams": teams,
            "participants": participants,
        },
    }


def _demo_timeline_payload(match_payload: dict) -> dict:
    puuids = match_payload["metadata"]["participants"]
    participants = [{"participantId": i + 1, "puuid": p} for i, p in enumerate(puuids)]
    frames = []
    # Approximate lane coordinates on Summoner's Rift (0..14870)
    lane_coords = {
        1: (2200, 12600),
        2: (4800, 8200),
        3: (7200, 7400),
        4: (12200, 2600),
        5: (11600, 2200),
        6: (2900, 13000),
        7: (9600, 6200),
        8: (7800, 7900),
        9: (12800, 3200),
        10: (12400, 3600),
    }
    for minute in (0, 5, 10, 15, 20, 25):
        pframes = {}
        for pid in range(1, 11):
            is_blue = pid <= 5
            gold_bonus = minute * 55 if is_blue else 0
            xp_bonus = minute * 30 if is_blue else 0
            bx, by = lane_coords[pid]
            dx = (minute * 120) if is_blue else -(minute * 110)
            pframes[str(pid)] = {
                "participantId": pid,
                "totalGold": 500 + minute * 410 + gold_bonus + pid * 15,
                "currentGold": 350,
                "xp": minute * 480 + xp_bonus + pid * 10,
                "level": min(18, 1 + minute // 2),
                "minionsKilled": minute * 8,
                "jungleMinionsKilled": minute * 3 if pid in (2, 7) else 0,
                "position": {"x": max(600, min(14200, bx + dx)), "y": max(600, min(14200, by + dx // 2))},
            }
        events = []
        if minute == 5:
            events.append({"type": "ITEM_PURCHASED", "timestamp": 310000, "participantId": 3, "itemId": 3006})
        if minute == 10:
            events.append(
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 612000,
                    "monsterType": "DRAGON",
                    "monsterSubType": "FIRE_DRAGON",
                    "killerId": 2,
                    "killerTeamId": 100,
                }
            )
        if minute == 15:
            events.append(
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 912000,
                    "monsterType": "RIFTHERALD",
                    "killerId": 2,
                    "killerTeamId": 100,
                }
            )
            events.append(
                {
                    "type": "BUILDING_KILL",
                    "timestamp": 945000,
                    "buildingType": "TOWER_BUILDING",
                    "towerType": "OUTER_TURRET",
                    "laneType": "MID_LANE",
                    "teamId": 200,
                    "killerId": 3,
                }
            )
        if minute == 25:
            events.append(
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 1490000,
                    "monsterType": "BARON_NASHOR",
                    "killerId": 3,
                    "killerTeamId": 100,
                }
            )
        frames.append({"timestamp": minute * 60000, "participantFrames": pframes, "events": events})

    return {
        "metadata": match_payload["metadata"],
        "info": {"frameInterval": 60000, "participants": participants, "frames": frames},
    }


def _demo_static_files(lang: str) -> dict:
    is_vi = lang == "vi_VN"
    champions = {
        "Yasuo": {
            "id": "Yasuo",
            "key": "157",
            "name": "Yasuo",
            "title": "Kẻ Bất Dung Thứ" if is_vi else "the Unforgiven",
            "image": {"full": "Yasuo.png"},
        },
        "Aatrox": {
            "id": "Aatrox",
            "key": "266",
            "name": "Aatrox",
            "title": "Quỷ Kiếm Darkin" if is_vi else "the Darkin Blade",
            "image": {"full": "Aatrox.png"},
        },
        "LeeSin": {
            "id": "LeeSin",
            "key": "64",
            "name": "Lee Sin",
            "title": "Thầy Tu Mù" if is_vi else "the Blind Monk",
            "image": {"full": "LeeSin.png"},
        },
        "Jinx": {
            "id": "Jinx",
            "key": "222",
            "name": "Jinx",
            "title": "Khẩu Pháo Nổi Loạn" if is_vi else "the Loose Cannon",
            "image": {"full": "Jinx.png"},
        },
        "Thresh": {
            "id": "Thresh",
            "key": "412",
            "name": "Thresh",
            "title": "Cai Ngục Xiềng Xích" if is_vi else "the Chain Warden",
            "image": {"full": "Thresh.png"},
        },
    }
    items = {
        "3153": {
            "name": "Gươm Của Vua Vô Danh" if is_vi else "Blade of the Ruined King",
            "gold": {"total": 3200},
            "image": {"full": "3153.png"},
        },
        "3031": {
            "name": "Vô Cực Kiếm" if is_vi else "Infinity Edge",
            "gold": {"total": 3400},
            "image": {"full": "3031.png"},
        },
        "3006": {
            "name": "Giày Cuồng Nộ" if is_vi else "Berserker's Greaves",
            "gold": {"total": 1100},
            "image": {"full": "3006.png"},
        },
    }
    runes = [
        {
            "id": 8000,
            "name": "Chuẩn Xác" if is_vi else "Precision",
            "icon": "perk-images/Styles/7201_Precision.png",
            "slots": [
                {
                    "runes": [
                        {
                            "id": 8008,
                            "name": "Nhịp Độ Chết Người" if is_vi else "Lethal Tempo",
                            "icon": "perk-images/Styles/Precision/LethalTempo/LethalTempoTemp.png",
                        }
                    ]
                }
            ],
        }
    ]
    spells = {
        "SummonerFlash": {
            "id": "SummonerFlash",
            "key": "4",
            "name": "Tốc Biến" if is_vi else "Flash",
            "image": {"full": "SummonerFlash.png"},
        },
        "SummonerDot": {
            "id": "SummonerDot",
            "key": "14",
            "name": "Thiêu Đốt" if is_vi else "Ignite",
            "image": {"full": "SummonerDot.png"},
        },
        "SummonerTeleport": {
            "id": "SummonerTeleport",
            "key": "12",
            "name": "Dịch Chuyển" if is_vi else "Teleport",
            "image": {"full": "SummonerTeleport.png"},
        },
    }
    return {"champions": champions, "items": items, "runes": runes, "spells": spells}


def seed_demo_data() -> dict:
    """Reset demo records and populate 1 player, 10 matches, 1 timeline, and static catalogs."""
    db.create_all()
    redis_client.flushdb()

    # Clear existing demo rows cleanly
    db.session.query(MatchTimeline).delete()
    db.session.query(MatchParticipant).delete()
    db.session.query(Match).delete()
    db.session.query(Player).filter_by(puuid=DEMO_PUUID).delete()
    db.session.query(StaticAsset).filter_by(patch_version=DEMO_PATCH).delete()
    db.session.commit()

    player = Player(
        puuid=DEMO_PUUID,
        region="vn2",
        game_name="Player1",
        tag_line="VN2",
        profile_icon_id=588,
        summoner_level=245,
        solo_tier="DIAMOND",
        solo_rank="II",
        solo_lp=64,
        solo_wins=72,
        solo_losses=58,
        last_synced_at=None,
        updated_at=utcnow(),
    )
    db.session.add(player)

    base_ts = 1763700000000
    latest_payload = None
    for i in range(10):
        payload = _demo_match_payload(i, base_ts)
        save_match(payload, "vn2", commit=False)
        latest_payload = payload

    db.session.flush()
    save_timeline(latest_payload["metadata"]["matchId"], _demo_timeline_payload(latest_payload), commit=False)
    db.session.commit()

    for lang in ("vi_VN", "en_US"):
        ddragon_service.upsert_static_asset(DEMO_PATCH, lang, _demo_static_files(lang))

    return {
        "puuid": DEMO_PUUID,
        "matches": 10,
        "latestMatchId": latest_payload["metadata"]["matchId"],
        "patch": DEMO_PATCH,
    }


def register_cli(app) -> None:
    @app.cli.command("seed-demo")
    def seed_demo_cmd():
        """Seed demo player, 10 matches, 1 timeline, and static catalogs for offline Newman/Locust runs."""
        info = seed_demo_data()
        click.echo(
            f"Seeded demo data: Player1#VN2 (puuid={info['puuid']}), "
            f"{info['matches']} matches (latest={info['latestMatchId']}), patch={info['patch']}"
        )

    @app.cli.command("gen-keys")
    @click.option("--overwrite", is_flag=True, help="Overwrite existing key files.")
    def gen_keys_cmd(overwrite: bool):
        """Generate an RS256 key pair for JWT signing/verification."""
        priv = current_app.config["JWT_PRIVATE_KEY_PATH"]
        pub = current_app.config["JWT_PUBLIC_KEY_PATH"]
        created = write_keypair(priv, pub, overwrite=overwrite)
        click.echo(f"{'Generated' if created else 'Kept existing'} keys at {priv} and {pub}")

    @app.cli.command("issue-token")
    @click.option("--sub", default="demo-client", help="Token subject / client_id.")
    @click.option("--scopes", default=" ".join(DEFAULT_SCOPES), help="Space-separated scopes.")
    def issue_token_cmd(sub: str, scopes: str):
        """Issue a local RS256 access token for manual testing."""
        token, ttl = issue_access_token(sub, scopes.split())
        click.echo(f"Expires in: {ttl}s\nBearer {token}")

    @app.cli.command("sync-ddragon")
    @click.option("--patch", default=None, help="Specific patch version (default: latest).")
    def sync_ddragon_cmd(patch: str | None):
        """Download Data Dragon static files (vi_VN and en_US) into static_assets."""
        version = ddragon_service.sync_patch(version=patch)
        click.echo(f"Synced Data Dragon patch {version}")

    @app.cli.command("crawl-matches")
    @click.option("--region", default="vn2", show_default=True, help="Riot platform region (e.g. vn2, kr, euw1, na1).")
    @click.option("--target-matches", default=100, show_default=True, type=int, help="Number of new matches + timelines to collect.")
    @click.option("--queue", "queue_id", default=420, show_default=True, type=int, help="Queue ID (420=Ranked Solo, 0=all).")
    @click.option("--per-player", default=10, show_default=True, type=int, help="Match IDs fetched per visited player.")
    @click.option("--tier", default="master", show_default=True, type=click.Choice(["challenger", "grandmaster", "master"]))
    @click.option("--seed", "seeds", multiple=True, help="Optional Riot ID seed(s), e.g. --seed 'Name#VN2'.")
    def crawl_matches_cmd(region: str, target_matches: int, queue_id: int, per_player: int, tier: str, seeds: tuple[str, ...]):
        """Crawl real matches + timelines from Riot API into the DB for LightGBM training."""
        from .ml.crawler import crawl_matches

        report = crawl_matches(
            region=region,
            target_matches=target_matches,
            queue_id=queue_id or None,
            matches_per_player=per_player,
            tier=tier,
            seed_riot_ids=list(seeds) if seeds else None,
            on_progress=click.echo,
        )
        click.echo(
            f"Done: saved_matches={report.saved_matches}, saved_timelines={report.saved_timelines}, "
            f"skipped={report.skipped_existing}, players_visited={report.players_visited}, errors={report.errors}"
        )

    @app.cli.command("train-win-model")
    @click.option("--min-matches", default=8, show_default=True, type=int, help="Minimum matches with timelines required.")
    def train_win_model_cmd(min_matches: int):
        """Train LightGBM win-probability model from matches + timelines stored in DB."""
        from .ml.model import train_win_probability_model

        info = train_win_probability_model(min_matches=min_matches)
        click.echo(f"Model trained and saved to: {info['modelPath']}")
        click.echo(f"Metrics: {info['metrics']}")
        top_feats = sorted(info["featureImportances"].items(), key=lambda kv: kv[1], reverse=True)[:8]
        click.echo("Top features: " + ", ".join(f"{k}={v}" for k, v in top_feats))
