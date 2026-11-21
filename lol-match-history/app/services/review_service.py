"""Match history listing and post-game review (scoreboard + timeline analytics)."""
from __future__ import annotations

from collections import defaultdict

from flask import current_app
from sqlalchemy import and_, case, func, or_, select

from ..api.errors import ApiError
from ..extensions import db
from ..ml.model import analyze_match
from ..models import Match, MatchParticipant, MatchTimeline, Player
from . import routing
from .cursor import InvalidCursor, decode_cursor, encode_cursor
from .match_parser import save_match, save_timeline
from .riot_client import RiotClient, get_riot_client

POSITION_ORDER = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
BLUE, RED = 100, 200


# ------------------------------------------------------------------ math
def kda(kills: int, deaths: int, assists: int) -> float:
    """(K + A) / D, treating 0 deaths as 1 so perfect games never divide by zero."""
    return round((kills + assists) / max(deaths, 1), 2)


def cs_per_min(cs_total: int, duration_sec: int) -> float:
    if not duration_sec or duration_sec <= 0:
        return 0.0
    return round(cs_total / (duration_sec / 60), 2)


# -------------------------------------------------------------- timeline
def _team_resolver(participants_map: list[dict] | None, puuid_team: dict[str, int] | None):
    pid_team: dict[int, int] = {}
    for entry in participants_map or []:
        team = (puuid_team or {}).get(entry.get("puuid"))
        if team:
            pid_team[int(entry["participantId"])] = team

    def team_of(pid) -> int | None:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return None
        if pid in pid_team:
            return pid_team[pid]
        if 1 <= pid <= 5:
            return BLUE
        if 6 <= pid <= 10:
            return RED
        return None

    return team_of


def build_timeline_frames(frames: list[dict], team_of=None) -> list[dict]:
    """Per-minute blue-minus-red gold and XP differences."""
    team_of = team_of or _team_resolver(None, None)
    out = []
    for frame in frames:
        gold = {BLUE: 0, RED: 0}
        xp = {BLUE: 0, RED: 0}
        for pid, pf in (frame.get("participantFrames") or {}).items():
            team = team_of(pf.get("participantId", pid))
            if team not in gold:
                continue
            gold[team] += pf.get("totalGold", 0)
            xp[team] += pf.get("xp", 0)
        ts = frame.get("timestamp", 0)
        out.append(
            {
                "minute": int(round(ts / 60000)),
                "timestampMs": ts,
                "blueGold": gold[BLUE],
                "redGold": gold[RED],
                "blueGoldDiff": gold[BLUE] - gold[RED],
                "blueXp": xp[BLUE],
                "redXp": xp[RED],
                "blueXpDiff": xp[BLUE] - xp[RED],
            }
        )
    return out


def extract_key_events(events: list[dict], team_of=None) -> list[dict]:
    """Barons, dragons, heralds (and other epic monsters) plus structure kills."""
    team_of = team_of or _team_resolver(None, None)
    out = []
    for e in events:
        etype = e.get("type")
        if etype == "ELITE_MONSTER_KILL":
            killer_team = e.get("killerTeamId") or team_of(e.get("killerId"))
            item = {
                "timestampMs": e.get("timestamp", 0),
                "type": etype,
                "monsterType": e.get("monsterType"),
                "killerTeamId": killer_team,
            }
            if e.get("monsterSubType"):
                item["monsterSubType"] = e["monsterSubType"]
            out.append(item)
        elif etype == "BUILDING_KILL":
            owner = e.get("teamId")
            killer_team = (RED if owner == BLUE else BLUE) if owner in (BLUE, RED) else team_of(e.get("killerId"))
            out.append(
                {
                    "timestampMs": e.get("timestamp", 0),
                    "type": etype,
                    "buildingType": e.get("buildingType"),
                    "towerType": e.get("towerType"),
                    "laneType": e.get("laneType"),
                    "teamId": owner,
                    "killerTeamId": killer_team,
                    "position": e.get("position"),
                }
            )
    out.sort(key=lambda x: x["timestampMs"])
    return out


