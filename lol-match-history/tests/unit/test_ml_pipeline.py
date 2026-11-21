import copy
from pathlib import Path

import httpx
import respx

from app.extensions import db
from app.ml.crawler import crawl_matches
from app.ml.model import analyze_match, train_win_probability_model
from app.ml.stats_store import ChampionStatsStore
from app.models import Match, MatchParticipant, MatchTimeline
from app.services.match_parser import save_match, save_timeline


def _synthetic_match_and_timeline(
    sample_match: dict,
    sample_timeline: dict,
    idx: int,
    blue_wins: bool,
    duration_sec: int,
    blue_gold_slope: int,
):
    m = copy.deepcopy(sample_match)
    tl = copy.deepcopy(sample_timeline)
    mid = f"VN2_70000{idx:03d}"
    m["metadata"]["matchId"] = mid
    tl["metadata"]["matchId"] = mid
    m["info"]["gameCreation"] = 1764000000000 + idx * 3_600_000
    m["info"]["gameDuration"] = duration_sec
    m["info"]["teams"][0]["win"] = blue_wins
    m["info"]["teams"][1]["win"] = not blue_wins
    for p in m["info"]["participants"]:
        p["win"] = blue_wins if p["teamId"] == 100 else not blue_wins

    frames = []
    for minute in (0, 5, 10, 15, 20, 25):
        pframes = {}
        for pid in range(1, 11):
            is_blue = pid <= 5
            lead = minute * blue_gold_slope if is_blue else 0
            pframes[str(pid)] = {
                "participantId": pid,
                "totalGold": 500 + minute * 380 + lead,
                "currentGold": 200,
                "xp": minute * 450 + lead,
                "level": min(18, 1 + minute // 2),
                "minionsKilled": minute * 7 + (minute if is_blue and blue_wins else 0),
                "jungleMinionsKilled": minute * 2 if pid in (2, 7) else 0,
            }
        events = []
        if minute == 10:
            events.append(
                {
                    "type": "CHAMPION_KILL",
                    "timestamp": 590000,
                    "killerId": 3 if blue_wins else 8,
                    "victimId": 8 if blue_wins else 3,
                    "assistingParticipantIds": [2] if blue_wins else [7],
                }
            )
        if minute == 20:
            events.append(
                {
                    "type": "ELITE_MONSTER_KILL",
                    "timestamp": 1190000,
                    "monsterType": "BARON_NASHOR",
                    "killerId": 2 if blue_wins else 7,
                    "killerTeamId": 100 if blue_wins else 200,
                    "assistingParticipantIds": [3, 4] if blue_wins else [8, 9],
                }
            )
        frames.append({"timestamp": minute * 60000, "participantFrames": pframes, "events": events})
    tl["info"]["frames"] = frames
    return m, tl


def test_crawler_fetches_apex_seeds_snowballs_and_deduplicates(app, sample_match, sample_timeline):
    seed_puuid = "seed-puuid-master-001"
    mid1 = sample_match["metadata"]["matchId"]
    m2, tl2 = _synthetic_match_and_timeline(sample_match, sample_timeline, 2, True, 1800, 120)
    mid2 = m2["metadata"]["matchId"]

    with respx.mock:
        respx.get("https://vn2.api.riotgames.com/lol/league/v4/masterleagues/by-queue/RANKED_SOLO_5x5").mock(
            return_value=httpx.Response(200, json={"entries": [{"puuid": seed_puuid, "leaguePoints": 500}]})
        )
        respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/by-puuid/{seed_puuid}/ids").mock(
            return_value=httpx.Response(200, json=[mid1, mid2])
        )
        respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/{mid1}").mock(
            return_value=httpx.Response(200, json=sample_match)
        )
        respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/{mid1}/timeline").mock(
            return_value=httpx.Response(200, json=sample_timeline)
        )
        respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/{mid2}").mock(
            return_value=httpx.Response(200, json=m2)
        )
        respx.get(f"https://sea.api.riotgames.com/lol/match/v5/matches/{mid2}/timeline").mock(
            return_value=httpx.Response(200, json=tl2)
        )

        with app.app_context():
            report = crawl_matches(region="vn2", target_matches=2, queue_id=420, tier="master")
            assert report.saved_matches == 2
            assert report.saved_timelines == 2
            assert db.session.get(Match, mid1) is not None
            assert db.session.get(MatchTimeline, mid2) is not None

            # Running again skips already-stored matches
            report2 = crawl_matches(region="vn2", target_matches=2, queue_id=420, seed_puuids=[seed_puuid])
            assert report2.saved_matches == 0
            assert report2.skipped_existing == 2


def test_matchup_initial_win_rate_and_lightgbm_training_and_inference(app, tmp_path, sample_match, sample_timeline):
    with app.app_context():
        # Seed 14 synthetic matches with clear blue-win vs red-win signals and varying durations
        for i in range(14):
            blue_wins = i % 2 == 0
            # Make blue win more in late games (36m) and lose in early games (20m) to test scaling curve
            duration = 2160 if blue_wins else 1200
            slope = 160 if blue_wins else -160
            m, tl = _synthetic_match_and_timeline(sample_match, sample_timeline, i, blue_wins, duration, slope)
            save_match(m, "vn2", commit=False)
            db.session.flush()
            save_timeline(m["metadata"]["matchId"], tl, commit=False)
        db.session.commit()

        # Verify stats store computes matchup win rates and positive/negative scaling slopes
        stats = ChampionStatsStore.build_from_db()
        assert stats.total_matches == 14
        sample_m = db.session.get(Match, "VN2_70000000")
        sample_parts = db.session.query(MatchParticipant).filter_by(match_id=sample_m.match_id).all()
        init_wr, lanes = stats.compute_initial_win_rate(sample_parts)
        assert 0.25 <= init_wr <= 0.75
        assert len(lanes) == 5
        # Blue mid (157) won every late game -> positive scaling slope; Red mid (103) won every early game -> negative slope
        assert stats.champion_scaling_slope(157) > 0
        assert stats.champion_scaling_slope(103) < 0

        # Train LightGBM model and save to temp path
        model_file = Path(tmp_path) / "win_prob_model.pkl"
        res = train_win_probability_model(model_path=model_file, min_matches=8)
        assert model_file.exists()
        assert res["metrics"]["trainMatches"] >= 10
        assert "logLoss" in res["metrics"]

        # Run inference with the trained LightGBM model
        tl_row = db.session.get(MatchTimeline, sample_m.match_id)
        focus_puuid = "test-puuid-player1-vn2-00000000000000000000000000000000000000000001"
        analytics = analyze_match(sample_m, sample_parts, tl_row, focus_puuid=focus_puuid, model_path=model_file)
        assert analytics["modelSource"] == "lightgbm"
        assert len(analytics["laneMatchups"]) == 5
        frames = analytics["winProbabilityFrames"]
        assert len(frames) == 6
        assert frames[0]["minute"] == 0
        assert frames[0]["blueWinProb"] == analytics["initialBlueWinRate"]
        assert all(0.0 <= f["blueWinProb"] <= 100.0 for f in frames)
        assert len(analytics["playerContributions"]) == 10
        assert sum(1 for c in analytics["playerContributions"] if c["isFocus"]) == 1
