"""LightGBM win-probability model training, persistence, inference, and player impact (WPA) attribution."""
from __future__ import annotations

import logging
import math
import pickle
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import Match, MatchParticipant, MatchTimeline
from ..services.timeutil import iso, utcnow
from .features import BLUE, FEATURE_NAMES, RED, ExtractedMatchFrames, extract_match_frames
from .stats_store import ChampionStatsStore

log = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def default_model_path() -> Path:
    try:
        base = Path(current_app.instance_path)
    except RuntimeError:
        base = Path("instance")
    return base / "ml" / "win_prob_model.pkl"


def _sigmoid(x: float) -> float:
    x = max(-15.0, min(15.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p: float) -> float:
    p = max(1e-4, min(1.0 - 1e-4, p))
    return math.log(p / (1.0 - p))


def _heuristic_predict_proba(rows: list[list[float]]) -> list[float]:
    """Smooth logistic fallback used before a LightGBM model has been trained on real data."""
    probs = []
    for r in rows:
        (
            minute,
            initial_wr,
            blue_time_wr_diff,
            blue_scaling_diff,
            _m_x_s,
            gold_diff,
            xp_diff,
            cs_diff,
            level_diff,
            _g_pm,
            _x_pm,
            kill_diff,
            baron_diff,
            dragon_diff,
            herald_diff,
            grub_diff,
            tower_diff,
            inhib_diff,
        ) = r
        # Initial lane-matchup prior decays slightly as in-game state accumulates
        z = _logit(initial_wr)
        # Time-based champion scaling shift (even without big events)
        z += blue_time_wr_diff * 3.0 + (minute / 30.0) * blue_scaling_diff * 2.5
        # In-game state & objective events
        z += gold_diff / 4200.0
        z += xp_diff / 5500.0
        z += cs_diff / 140.0
        z += level_diff * 0.08
        z += kill_diff * 0.06
        z += baron_diff * 0.45 + dragon_diff * 0.18 + herald_diff * 0.12 + grub_diff * 0.05
        z += tower_diff * 0.16 + inhib_diff * 0.45
        probs.append(_sigmoid(z))
    return probs


def train_win_probability_model(
    model_path: Path | None = None,
    min_matches: int = 8,
    min_duration_sec: int = 600,
) -> dict[str, Any]:
    """Train a LightGBM binary classifier on all matches with timelines in the DB.

    Splits train/validation strictly by match_id (never splitting frames of the same match)
    to avoid temporal leakage.
    """
    import lightgbm as lgb
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

    model_path = model_path or default_model_path()
    stats = ChampionStatsStore.build_from_db(min_duration_sec=min_duration_sec)

    timelines = db.session.scalars(select(MatchTimeline)).all()
    if not timelines:
        raise ValueError("No match timelines found in DB. Run `flask crawl-matches` first.")

    tl_by_id = {t.match_id: t for t in timelines}
    matches = db.session.scalars(
        select(Match).where(
            Match.match_id.in_(list(tl_by_id.keys())),
            Match.game_duration >= min_duration_sec,
            Match.winning_team_id.in_([BLUE, RED]),
        )
    ).all()

    if len(matches) < min_matches:
        raise ValueError(
            f"Need at least {min_matches} completed matches with timelines to train LightGBM (found {len(matches)})."
        )

    parts = db.session.scalars(
        select(MatchParticipant).where(MatchParticipant.match_id.in_([m.match_id for m in matches]))
    ).all()
    parts_by_match: dict[str, list[MatchParticipant]] = defaultdict(list)
    for p in parts:
        parts_by_match[p.match_id].append(p)

    # Sort matches chronologically so validation evaluates on newer matches
    matches.sort(key=lambda m: m.game_creation)
    n_val = max(2, int(round(len(matches) * 0.2)))
    train_matches = matches[:-n_val]
    val_matches = matches[-n_val:]

    # Build stats strictly on train_matches to prevent target leakage into validation
    train_stats = ChampionStatsStore.build_from_records(train_matches, parts_by_match)

    def build_dataset(subset: list[Match], base_stats: ChampionStatsStore, leave_one_out: bool) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = [], []
        for m in subset:
            m_parts = parts_by_match.get(m.match_id) or []
            if len(m_parts) != 10:
                continue
            m_stats = base_stats.without_match(m, m_parts) if leave_one_out else base_stats
            extracted = extract_match_frames(m, m_parts, tl_by_id[m.match_id], m_stats)
            label = 1 if m.winning_team_id == BLUE else 0
            for row in extracted.feature_rows:
                xs.append(row)
                ys.append(label)
        return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.int32)

    X_train, y_train = build_dataset(train_matches, train_stats, leave_one_out=True)
    X_val, y_val = build_dataset(val_matches, train_stats, leave_one_out=False)

    if len(X_train) == 0 or len(np.unique(y_train)) < 2:
        raise ValueError("Training set must contain both blue-side wins and red-side wins.")

    clf = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=150,
        learning_rate=0.04,
        max_depth=4,
        num_leaves=15,
        min_child_samples=max(10, min(25, len(X_train) // 25)),
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=42,
        verbose=-1,
    )
    fit_kwargs: dict[str, Any] = {}
    if len(X_val) > 0 and len(np.unique(y_val)) == 2:
        fit_kwargs["eval_X"] = X_val
        fit_kwargs["eval_y"] = y_val
        fit_kwargs["callbacks"] = [lgb.early_stopping(stopping_rounds=20, verbose=False)]
    clf.fit(X_train, y_train, **fit_kwargs)

    metrics: dict[str, Any] = {
        "trainMatches": len(train_matches),
        "valMatches": len(val_matches),
        "trainFrames": int(len(X_train)),
        "valFrames": int(len(X_val)),
        "trainedAt": iso(utcnow()),
    }
    if len(X_val) > 0:
        val_probs = clf.predict_proba(X_val)[:, 1]
        metrics["logLoss"] = round(float(log_loss(y_val, val_probs, labels=[0, 1])), 4)
        metrics["brierScore"] = round(float(brier_score_loss(y_val, val_probs)), 4)
        if len(np.unique(y_val)) == 2:
            metrics["rocAuc"] = round(float(roc_auc_score(y_val, val_probs)), 4)

    importances = {
        name: int(val) for name, val in zip(FEATURE_NAMES, clf.feature_importances_)
    }
    artifact = {
        "model": clf,
        "stats": stats,
        "feature_names": list(FEATURE_NAMES),
        "metrics": metrics,
        "feature_importances": importances,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as fh:
        pickle.dump(artifact, fh)
    _MODEL_CACHE.pop(str(model_path), None)
    log.info("Saved LightGBM win-probability model to %s (%s)", model_path, metrics)
    return {"modelPath": str(model_path), "metrics": metrics, "featureImportances": importances}


def load_model_artifact(model_path: Path | None = None) -> dict[str, Any] | None:
    path = model_path or default_model_path()
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    cached = _MODEL_CACHE.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with path.open("rb") as fh:
            artifact = pickle.load(fh)
        _MODEL_CACHE[str(path)] = (mtime, artifact)
        return artifact
    except Exception:  # pragma: no cover - corrupted file fallback
        log.warning("Failed to load LightGBM artifact at %s; falling back to heuristic", path)
        return None


def _compute_player_contributions(
    extracted: ExtractedMatchFrames,
    participants: list[MatchParticipant],
    blue_probs: list[float],
    focus_puuid: str | None,
) -> tuple[list[dict], list[dict]]:
    """Attribute minute-by-minute win-probability deltas (WPA%) to all 10 players.

    Splits each minute's team win-probability change across:
    1. Combat events (kills, assists, deaths)
    2. Objective events (Baron, Dragon, Herald, Grubs, Towers, Inhibitors)
    3. Laning & farm growth (gold + XP gained vs lane opponent during that minute)
    """
    pids = list(extracted.pid_to_puuid.keys())
    puuid_by_pid = extracted.pid_to_puuid
    team_by_pid = extracted.pid_to_team
    part_by_puuid = {p.puuid: p for p in participants}

    # Pair each participant with their lane opponent for fair laning comparison
    lane_team_pid: dict[tuple[str, int], int] = {}
    for pid, puuid in puuid_by_pid.items():
        part = part_by_puuid.get(puuid)
        if part and part.team_position:
            lane_team_pid[(part.team_position.upper(), part.team_id)] = pid

    opponent_of: dict[int, int] = {}
    for (pos, team), pid in lane_team_pid.items():
        opp = lane_team_pid.get((pos, RED if team == BLUE else BLUE))
        if opp is not None:
            opponent_of[pid] = opp

    totals = {pid: {"combat": 0.0, "objective": 0.0, "laning": 0.0} for pid in pids}
    focus_pid = extracted.puuid_to_pid.get(focus_puuid) if focus_puuid else None
    focus_team = team_by_pid.get(focus_pid, BLUE) if focus_pid else BLUE

    timeline_out: list[dict] = []
    focus_cum = 0.0

    for idx, minute in enumerate(extracted.minutes):
        p_blue = blue_probs[idx]
        p_focus = p_blue if focus_team == BLUE else (1.0 - p_blue)

        if idx == 0:
            timeline_out.append(
                {
                    "minute": minute,
                    "blueWinProb": round(p_blue * 100, 1),
                    "focusWinProb": round(p_focus * 100, 1),
                    "focusImpactDelta": 0.0,
                    "focusImpactCumulative": 0.0,
                }
            )
            continue

        # Delta in percentage points (-100..+100) from blue's perspective
        delta_blue_pct = (p_blue - blue_probs[idx - 1]) * 100.0
        frame_events = extracted.events_by_frame[idx]

        # Raw positive/negative credit signals for each player in this minute (signed in each player's own team frame)
        combat_sig = {pid: 0.0 for pid in pids}
        obj_sig = {pid: 0.0 for pid in pids}
        lane_sig = {pid: 0.0 for pid in pids}

        for ev in frame_events:
            etype = ev.get("type")
            if etype == "CHAMPION_KILL":
                killer = ev.get("killerId")
                victim = ev.get("victimId")
                assists = ev.get("assistingParticipantIds") or []
                if killer in combat_sig:
                    combat_sig[killer] += 1.0
                for a in assists:
                    if a in combat_sig:
                        combat_sig[a] += 0.5
                if victim in combat_sig:
                    combat_sig[victim] -= 1.0
            elif etype == "ELITE_MONSTER_KILL":
                mtype = ev.get("monsterType")
                weight = 3.0 if mtype == "BARON_NASHOR" else (1.5 if mtype in ("DRAGON", "RIFTHERALD") else 0.8)
                killer = ev.get("killerId")
                kt = ev.get("killerTeamId") or team_by_pid.get(killer)
                assists = ev.get("assistingParticipantIds") or []
                if killer in obj_sig:
                    obj_sig[killer] += weight * 0.6
                for a in assists:
                    if a in obj_sig:
                        obj_sig[a] += weight * 0.25
                for pid in pids:
                    if team_by_pid.get(pid) == kt:
                        obj_sig[pid] += weight * 0.15
            elif etype == "BUILDING_KILL":
                weight = 2.0 if ev.get("buildingType") == "INHIBITOR_BUILDING" else 1.2
                killer = ev.get("killerId")
                owner = ev.get("teamId")
                kt = (RED if owner == BLUE else BLUE) if owner in (BLUE, RED) else team_by_pid.get(killer)
                assists = ev.get("assistingParticipantIds") or []
                if killer in obj_sig:
                    obj_sig[killer] += weight * 0.5
                for a in assists:
                    if a in obj_sig:
                        obj_sig[a] += weight * 0.25
                for pid in pids:
                    if team_by_pid.get(pid) == kt:
                        obj_sig[pid] += weight * 0.12

        # Laning/farming growth relative to lane opponent during this minute
        prev_state = extracted.participant_states[idx - 1]
        curr_state = extracted.participant_states[idx]
        for pid in pids:
            g1, x1 = curr_state.get(pid, (0, 0))
            g0, x0 = prev_state.get(pid, (0, 0))
            dg, dx = g1 - g0, x1 - x0
            opp = opponent_of.get(pid)
            if opp is not None:
                og1, ox1 = curr_state.get(opp, (0, 0))
                og0, ox0 = prev_state.get(opp, (0, 0))
                dg -= og1 - og0
                dx -= ox1 - ox0
            lane_sig[pid] = dg / 400.0 + dx / 500.0

        # Attribute team delta_pct proportionally across players & categories
        minute_focus_delta = 0.0
        for team in (BLUE, RED):
            team_delta = delta_blue_pct if team == BLUE else -delta_blue_pct
            team_pids = [pid for pid in pids if team_by_pid.get(pid) == team]

            # Combine category scores aligned with the sign of team_delta (or magnitude fallback)
            weights: dict[tuple[int, str], float] = {}
            total_w = 0.0
            for pid in team_pids:
                for cat, sig in (("combat", combat_sig[pid]), ("objective", obj_sig[pid]), ("laning", lane_sig[pid])):
                    # Players whose action aligns with the probability swing get proportionally more credit/blame
                    aligned = sig if team_delta >= 0 else -sig
                    w = max(0.0, aligned)
                    weights[(pid, cat)] = w
                    total_w += w

            if total_w > 1e-6:
                for (pid, cat), w in weights.items():
                    share = team_delta * (w / total_w)
                    totals[pid][cat] += share
                    if pid == focus_pid:
                        minute_focus_delta += share
            else:
                # Even split across team when swing is purely passive (e.g., team-comp time scaling)
                even = team_delta / max(1, len(team_pids))
                for pid in team_pids:
                    totals[pid]["laning"] += even
                    if pid == focus_pid:
                        minute_focus_delta += even

        focus_cum += minute_focus_delta
        timeline_out.append(
            {
                "minute": minute,
                "blueWinProb": round(p_blue * 100, 1),
                "focusWinProb": round(p_focus * 100, 1),
                "focusImpactDelta": round(minute_focus_delta, 2),
                "focusImpactCumulative": round(focus_cum, 2),
            }
        )

    contributions = []
    for pid in pids:
        puuid = puuid_by_pid[pid]
        part = part_by_puuid.get(puuid)
        c = totals[pid]
        total_imp = c["combat"] + c["objective"] + c["laning"]
        contributions.append(
            {
                "puuid": puuid,
                "riotId": f"{part.riot_id_name}#{part.riot_id_tagline}" if part and part.riot_id_name else None,
                "teamId": team_by_pid.get(pid),
                "teamPosition": part.team_position if part else None,
                "championId": part.champion_id if part else None,
                "isFocus": puuid == focus_puuid,
                "totalImpact": round(total_imp, 2),
                "combatImpact": round(c["combat"], 2),
                "objectiveImpact": round(c["objective"], 2),
                "laningImpact": round(c["laning"], 2),
            }
        )
    contributions.sort(key=lambda x: x["totalImpact"], reverse=True)
    return timeline_out, contributions


def _build_event_timeline(
    extracted: ExtractedMatchFrames,
    participants: list[MatchParticipant],
    blue_probs: list[float],
    win_frames: list[dict],
    focus_puuid: str | None,
    clf: Any | None,
) -> tuple[list[dict], list[dict]]:
    """Build a unified, timestamp-accurate (MM:SS) timeline combining minute ticks and key combat/objective events.

    For every kill / elite monster / building event between minute m and m+1, interpolates the
    feature state and runs LightGBM (or heuristic fallback) to produce sharp win-probability
    swings at the exact second the event occurred.
    """
    puuid_by_pid = extracted.pid_to_puuid
    team_by_pid = extracted.pid_to_team
    part_by_puuid = {p.puuid: p for p in participants}
    champ_by_pid = {
        pid: part_by_puuid[puuid].champion_id
        for pid, puuid in puuid_by_pid.items()
        if puuid in part_by_puuid
    }

    focus_pid = extracted.puuid_to_pid.get(focus_puuid) if focus_puuid else None
    focus_team = team_by_pid.get(focus_pid, BLUE) if focus_pid else BLUE
    impact_by_min = {f["minute"]: (f["focusImpactDelta"], f["focusImpactCumulative"]) for f in win_frames}

    # Collect raw timeline points: (timestampMs, kind, feature_row, event_meta, minute_idx)
    raw_points: list[tuple[int, str, list[float], dict | None, int]] = []
    n_frames = len(extracted.minutes)

    for idx in range(n_frames):
        minute = extracted.minutes[idx]
        frame_ts = minute * 60_000

        # Insert events that happened between previous frame and this frame (accurate to the second)
        if idx > 0:
            prev_row = extracted.feature_rows[idx - 1]
            curr_row = extracted.feature_rows[idx]
            prev_ts = extracted.minutes[idx - 1] * 60_000
            span = max(1, frame_ts - prev_ts)

            interesting = [
                e
                for e in extracted.events_by_frame[idx]
                if e.get("type") in ("CHAMPION_KILL", "ELITE_MONSTER_KILL", "BUILDING_KILL")
            ]
            interesting.sort(key=lambda e: int(e.get("timestamp", frame_ts)))

            # Track incremental event counts within this minute so each event nudges the feature row
            inc_kills = 0.0
            inc_baron = 0.0
            inc_dragon = 0.0
            inc_herald = 0.0
            inc_grub = 0.0
            inc_tower = 0.0
            inc_inhib = 0.0

            for ev in interesting:
                ev_ts = int(ev.get("timestamp", frame_ts))
                alpha = max(0.0, min(1.0, (ev_ts - prev_ts) / span))
                interp = [prev_row[k] + alpha * (curr_row[k] - prev_row[k]) for k in range(len(prev_row))]
                interp[0] = ev_ts / 60_000.0

                etype = ev.get("type")
                meta: dict[str, Any] = {"type": etype}
                if isinstance(ev.get("position"), dict):
                    meta["position"] = {"x": ev["position"].get("x", 0), "y": ev["position"].get("y", 0)}
                if etype == "CHAMPION_KILL":
                    killer = ev.get("killerId")
                    victim = ev.get("victimId")
                    assists = ev.get("assistingParticipantIds") or []
                    kt = team_by_pid.get(int(killer)) if killer is not None else None
                    if kt == BLUE:
                        inc_kills += 1.0
                    elif kt == RED:
                        inc_kills -= 1.0
                    meta.update(
                        {
                            "killerTeamId": kt,
                            "killerChampionId": champ_by_pid.get(int(killer)) if killer else None,
                            "victimChampionId": champ_by_pid.get(int(victim)) if victim else None,
                            "assistChampionIds": [champ_by_pid[int(a)] for a in assists if int(a) in champ_by_pid],
                        }
                    )
                elif etype == "ELITE_MONSTER_KILL":
                    killer = ev.get("killerId")
                    kt = ev.get("killerTeamId") or (team_by_pid.get(int(killer)) if killer else None)
                    sign = 1.0 if kt == BLUE else (-1.0 if kt == RED else 0.0)
                    mtype = ev.get("monsterType")
                    if mtype == "BARON_NASHOR":
                        inc_baron += sign
                    elif mtype == "DRAGON":
                        inc_dragon += sign
                    elif mtype == "RIFTHERALD":
                        inc_herald += sign
                    elif mtype == "HORDE":
                        inc_grub += sign
                    meta.update(
                        {
                            "killerTeamId": kt,
                            "killerChampionId": champ_by_pid.get(int(killer)) if killer else None,
                            "monsterType": mtype,
                            "monsterSubType": ev.get("monsterSubType"),
                        }
                    )
                elif etype == "BUILDING_KILL":
                    killer = ev.get("killerId")
                    owner = ev.get("teamId")
                    kt = (RED if owner == BLUE else BLUE) if owner in (BLUE, RED) else (
                        team_by_pid.get(int(killer)) if killer else None
                    )
                    sign = 1.0 if kt == BLUE else (-1.0 if kt == RED else 0.0)
                    btype = ev.get("buildingType")
                    if btype == "INHIBITOR_BUILDING":
                        inc_inhib += sign
                    else:
                        inc_tower += sign
                    meta.update(
                        {
                            "killerTeamId": kt,
                            "killerChampionId": champ_by_pid.get(int(killer)) if killer else None,
                            "buildingType": btype,
                            "laneType": ev.get("laneType"),
                        }
                    )

                # Apply event deltas on top of prev_row's event counters so probabilities react at the exact second
                interp[11] = prev_row[11] + inc_kills
                interp[12] = prev_row[12] + inc_baron
                interp[13] = prev_row[13] + inc_dragon
                interp[14] = prev_row[14] + inc_herald
                interp[15] = prev_row[15] + inc_grub
                interp[16] = prev_row[16] + inc_tower
                interp[17] = prev_row[17] + inc_inhib

                raw_points.append((ev_ts, etype, interp, meta, idx))

        # Add the round minute tick itself
        raw_points.append((frame_ts, "MINUTE", extracted.feature_rows[idx], None, idx))

    if not raw_points:
        return [], []

    # Predict probabilities in one batch
    rows_matrix = [p[2] for p in raw_points]
    if clf is not None:
        probs = [float(v) for v in clf.predict_proba(np.asarray(rows_matrix, dtype=np.float32))[:, 1]]
    else:
        probs = _heuristic_predict_proba(rows_matrix)

    # Anchor timestamp 0 to initial_win_rate
    if raw_points[0][0] == 0:
        probs[0] = extracted.initial_win_rate

    timeline_points: list[dict] = []
    prev_focus_prob = None

    for i, (ts, kind, _row, meta, min_idx) in enumerate(raw_points):
        p_blue = probs[i]
        p_focus = p_blue if focus_team == BLUE else (1.0 - p_blue)
        focus_pct = round(p_focus * 100.0, 1)
        blue_pct = round(p_blue * 100.0, 1)
        delta = 0.0 if prev_focus_prob is None else round(focus_pct - prev_focus_prob, 1)
        prev_focus_prob = focus_pct

        minute = extracted.minutes[min_idx]
        imp_delta, imp_cum = impact_by_min.get(minute, (0.0, 0.0))

        point: dict[str, Any] = {
            "id": f"pt-{i}-{ts}",
            "timestampMs": ts,
            "minute": minute,
            "kind": kind,
            "blueWinProb": blue_pct,
            "focusWinProb": focus_pct,
            "probDelta": delta,
            "focusImpactDelta": imp_delta if kind == "MINUTE" else round(delta * 0.6, 2),
            "focusImpactCumulative": imp_cum,
        }
        if meta:
            point.update(meta)
        timeline_points.append(point)

    # Pick up to 5 biggest turning-point events (non-MINUTE) for chart markers & summary cards
    candidates = [p for p in timeline_points if p["kind"] != "MINUTE" and abs(p["probDelta"]) >= 0.5]
    candidates.sort(key=lambda p: abs(p["probDelta"]), reverse=True)

    highlights: list[dict] = []
    used_windows: list[int] = []
    for p in candidates:
        # Spread highlights out so two kills in the same 30s fight don't duplicate cards
        if any(abs(p["timestampMs"] - t) < 30_000 for t in used_windows):
            continue
        used_windows.append(p["timestampMs"])
        positive = p["probDelta"] >= 0
        if p["kind"] == "ELITE_MONSTER_KILL":
            label = "Objective Secured" if positive else "Objective Lost"
        elif p["kind"] == "BUILDING_KILL":
            label = "Tower Taken" if positive else "Tower Lost"
        elif abs(p["probDelta"]) >= 12.0 and positive:
            label = "Epic Play"
        else:
            label = "Kill Trade"
        highlights.append(
            {
                "pointId": p["id"],
                "timestampMs": p["timestampMs"],
                "kind": p["kind"],
                "label": label,
                "probDelta": p["probDelta"],
                "focusWinProb": p["focusWinProb"],
                "monsterType": p.get("monsterType"),
            }
        )
        if len(highlights) >= 5:
            break
    highlights.sort(key=lambda h: h["timestampMs"])
    return timeline_points, highlights


def analyze_match(
    match: Match,
    participants: list[MatchParticipant],
    timeline: MatchTimeline | None,
    focus_puuid: str | None = None,
    model_path: Path | None = None,
) -> dict[str, Any] | None:
    """Compute initial_win_rate, per-minute & per-event LightGBM win probability, and player contributions."""
    if timeline is None or not (timeline.frames_jsonb or []):
        return None

    artifact = load_model_artifact(model_path)
    if artifact is not None:
        stats: ChampionStatsStore = artifact["stats"]
        clf = artifact["model"]
        model_source = "lightgbm"
        model_metrics = artifact.get("metrics")
    else:
        stats = ChampionStatsStore.build_from_db()
        clf = None
        model_source = "heuristic"
        model_metrics = None

    # Subtract this match's own outcome if it was part of the historical store so initial_win_rate is unbiased
    eval_stats = stats.without_match(match, participants) if stats.total_matches > 0 else stats
    extracted = extract_match_frames(match, participants, timeline, eval_stats)
    if not extracted.feature_rows:
        return None

    if clf is not None:
        X = np.asarray(extracted.feature_rows, dtype=np.float32)
        blue_probs = [float(p) for p in clf.predict_proba(X)[:, 1]]
    else:
        blue_probs = _heuristic_predict_proba(extracted.feature_rows)

    # Anchor minute 0 cleanly to the lane-matchup initial_win_rate
    if extracted.minutes and extracted.minutes[0] == 0:
        blue_probs[0] = extracted.initial_win_rate

    win_frames, contributions = _compute_player_contributions(extracted, participants, blue_probs, focus_puuid)
    event_timeline, highlights = _build_event_timeline(
        extracted, participants, blue_probs, win_frames, focus_puuid, clf
    )

    return {
        "modelSource": model_source,
        "modelMetrics": model_metrics,
        "initialBlueWinRate": round(extracted.initial_win_rate * 100, 1),
        "laneMatchups": extracted.lane_matchups,
        "winProbabilityFrames": win_frames,
        "eventTimeline": event_timeline,
        "highlights": highlights,
        "playerContributions": contributions,
    }
