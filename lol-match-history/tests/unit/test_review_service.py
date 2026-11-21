from app.services import review_service
from app.services.match_parser import compact_timeline


def test_kda_handles_zero_deaths():
    assert review_service.kda(10, 0, 5) == 15.0
    assert review_service.kda(9, 3, 7) == 5.33
    assert review_service.kda(0, 0, 0) == 0.0


def test_cs_per_min():
    assert review_service.cs_per_min(248, 1842) == 8.08
    assert review_service.cs_per_min(100, 0) == 0.0


def test_timeline_gold_xp_diff_and_key_events(sample_timeline):
    interval, frames, events_doc = compact_timeline(sample_timeline)
    assert interval == 60000

    diff_frames = review_service.build_timeline_frames(frames)
    assert len(diff_frames) == 2
    assert diff_frames[0]["minute"] == 10
    assert diff_frames[0]["blueGoldDiff"] == 850
    assert diff_frames[0]["blueXpDiff"] == 420
    assert diff_frames[1]["minute"] == 15
    assert diff_frames[1]["blueGoldDiff"] == 2400
    assert diff_frames[1]["blueXpDiff"] == 1150

    key_events = review_service.extract_key_events(events_doc["events"])
    assert len(key_events) == 2
    assert key_events[0]["type"] == "ELITE_MONSTER_KILL"
    assert key_events[0]["monsterType"] == "RIFTHERALD"
    assert key_events[0]["killerTeamId"] == 100
    assert key_events[1]["type"] == "BUILDING_KILL"
    assert key_events[1]["killerTeamId"] == 100  # red team's tower destroyed -> killer is blue (100)

    purchases = review_service.extract_item_purchases(events_doc["events"])
    assert purchases[3] == [{"timestampMs": 590000, "itemId": 3006}]
