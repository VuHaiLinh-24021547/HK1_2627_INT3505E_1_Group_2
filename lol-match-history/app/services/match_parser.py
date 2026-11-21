"""Parse Riot Match-V5 / Timeline payloads into database rows."""
from __future__ import annotations

from ..extensions import db
from ..models import Match, MatchParticipant, MatchTimeline

KEPT_EVENT_TYPES = {
    "ELITE_MONSTER_KILL",
    "BUILDING_KILL",
    "TURRET_PLATE_DESTROYED",
    "CHAMPION_KILL",
    "ITEM_PURCHASED",
    "ITEM_SOLD",
    "ITEM_DESTROYED",
    "ITEM_UNDO",
}
FRAME_FIELDS = ("totalGold", "currentGold", "xp", "level", "minionsKilled", "jungleMinionsKilled", "position")


def patch_from_game_version(game_version: str) -> str:
    parts = (game_version or "0.0").split(".")
    return ".".join(parts[:2])


def _runes(perks: dict | None) -> dict:
    perks = perks or {}
    styles = perks.get("styles") or []
    primary = styles[0] if styles else {}
    secondary = styles[1] if len(styles) > 1 else {}
    selections = primary.get("selections") or []
    return {
        "primaryStyle": primary.get("style"),
        "subStyle": secondary.get("style"),
        "keystoneId": selections[0].get("perk") if selections else None,
        "perkIds": [s.get("perk") for st in styles for s in (st.get("selections") or [])],
        "statPerks": perks.get("statPerks"),
    }


def parse_participant(p: dict, match_id: str, game_creation: int) -> MatchParticipant:
    return MatchParticipant(
        match_id=match_id,
        puuid=p["puuid"],
        riot_id_name=p.get("riotIdGameName") or p.get("summonerName"),
        riot_id_tagline=p.get("riotIdTagline"),
        team_id=p["teamId"],
        team_position=p.get("teamPosition") or p.get("individualPosition") or None,
        champion_id=p["championId"],
        win=bool(p.get("win")),
        kills=p.get("kills", 0),
        deaths=p.get("deaths", 0),
        assists=p.get("assists", 0),
        cs_total=p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
        gold_earned=p.get("goldEarned", 0),
        damage_to_champs=p.get("totalDamageDealtToChampions", 0),
        vision_score=p.get("visionScore", 0),
        items_jsonb=[p.get(f"item{i}", 0) for i in range(7)],
        runes_jsonb=_runes(p.get("perks")),
        spells_jsonb=[p.get("summoner1Id"), p.get("summoner2Id")],
        game_creation=game_creation,
    )


def save_match(data: dict, region: str, commit: bool = True) -> Match:
    meta, info = data["metadata"], data["info"]
    match_id = meta["matchId"]
    duration = int(info.get("gameDuration", 0))
    if "gameEndTimestamp" not in info and duration > 10_000:  # legacy payloads used milliseconds
        duration //= 1000
    teams = info.get("teams") or []
    winner = next((t["teamId"] for t in teams if t.get("win")), 0)
    game_creation = int(info["gameCreation"])
    match = Match(
        match_id=match_id,
        region=region,
        queue_id=info.get("queueId", 0),
        game_creation=game_creation,
        game_duration=duration,
        patch_version=patch_from_game_version(info.get("gameVersion", "")),
        winning_team_id=winner,
        teams_jsonb=teams,
    )
    db.session.add(match)
    for p in info.get("participants") or []:
        db.session.add(parse_participant(p, match_id, game_creation))
    if commit:
        db.session.commit()
    return match


def compact_timeline(data: dict) -> tuple[int, list, dict]:
    """Reduce a Riot timeline (~1MB) to what the review needs."""
    info = data.get("info") or {}
    meta = data.get("metadata") or {}
    mapping = info.get("participants")
    if not mapping:
        mapping = [{"participantId": i + 1, "puuid": p} for i, p in enumerate(meta.get("participants") or [])]
    frames, events = [], []
    for frame in info.get("frames") or []:
        pframes = {}
        for pid, pf in (frame.get("participantFrames") or {}).items():
            entry = {k: pf.get(k, 0) for k in FRAME_FIELDS if k != "position"}
            if isinstance(pf.get("position"), dict):
                entry["position"] = {"x": pf["position"].get("x", 0), "y": pf["position"].get("y", 0)}
            pframes[str(pf.get("participantId", pid))] = entry
        frames.append({"timestamp": frame.get("timestamp", 0), "participantFrames": pframes})
        events.extend(e for e in frame.get("events") or [] if e.get("type") in KEPT_EVENT_TYPES)
    return int(info.get("frameInterval", 60000)), frames, {"participants": mapping, "events": events}


def save_timeline(match_id: str, data: dict, commit: bool = True) -> MatchTimeline:
    interval, frames, events = compact_timeline(data)
    tl = MatchTimeline(match_id=match_id, interval_ms=interval, frames_jsonb=frames, events_jsonb=events)
    db.session.add(tl)
    if commit:
        db.session.commit()
    return tl
