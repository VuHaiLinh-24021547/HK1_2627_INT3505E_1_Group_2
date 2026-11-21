"""Snowball match + timeline crawler bot for collecting real Riot API training data."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select

from ..extensions import db
from ..models import Match, MatchParticipant, MatchTimeline, Player
from ..services import routing
from ..services.match_parser import save_match, save_timeline
from ..services.riot_client import RiotApiError, RiotAuthError, RiotClient, get_riot_client
from ..services.timeutil import utcnow

log = logging.getLogger(__name__)


@dataclass
class CrawlReport:
    region: str
    target_matches: int
    saved_matches: int = 0
    saved_timelines: int = 0
    skipped_existing: int = 0
    players_visited: int = 0
    errors: int = 0
    saved_match_ids: list[str] = field(default_factory=list)


def _seed_puuids_from_league(client: RiotClient, region: str, tier: str, max_seeds: int = 100) -> list[str]:
    league = client.get_apex_league(region, tier=tier)
    if not league:
        return []
    entries = league.get("entries") or []
    entries.sort(key=lambda e: e.get("leaguePoints", 0), reverse=True)
    puuids = []
    for entry in entries:
        puuid = entry.get("puuid")
        if puuid:
            puuids.append(puuid)
        if len(puuids) >= max_seeds:
            break
    return puuids


def _seed_puuids_from_riot_ids(client: RiotClient, region: str, riot_ids: list[str]) -> list[str]:
    out = []
    for raw in riot_ids:
        if "#" not in raw:
            continue
        name, tag = raw.rsplit("#", 1)
        account = client.get_account_by_riot_id(region, name.strip(), tag.strip())
        if account and account.get("puuid"):
            out.append(account["puuid"])
    return out


def _upsert_lightweight_player(puuid: str, region: str, participant: dict) -> None:
    """Save basic player identity from match data so profiles are searchable in DB too."""
    if db.session.get(Player, puuid) is not None:
        return
    name = participant.get("riotIdGameName") or participant.get("summonerName")
    tag = participant.get("riotIdTagline") or region.upper()
    if not name:
        return
    db.session.add(
        Player(
            puuid=puuid,
            region=region,
            game_name=name[:64],
            tag_line=tag[:16],
            updated_at=utcnow(),
        )
    )


def crawl_matches(
    region: str = "vn2",
    target_matches: int = 100,
    queue_id: int | None = 420,
    matches_per_player: int = 10,
    tier: str = "master",
    seed_riot_ids: list[str] | None = None,
    seed_puuids: list[str] | None = None,
    min_duration_sec: int = 600,
    client: RiotClient | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> CrawlReport:
    """Crawl real matches + timelines using BFS snowballing across participants.

    - Respects RiotClient's TokenBucketLimiter and Retry-After handling.
    - Deduplicates match_ids already stored in the database.
    - Backfills missing timelines for existing matches if encountered.
    - Skips remakes (< min_duration_sec) so training data stays clean.
    """
    region = routing.normalize_region(region)
    client = client or get_riot_client()
    report = CrawlReport(region=region, target_matches=target_matches)

    def emit(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    queue: deque[str] = deque()
    seen_puuids: set[str] = set()

    def enqueue_puuid(p: str) -> None:
        if p and p not in seen_puuids:
            seen_puuids.add(p)
            queue.append(p)

    for p in seed_puuids or []:
        enqueue_puuid(p)
    if seed_riot_ids:
        for p in _seed_puuids_from_riot_ids(client, region, seed_riot_ids):
            enqueue_puuid(p)
    if not queue:
        emit(f"Fetching seed players from {region.upper()} {tier} league...")
        for p in _seed_puuids_from_league(client, region, tier=tier):
            enqueue_puuid(p)
    if not queue:
        # Fallback: seed from players already in DB for this region
        db_puuids = db.session.scalars(select(Player.puuid).where(Player.region == region).limit(50)).all()
        for p in db_puuids:
            enqueue_puuid(p)

    if not queue:
        emit("No seed players found. Provide --seed 'GameName#TAG' or ensure RIOT_API_KEY is valid.")
        return report

    emit(f"Starting crawl: region={region}, target={target_matches}, queue={queue_id}, seeds={len(queue)}")

    while queue and report.saved_matches < target_matches:
        puuid = queue.popleft()
        report.players_visited += 1

        try:
            match_ids = client.get_match_ids(region, puuid, start=0, count=matches_per_player, queue=queue_id)
        except RiotAuthError:
            raise
        except RiotApiError as exc:
            report.errors += 1
            emit(f"Skipping player {puuid[:10]}... ({exc.code})")
            continue

        if not match_ids:
            continue

        existing_matches = set(
            db.session.scalars(select(Match.match_id).where(Match.match_id.in_(match_ids))).all()
        )
        existing_timelines = set(
            db.session.scalars(select(MatchTimeline.match_id).where(MatchTimeline.match_id.in_(match_ids))).all()
        )

        for match_id in match_ids:
            if report.saved_matches >= target_matches:
                break

            if match_id in existing_matches and match_id in existing_timelines:
                report.skipped_existing += 1
                continue

            try:
                if match_id not in existing_matches:
                    match_data = client.get_match(region, match_id)
                    if not match_data:
                        continue
                    info = match_data.get("info") or {}
                    duration = int(info.get("gameDuration", 0))
                    if "gameEndTimestamp" not in info and duration > 10_000:
                        duration //= 1000
                    participants = info.get("participants") or []
                    if duration < min_duration_sec or len(participants) != 10:
                        continue  # skip remakes / non-standard games

                    timeline_data = client.get_timeline(region, match_id)
                    if not timeline_data:
                        continue

                    save_match(match_data, region, commit=False)
                    for part in participants:
                        _upsert_lightweight_player(part["puuid"], region, part)
                        enqueue_puuid(part["puuid"])
                    db.session.flush()
                    save_timeline(match_id, timeline_data, commit=False)
                    db.session.commit()

                    report.saved_matches += 1
                    report.saved_timelines += 1
                    report.saved_match_ids.append(match_id)
                    emit(
                        f"[{report.saved_matches}/{target_matches}] Saved {match_id} "
                        f"({duration // 60}m{duration % 60:02d}s, queue={len(queue)})"
                    )
                else:
                    # Match exists, backfill missing timeline only
                    timeline_data = client.get_timeline(region, match_id)
                    if timeline_data:
                        save_timeline(match_id, timeline_data, commit=True)
                        report.saved_timelines += 1
                        emit(f"[backfill] Saved timeline for existing match {match_id}")
            except RiotAuthError:
                db.session.rollback()
                raise
            except RiotApiError as exc:
                db.session.rollback()
                report.errors += 1
                emit(f"Error on {match_id}: {exc.code} ({exc})")
            except Exception as exc:
                db.session.rollback()
                report.errors += 1
                log.exception("Unexpected error saving %s", match_id)
                emit(f"Unexpected error on {match_id}: {exc}")

    # Also ensure snowballing works even if existing matches had participants
    if report.saved_matches == 0 and report.skipped_existing > 0:
        emit(
            f"Finished: 0 new matches saved ({report.skipped_existing} already in DB). "
            "Try increasing --per-player or using another --tier / --seed."
        )
    else:
        emit(
            f"Crawl complete: saved_matches={report.saved_matches}, saved_timelines={report.saved_timelines}, "
            f"skipped={report.skipped_existing}, players_visited={report.players_visited}, errors={report.errors}"
        )
    return report