def extract_item_purchases(events: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    for e in events:
        if e.get("type") == "ITEM_PURCHASED" and e.get("participantId"):
            out[int(e["participantId"])].append({"timestampMs": e.get("timestamp", 0), "itemId": e.get("itemId")})
    return out


def extract_item_events(events: list[dict]) -> list[dict]:
    """All inventory-mutating events (purchased/sold/destroyed/undo) sorted by timestamp."""
    out = []
    for e in events:
        etype = e.get("type")
        if etype in ("ITEM_PURCHASED", "ITEM_SOLD", "ITEM_DESTROYED", "ITEM_UNDO") and e.get("participantId"):
            item: dict = {
                "timestampMs": int(e.get("timestamp", 0)),
                "type": etype,
                "participantId": int(e["participantId"]),
            }
            if etype == "ITEM_UNDO":
                item["beforeId"] = e.get("beforeId", 0)
                item["afterId"] = e.get("afterId", 0)
            else:
                item["itemId"] = e.get("itemId", 0)
            out.append(item)
    out.sort(key=lambda x: x["timestampMs"])
    return out


def extract_kill_events(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        if e.get("type") == "CHAMPION_KILL":
            out.append(
                {
                    "timestampMs": int(e.get("timestamp", 0)),
                    "killerId": e.get("killerId"),
                    "victimId": e.get("victimId"),
                    "assistingParticipantIds": list(e.get("assistingParticipantIds") or []),
                    "position": e.get("position"),
                }
            )
    out.sort(key=lambda x: x["timestampMs"])
    return out


def build_participant_frames(frames: list[dict]) -> list[dict]:
    """Per-minute snapshot of each participant's gold, level, cs, and (x, y) map position."""
    out = []
    for frame in frames:
        ts = int(frame.get("timestamp", 0))
        p_map: dict[str, dict] = {}
        for pid, pf in (frame.get("participantFrames") or {}).items():
            pos = pf.get("position") if isinstance(pf.get("position"), dict) else None
            p_map[str(pf.get("participantId", pid))] = {
                "gold": int(pf.get("totalGold", 0)),
                "level": int(pf.get("level", 1)),
                "cs": int(pf.get("minionsKilled", 0)) + int(pf.get("jungleMinionsKilled", 0)),
                "x": pos.get("x") if pos else None,
                "y": pos.get("y") if pos else None,
            }
        out.append({"minute": int(round(ts / 60000)), "timestampMs": ts, "participants": p_map})
    return out


# ---------------------------------------------------------------- history
def _serialize_participant_full(p: MatchParticipant, duration: int) -> dict:
    return {
        "puuid": p.puuid,
        "riotId": f"{p.riot_id_name}#{p.riot_id_tagline}" if p.riot_id_name else None,
        "teamId": p.team_id,
        "teamPosition": p.team_position,
        "championId": p.champion_id,
        "win": p.win,
        "kills": p.kills,
        "deaths": p.deaths,
        "assists": p.assists,
        "kda": kda(p.kills, p.deaths, p.assists),
        "csTotal": p.cs_total,
        "csPerMin": cs_per_min(p.cs_total, duration),
        "goldEarned": p.gold_earned,
        "damageToChamps": p.damage_to_champs,
        "visionScore": p.vision_score,
        "items": list(p.items_jsonb or []),
        "spells": list(p.spells_jsonb or []),
        "keystoneId": (p.runes_jsonb or {}).get("keystoneId"),
        "runes": p.runes_jsonb,
    }


def _participant_brief(p: MatchParticipant) -> dict:
    return {
        "puuid": p.puuid,
        "teamId": p.team_id,
        "championId": p.champion_id,
        "teamPosition": p.team_position,
        "riotId": f"{p.riot_id_name}#{p.riot_id_tagline}" if p.riot_id_name else None,
    }


def _sort_participants(parts):
    return sorted(parts, key=lambda p: (p.team_id, POSITION_ORDER.get(p.team_position or "", 9)))


def list_matches(
    puuid: str,
    limit: int = 20,
    cursor: str | None = None,
    queue_id: int | None = None,
    champion_id: int | None = None,
) -> dict:
    if db.session.get(Player, puuid) is None:
        raise ApiError(404, "PLAYER_NOT_FOUND", f"Player '{puuid}' does not exist.")

    secret = current_app.config["SECRET_KEY"]
    filters = [MatchParticipant.puuid == puuid]
    if queue_id is not None:
        filters.append(Match.queue_id == queue_id)
    if champion_id is not None:
        filters.append(MatchParticipant.champion_id == champion_id)

    page_filters = list(filters)
    if cursor:
        try:
            gc, mid = decode_cursor(cursor, secret)
        except InvalidCursor as exc:
            raise ApiError(400, "INVALID_CURSOR", f"The cursor is invalid or has been tampered with ({exc}).") from None
        page_filters.append(
            or_(
                MatchParticipant.game_creation < gc,
                and_(MatchParticipant.game_creation == gc, MatchParticipant.match_id < mid),
            )
        )

    rows = db.session.execute(
        select(MatchParticipant, Match)
        .join(Match, Match.match_id == MatchParticipant.match_id)
        .where(*page_filters)
        .order_by(MatchParticipant.game_creation.desc(), MatchParticipant.match_id.desc())
        .limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    match_ids = [m.match_id for _, m in rows]
    others: dict[str, list[MatchParticipant]] = defaultdict(list)
    if match_ids:
        for p in db.session.scalars(select(MatchParticipant).where(MatchParticipant.match_id.in_(match_ids))):
            others[p.match_id].append(p)

    data = []
    for me, m in rows:
        player = _serialize_participant_full(me, m.game_duration)
        player.pop("runes")
        data.append(
            {
                "matchId": m.match_id,
                "queueId": m.queue_id,
                "gameCreation": m.game_creation,
                "gameDuration": m.game_duration,
                "patch": m.patch_version,
                "player": player,
                "participants": [_participant_brief(p) for p in _sort_participants(others[m.match_id])],
            }
        )

    next_cursor = None
    if has_more and rows:
        last_me, last_m = rows[-1]
        next_cursor = encode_cursor(last_me.game_creation, last_m.match_id, secret)

    return {
        "data": data,
        "summary": _summary(filters),
        "pagination": {"limit": limit, "nextCursor": next_cursor, "hasMore": has_more},
    }


def _summary(filters) -> dict:
    """Aggregate over every stored match matching the filters (independent of the page)."""
    games, wins, k, d, a, cs, dur = db.session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(case((MatchParticipant.win.is_(True), 1), else_=0)), 0),
            func.coalesce(func.sum(MatchParticipant.kills), 0),
            func.coalesce(func.sum(MatchParticipant.deaths), 0),
            func.coalesce(func.sum(MatchParticipant.assists), 0),
            func.coalesce(func.sum(MatchParticipant.cs_total), 0),
            func.coalesce(func.sum(Match.game_duration), 0),
        )
        .select_from(MatchParticipant)
        .join(Match, Match.match_id == MatchParticipant.match_id)
        .where(*filters)
    ).one()
    return {
        "games": int(games),
        "wins": int(wins),
        "losses": int(games - wins),
        "winRate": round(wins * 100 / games, 1) if games else 0.0,
        "avgKda": kda(int(k), int(d), int(a)) if games else 0.0,
        "avgCsPerMin": cs_per_min(int(cs), int(dur)) if games else 0.0,
    }


