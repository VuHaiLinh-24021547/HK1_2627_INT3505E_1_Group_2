"""Champion lane-matchup win rates and time-phase scaling curves computed from stored matches."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select

from ..extensions import db
from ..models import Match, MatchParticipant

LANES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
# Bayesian smoothing prior strength: pulls tiny-sample matchups smoothly toward 50%
MATCHUP_PRIOR_M = 8.0
CHAMP_PRIOR_M = 10.0

# Time buckets (in minutes) to capture early-game vs late-game champion scaling
# early: < 25m, mid: 25-32m, late: >= 33m
EARLY_CUTOFF_MIN = 25.0
LATE_CUTOFF_MIN = 33.0


def _smoothed(wins: int, games: int, prior_m: float, prior_p: float = 0.5) -> float:
    return (wins + prior_m * prior_p) / (games + prior_m)


@dataclass
class ChampionStatsStore:
    """Lookup tables for lane matchups and early/mid/late scaling."""

    # (champ_id, opp_champ_id, position) -> [wins, games]
    matchups: dict[tuple[int, int, str], tuple[int, int]] = field(default_factory=dict)
    # champ_id -> [wins, games]
    champ_overall: dict[int, tuple[int, int]] = field(default_factory=dict)
    # (champ_id, phase) -> [wins, games], phase in {"early", "mid", "late"}
    champ_phase: dict[tuple[int, str], tuple[int, int]] = field(default_factory=dict)
    total_matches: int = 0

    @classmethod
    def build_from_records(
        cls,
        matches: list[Match],
        parts_by_match: dict[str, list[MatchParticipant]],
    ) -> "ChampionStatsStore":
        matchup_counts: dict[tuple[int, int, str], list[int]] = defaultdict(lambda: [0, 0])
        champ_counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        phase_counts: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])

        for m in matches:
            m_parts = parts_by_match.get(m.match_id) or []
            if not m_parts:
                continue
            dur_min = m.game_duration / 60.0
            phase = "early" if dur_min < EARLY_CUTOFF_MIN else ("late" if dur_min >= LATE_CUTOFF_MIN else "mid")

            blue_by_lane: dict[str, MatchParticipant] = {}
            red_by_lane: dict[str, MatchParticipant] = {}

            for p in m_parts:
                win_int = 1 if p.win else 0
                c = champ_counts[p.champion_id]
                c[0] += win_int
                c[1] += 1

                pc = phase_counts[(p.champion_id, phase)]
                pc[0] += win_int
                pc[1] += 1

                pos = (p.team_position or "").upper()
                if pos in LANES:
                    if p.team_id == 100:
                        blue_by_lane[pos] = p
                    elif p.team_id == 200:
                        red_by_lane[pos] = p

            for pos in LANES:
                bp = blue_by_lane.get(pos)
                rp = red_by_lane.get(pos)
                if not bp or not rp:
                    continue
                mc_b = matchup_counts[(bp.champion_id, rp.champion_id, pos)]
                mc_b[0] += 1 if bp.win else 0
                mc_b[1] += 1

                mc_r = matchup_counts[(rp.champion_id, bp.champion_id, pos)]
                mc_r[0] += 1 if rp.win else 0
                mc_r[1] += 1

        return cls(
            matchups={k: (v[0], v[1]) for k, v in matchup_counts.items()},
            champ_overall={k: (v[0], v[1]) for k, v in champ_counts.items()},
            champ_phase={k: (v[0], v[1]) for k, v in phase_counts.items()},
            total_matches=len(matches),
        )

    @classmethod
    def build_from_db(cls, min_duration_sec: int = 600) -> "ChampionStatsStore":
        matches = db.session.scalars(select(Match).where(Match.game_duration >= min_duration_sec)).all()
        if not matches:
            return cls()
        parts = db.session.scalars(
            select(MatchParticipant).where(MatchParticipant.match_id.in_([m.match_id for m in matches]))
        ).all()
        by_match: dict[str, list[MatchParticipant]] = defaultdict(list)
        for p in parts:
            by_match[p.match_id].append(p)
        return cls.build_from_records(matches, by_match)

    def without_match(self, match: Match, participants: list[MatchParticipant]) -> "ChampionStatsStore":
        """Return a shallow-adjusted view with this match's outcome subtracted (Leave-One-Match-Out)."""
        dur_min = match.game_duration / 60.0
        phase = "early" if dur_min < EARLY_CUTOFF_MIN else ("late" if dur_min >= LATE_CUTOFF_MIN else "mid")

        matchups = dict(self.matchups)
        champ_overall = dict(self.champ_overall)
        champ_phase = dict(self.champ_phase)

        blue_by_lane: dict[str, MatchParticipant] = {}
        red_by_lane: dict[str, MatchParticipant] = {}
        for p in participants:
            win_int = 1 if p.win else 0
            if p.champion_id in champ_overall:
                w, g = champ_overall[p.champion_id]
                champ_overall[p.champion_id] = (max(0, w - win_int), max(0, g - 1))
            if (p.champion_id, phase) in champ_phase:
                w, g = champ_phase[(p.champion_id, phase)]
                champ_phase[(p.champion_id, phase)] = (max(0, w - win_int), max(0, g - 1))
            pos = (p.team_position or "").upper()
            if pos in LANES:
                if p.team_id == 100:
                    blue_by_lane[pos] = p
                elif p.team_id == 200:
                    red_by_lane[pos] = p

        for pos in LANES:
            bp, rp = blue_by_lane.get(pos), red_by_lane.get(pos)
            if not bp or not rp:
                continue
            kb = (bp.champion_id, rp.champion_id, pos)
            if kb in matchups:
                w, g = matchups[kb]
                matchups[kb] = (max(0, w - (1 if bp.win else 0)), max(0, g - 1))
            kr = (rp.champion_id, bp.champion_id, pos)
            if kr in matchups:
                w, g = matchups[kr]
                matchups[kr] = (max(0, w - (1 if rp.win else 0)), max(0, g - 1))

        return ChampionStatsStore(
            matchups=matchups,
            champ_overall=champ_overall,
            champ_phase=champ_phase,
            total_matches=max(0, self.total_matches - 1),
        )

    def champion_win_rate(self, champion_id: int) -> float:
        wins, games = self.champ_overall.get(champion_id, (0, 0))
        return _smoothed(wins, games, CHAMP_PRIOR_M, 0.5)

    def matchup_win_rate(self, champion_id: int, opponent_id: int, position: str) -> tuple[float, int]:
        """Smoothed win rate of champion_id vs opponent_id in the same lane, plus sample size."""
        pos = (position or "").upper()
        wins, games = self.matchups.get((champion_id, opponent_id, pos), (0, 0))
        # Prior uses relative overall champion strength when matchup sample is small
        champ_wr = self.champion_win_rate(champion_id)
        opp_wr = self.champion_win_rate(opponent_id)
        prior_p = max(0.35, min(0.65, 0.5 + (champ_wr - opp_wr) * 0.5))
        return _smoothed(wins, games, MATCHUP_PRIOR_M, prior_p), games

    def champion_wr_at_minute(self, champion_id: int, minute: float) -> float:
        """Interpolate a champion's win-rate curve across early (15m), mid (28m), and late (40m)."""
        base = self.champion_win_rate(champion_id)
        early = _smoothed(*self.champ_phase.get((champion_id, "early"), (0, 0)), CHAMP_PRIOR_M, base)
        mid = _smoothed(*self.champ_phase.get((champion_id, "mid"), (0, 0)), CHAMP_PRIOR_M, base)
        late = _smoothed(*self.champ_phase.get((champion_id, "late"), (0, 0)), CHAMP_PRIOR_M, base)

        if minute <= 15.0:
            return early
        if minute <= 28.0:
            alpha = (minute - 15.0) / 13.0
            return early + alpha * (mid - early)
        if minute <= 40.0:
            alpha = (minute - 28.0) / 12.0
            return mid + alpha * (late - mid)
        return late

    def champion_scaling_slope(self, champion_id: int) -> float:
        """Positive = late-game scaler (e.g. Smolder/Kayle), Negative = early-game falloff (e.g. Pyke)."""
        base = self.champion_win_rate(champion_id)
        early = _smoothed(*self.champ_phase.get((champion_id, "early"), (0, 0)), CHAMP_PRIOR_M, base)
        late = _smoothed(*self.champ_phase.get((champion_id, "late"), (0, 0)), CHAMP_PRIOR_M, base)
        return late - early

    def compute_initial_win_rate(
        self, participants: list[MatchParticipant]
    ) -> tuple[float, list[dict]]:
        """Average blue-team win rate across the 5 lane matchups (TOP/JUNGLE/MIDDLE/BOTTOM/UTILITY)."""
        blue_by_lane: dict[str, MatchParticipant] = {}
        red_by_lane: dict[str, MatchParticipant] = {}
        for p in participants:
            pos = (p.team_position or "").upper()
            if pos in LANES:
                if p.team_id == 100:
                    blue_by_lane[pos] = p
                elif p.team_id == 200:
                    red_by_lane[pos] = p

        lane_details: list[dict] = []
        wrs: list[float] = []
        for pos in LANES:
            bp = blue_by_lane.get(pos)
            rp = red_by_lane.get(pos)
            if not bp or not rp:
                continue
            wr, games = self.matchup_win_rate(bp.champion_id, rp.champion_id, pos)
            wrs.append(wr)
            lane_details.append(
                {
                    "position": pos,
                    "blueChampionId": bp.champion_id,
                    "redChampionId": rp.champion_id,
                    "blueWinRate": round(wr * 100, 1),
                    "games": games,
                }
            )

        if not wrs:
            return 0.5, lane_details
        initial_wr = sum(wrs) / len(wrs)
        return max(0.25, min(0.75, initial_wr)), lane_details
