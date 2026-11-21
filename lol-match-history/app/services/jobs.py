"""Sync job storage in Redis."""
from __future__ import annotations

import json
import uuid

from flask import current_app

from ..extensions import redis_client
from .timeutil import iso, utcnow


def _key(job_id: str) -> str:
    return f"sync:job:{job_id}"


def create_job(**fields) -> dict:
    job = {
        "jobId": uuid.uuid4().hex,
        "status": "queued",
        "createdAt": iso(utcnow()),
        "startedAt": None,
        "finishedAt": None,
        "result": None,
        "error": None,
        **fields,
    }
    save_job(job)
    return job


def save_job(job: dict) -> None:
    redis_client.set(_key(job["jobId"]), json.dumps(job), ex=current_app.config["SYNC_JOB_TTL_SEC"])


def get_job(job_id: str) -> dict | None:
    raw = redis_client.get(_key(job_id))
    return json.loads(raw) if raw else None


def update_job(job_id: str, **fields) -> dict | None:
    job = get_job(job_id)
    if job is None:
        return None
    job.update(fields)
    save_job(job)
    return job


def public_job(job: dict) -> dict:
    """Strip internal fields before returning a job to API clients."""
    return {k: v for k, v in job.items() if k != "createdBy"}
