"""Match synchronisation: cooldown, job dispatch, deduplicated Match-V5 import."""
from __future__ import annotations

import logging
import threading

from flask import current_app
from sqlalchemy import select

from ..api.errors import ApiError
from ..extensions import db
from ..models import Match, Player
from . import jobs
from .match_parser import save_match
from .player_service import apply_summoner_and_league, cooldown_remaining
from .riot_client import RiotApiError, RiotClient, get_riot_client
from .timeutil import iso, utcnow

log = logging.getLogger(__name__)


def request_sync(puuid: str, region: str | None, count: int, queue_id: int | None, requested_by: str) -> dict:
    """Validate cooldown atomically, then create and dispatch a sync job."""
    player = db.session.scalars(select(Player).where(Player.puuid == puuid).with_for_update()).first()
    if player is None:
        db.session.rollback()
        raise ApiError(404, "PLAYER_NOT_FOUND", f"Player '{puuid}' does not exist. Look the player up first.")
    if region and region != player.region:
        db.session.rollback()
        raise ApiError(
            422,
            "REGION_MISMATCH",
            f"Player belongs to region '{player.region}', not '{region}'.",
            errors=[{"field": "region", "code": "mismatch", "message": f"Expected '{player.region}'."}],
        )
    remaining = cooldown_remaining(player)
    if remaining > 0:
        db.session.rollback()
        raise ApiError(
            429,
            "SYNC_COOLDOWN_ACTIVE",
            f"Vui lòng đợi thêm {remaining} giây trước khi đồng bộ lại.",
            headers={"Retry-After": str(remaining)},
            retryAfterSeconds=remaining,
        )
    player.last_synced_at = utcnow()
    db.session.commit()  # releases the row lock; cooldown is now active

    job = jobs.create_job(
        puuid=puuid, region=player.region, count=count, queueId=queue_id, createdBy=requested_by
    )
    dispatch(job["jobId"])
    return jobs.get_job(job["jobId"]) or job


def dispatch(job_id: str) -> None:
    mode = current_app.config["SYNC_MODE"]
    if mode == "inline":
        run_sync_job(job_id)
    elif mode == "thread":
        app = current_app._get_current_object()

        def _target():
            with app.app_context():
                run_sync_job(job_id)

        threading.Thread(target=_target, name=f"sync-{job_id[:8]}", daemon=True).start()
    else:
        from ..extensions import get_queue

        get_queue().enqueue("app.workers.sync_worker.run_job", job_id, job_id=job_id, job_timeout=600)


def run_sync_job(job_id: str, client: RiotClient | None = None) -> dict | None:
    job = jobs.update_job(job_id, status="started", startedAt=iso(utcnow()))
    if job is None:
        return None
    try:
        result = sync_player_matches(job["puuid"], job["region"], job["count"], job.get("queueId"), client)
    except RiotApiError as exc:
        db.session.rollback()
        log.warning("Sync job %s failed: %s", job_id, exc.code)
        return jobs.update_job(
            job_id, status="failed", finishedAt=iso(utcnow()), error={"code": exc.code, "message": str(exc)}
        )
    except Exception:  # pragma: no cover - defensive
        db.session.rollback()
        log.exception("Sync job %s crashed", job_id)
        return jobs.update_job(
            job_id, status="failed", finishedAt=iso(utcnow()), error={"code": "INTERNAL_ERROR", "message": "Job crashed"}
        )
    return jobs.update_job(job_id, status="finished", finishedAt=iso(utcnow()), result=result)


def sync_player_matches(
    puuid: str, region: str, count: int = 20, queue_id: int | None = None, client: RiotClient | None = None
) -> dict:
    client = client or get_riot_client()

    player = db.session.get(Player, puuid)
    if player is not None:
        apply_summoner_and_league(
            player, client.get_summoner_by_puuid(region, puuid), client.get_league_entries(region, puuid)
        )
        db.session.commit()

    ids = client.get_match_ids(region, puuid, start=0, count=count, queue=queue_id)
    existing = set(db.session.scalars(select(Match.match_id).where(Match.match_id.in_(ids))).all()) if ids else set()
    new_ids = [mid for mid in ids if mid not in existing]

    imported, missing = [], []
    for match_id in new_ids:
        data = client.get_match(region, match_id)
        if not data:
            missing.append(match_id)
            continue
        save_match(data, region)
        imported.append(match_id)

    return {
        "requested": len(ids),
        "newMatches": len(imported),
        "skippedExisting": len(existing),
        "notFound": len(missing),
        "importedMatchIds": imported,
    }
