"""Per-minute feature extraction from Match + MatchParticipant + MatchTimeline for LightGBM."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..models import Match, MatchParticipant, MatchTimeline
from .stats_store import ChampionStatsStore

BLUE, RED = 100, 200

FEATURE_NAMES: list[str] = [
    "minute",
    "initial_win_rate",
    "blue_time_wr_diff",
    "blue_scaling_diff",
    "minute_x_scaling",
    "blue_gold_diff",
    "blue_xp_diff",
    "blue_cs_diff",
    "blue_level_diff",
    "gold_diff_per_min",
    "xp_diff_per_min",
    "blue_kill_diff",
    "blue_baron_diff",
    "blue_dragon_diff",
    "blue_herald_diff",
    "blue_grub_diff",
    "blue_tower_diff",
    "blue_inhibitor_diff",
]


@dataclass
class ExtractedMatchFrames:
    initial_win_rate: float
    lane_matchups: list[dict]
    minutes: list[int]
    feature_rows: list[list[float]]
    # Per-frame snapshot of participant gold & xp: minute_index -> {pid: (totalGold, xp)}
    participant_states: list[dict[int, tuple[int, int]]]
    # Events bucketed by minute_index (0..len(minutes)-1)
    events_by_frame: list[list[dict]]
    pid_to_puuid: dict[int, str]
    puuid_to_pid: dict[str, int]
    pid_to_team: dict[int, int]


def _build_pid_maps(participants: list[MatchParticipant], events_doc: dict) -> tuple[dict[int, str], dict[str, int], dict[int, int]]:
    puuid_to_team = {p.puuid: p.team_id for p in participants}
    pid_to_puuid: dict[int, str] = {}
    pid_to_team: dict[int, int] = {}

    for entry in (events_doc or {}).get("participants") or []:
        pid = entry.get("participantId")
        puuid = entry.get("puuid")
        if pid is not None and puuid:
            pid = int(pid)
            pid_to_puuid[pid] = puuid
            pid_to_team[pid] = puuid_to_team.get(puuid, BLUE if pid <= 5 else RED)

    if not pid_to_puuid:
        # Fallback ordering: blue 1..5, red 6..10
        ordered = sorted(participants, key=lambda p: p.team_id)
        for idx, p in enumerate(ordered, start=1):
            pid_to_puuid[idx] = p.puuid
            pid_to_team[idx] = p.team_id

    puuid_to_pid = {puuid: pid for pid, puuid in pid_to_puuid.items()}
    return pid_to_puuid, puuid_to_pid, pid_to_team


def extract_match_frames(
    match: Match,
    participants: list[MatchParticipant],
    timeline: MatchTimeline,
    stats: ChampionStatsStore,
) -> ExtractedMatchFrames:
    events_doc = timeline.events_jsonb or {}
    raw_frames = timeline.frames_jsonb or []
    raw_events = events_doc.get("events") or []

    pid_to_puuid, puuid_to_pid, pid_to_team = _build_pid_maps(participants, events_doc)
    initial_wr, lane_matchups = stats.compute_initial_win_rate(participants)

    blue_champs = [p.champion_id for p in participants if p.team_id == BLUE]
    red_champs = [p.champion_id for p in participants if p.team_id == RED]
    blue_scaling = sum(stats.champion_scaling_slope(c) for c in blue_champs) / max(1, len(blue_champs))
    red_scaling = sum(stats.champion_scaling_slope(c) for c in red_champs) / max(1, len(red_champs))
    blue_scaling_diff = blue_scaling - red_scaling

    # Sort events by timestamp so we can accumulate them monotonically across frames
    sorted_events = sorted(raw_events, key=lambda e: e.get("timestamp", 0))
    ev_idx = 0
    total_events = len(sorted_events)

    cum = {
        "kills": {BLUE: 0, RED: 0},
        "barons": {BLUE: 0, RED: 0},
        "dragons": {BLUE: 0, RED: 0},
        "heralds": {BLUE: 0, RED: 0},
        "grubs": {BLUE: 0, RED: 0},
        "towers": {BLUE: 0, RED: 0},
        "inhibitors": {BLUE: 0, RED: 0},
    }

    minutes: list[int] = []
    feature_rows: list[list[float]] = []
    participant_states: list[dict[int, tuple[int, int]]] = []
    events_by_frame: list[list[dict]] = []

    def team_of_pid(pid) -> int | None:
        try:
            pid_int = int(pid)
        except (TypeError, ValueError):
            return None
        return pid_to_team.get(pid_int, BLUE if 1 <= pid_int <= 5 else (RED if 6 <= pid_int <= 10 else None))

    for frame in raw_frames:
        ts = int(frame.get("timestamp", 0))
        minute = int(round(ts / 60000))
        frame_events: list[dict] = []

        while ev_idx < total_events and int(sorted_events[ev_idx].get("timestamp", 0)) <= ts:
            ev = sorted_events[ev_idx]
            ev_idx += 1
            frame_events.append(ev)
            etype = ev.get("type")
            if etype == "CHAMPION_KILL":
                kt = team_of_pid(ev.get("killerId"))
                if kt in (BLUE, RED):
                    cum["kills"][kt] += 1
            elif etype == "ELITE_MONSTER_KILL":
                kt = ev.get("killerTeamId") or team_of_pid(ev.get("killerId"))
                if kt in (BLUE, RED):
                    mtype = ev.get("monsterType")
                    if mtype == "BARON_NASHOR":
                        cum["barons"][kt] += 1
                    elif mtype == "DRAGON":
                        cum["dragons"][kt] += 1
                    elif mtype == "RIFTHERALD":
                        cum["heralds"][kt] += 1
                    elif mtype == "HORDE":
                        cum["grubs"][kt] += 1
            elif etype == "BUILDING_KILL":
                owner = ev.get("teamId")
                kt = (RED if owner == BLUE else BLUE) if owner in (BLUE, RED) else team_of_pid(ev.get("killerId"))
                if kt in (BLUE, RED):
                    if ev.get("buildingType") == "INHIBITOR_BUILDING":
                        cum["inhibitors"][kt] += 1
                    else:
                        cum["towers"][kt] += 1

        gold = {BLUE: 0, RED: 0}
        xp = {BLUE: 0, RED: 0}
        cs = {BLUE: 0, RED: 0}
        level = {BLUE: 0, RED: 0}
        p_state: dict[int, tuple[int, int]] = {}

        for pid_str, pf in (frame.get("participantFrames") or {}).items():
            pid = int(pf.get("participantId", pid_str))
            team = team_of_pid(pid)
            tg = int(pf.get("totalGold", 0))
            txp = int(pf.get("xp", 0))
            p_state[pid] = (tg, txp)
            if team not in (BLUE, RED):
                continue
            gold[team] += tg
            xp[team] += txp
            cs[team] += int(pf.get("minionsKilled", 0)) + int(pf.get("jungleMinionsKilled", 0))
            level[team] += int(pf.get("level", 1))

        blue_time_wr = sum(stats.champion_wr_at_minute(c, minute) for c in blue_champs) / max(1, len(blue_champs))
        red_time_wr = sum(stats.champion_wr_at_minute(c, minute) for c in red_champs) / max(1, len(red_champs))
        blue_time_wr_diff = blue_time_wr - red_time_wr

        gold_diff = float(gold[BLUE] - gold[RED])
        xp_diff = float(xp[BLUE] - xp[RED])
        denom = max(1.0, float(minute))

        row = [
            float(minute),
            float(initial_wr),
            float(blue_time_wr_diff),
            float(blue_scaling_diff),
            float(minute) * float(blue_scaling_diff),
            gold_diff,
            xp_diff,
            float(cs[BLUE] - cs[RED]),
            float(level[BLUE] - level[RED]),
            gold_diff / denom,
            xp_diff / denom,
            float(cum["kills"][BLUE] - cum["kills"][RED]),
            float(cum["barons"][BLUE] - cum["barons"][RED]),
            float(cum["dragons"][BLUE] - cum["dragons"][RED]),
            float(cum["heralds"][BLUE] - cum["heralds"][RED]),
            float(cum["grubs"][BLUE] - cum["grubs"][RED]),
            float(cum["towers"][BLUE] - cum["towers"][RED]),
            float(cum["inhibitors"][BLUE] - cum["inhibitors"][RED]),
        ]

        minutes.append(minute)
        feature_rows.append(row)
        participant_states.append(p_state)
        events_by_frame.append(frame_events)

    return ExtractedMatchFrames(
        initial_win_rate=initial_wr,
        lane_matchups=lane_matchups,
        minutes=minutes,
        feature_rows=feature_rows,
        participant_states=participant_states,
        events_by_frame=events_by_frame,
        pid_to_puuid=pid_to_puuid,
        puuid_to_pid=puuid_to_pid,
        pid_to_team=pid_to_team,
    )