# ----------------------------------------------------------------- review
def _team_summary(team: dict) -> dict:
    obj = team.get("objectives") or {}

    def kills(name):
        return (obj.get(name) or {}).get("kills", 0)

    return {
        "teamId": team.get("teamId"),
        "win": bool(team.get("win")),
        "kills": kills("champion"),
        "barons": kills("baron"),
        "dragons": kills("dragon"),
        "heralds": kills("riftHerald"),
        "voidGrubs": kills("horde"),
        "towers": kills("tower"),
        "inhibitors": kills("inhibitor"),
        "bans": [b.get("championId") for b in team.get("bans") or []],
    }


def get_review(match_id: str, region: str | None = None, focus_puuid: str | None = None,
               client: RiotClient | None = None) -> dict:
    try:
        region = routing.normalize_region(region) if region else routing.region_from_match_id(match_id)
    except ValueError as exc:
        raise ApiError(400, "INVALID_REGION", str(exc)) from None

    match = db.session.get(Match, match_id)
    if match is None:
        client = client or get_riot_client()
        data = client.get_match(region, match_id)
        if not data:
            raise ApiError(404, "MATCH_NOT_FOUND", f"Match '{match_id}' was not found.")
        match = save_match(data, region)

    participants = _sort_participants(
        db.session.scalars(select(MatchParticipant).where(MatchParticipant.match_id == match_id)).all()
    )
    if focus_puuid and focus_puuid not in {p.puuid for p in participants}:
        raise ApiError(400, "INVALID_FOCUS_PUUID", "focusPuuid did not play in this match.")

    timeline = db.session.get(MatchTimeline, match_id)
    if timeline is None:
        client = client or get_riot_client()
        raw = client.get_timeline(region, match_id)
        if raw:
            timeline = save_timeline(match_id, raw)

    puuid_team = {p.puuid: p.team_id for p in participants}
    timeline_body = None
    purchases: dict[int, list] = {}
    pid_by_puuid: dict[str, int] = {}
    if timeline is not None:
        events_doc = timeline.events_jsonb or {}
        mapping = events_doc.get("participants") or []
        events = events_doc.get("events") or []
        team_of = _team_resolver(mapping, puuid_team)
        pid_by_puuid = {m.get("puuid"): int(m["participantId"]) for m in mapping if m.get("participantId")}
        purchases = extract_item_purchases(events)
        timeline_body = {
            "intervalMs": timeline.interval_ms,
            "frames": build_timeline_frames(timeline.frames_jsonb or [], team_of),
            "keyEvents": extract_key_events(events, team_of),
            "participantFrames": build_participant_frames(timeline.frames_jsonb or []),
            "itemEvents": extract_item_events(events),
            "killEvents": extract_kill_events(events),
        }

    parts_out = []
    for p in participants:
        item = _serialize_participant_full(p, match.game_duration)
        item["isFocus"] = p.puuid == focus_puuid
        item["participantId"] = pid_by_puuid.get(p.puuid)
        item["itemPurchases"] = purchases.get(pid_by_puuid.get(p.puuid), []) if pid_by_puuid else []
        parts_out.append(item)

    analytics = analyze_match(match, participants, timeline, focus_puuid=focus_puuid)

    return {
        "matchId": match.match_id,
        "region": match.region,
        "queueId": match.queue_id,
        "gameCreation": match.game_creation,
        "gameDuration": match.game_duration,
        "patch": match.patch_version,
        "focusPuuid": focus_puuid,
        "teams": [_team_summary(t) for t in sorted(match.teams_jsonb or [], key=lambda t: t.get("teamId", 0))],
        "participants": parts_out,
        "timeline": timeline_body,
        "analytics": analytics,
    }
