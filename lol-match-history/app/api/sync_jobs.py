from flask import g, jsonify, url_for

from ..auth.jwt_auth import require_scopes
from ..services import jobs, sync_service
from . import api_v1
from .errors import ApiError
from .idempotency import idempotent
from .request_utils import json_body
from .schemas import SyncJobRequest


@api_v1.post("/players/<puuid>/sync-jobs")
@require_scopes("players:sync")
@idempotent()
def create_sync_job(puuid):
    req = json_body(SyncJobRequest)
    job = sync_service.request_sync(puuid, req.region, req.count, req.queueId, requested_by=g.auth["sub"])
    resp = jsonify(jobs.public_job(job))
    resp.status_code = 202
    resp.headers["Location"] = url_for("api_v1.get_sync_job", job_id=job["jobId"])
    return resp


@api_v1.get("/sync-jobs/<job_id>")
@require_scopes("players:sync")
def get_sync_job(job_id):
    job = jobs.get_job(job_id)
    # Object-level authorization: jobs are only visible to the client that created them.
    if job is None or job.get("createdBy") != g.auth["sub"]:
        raise ApiError(404, "SYNC_JOB_NOT_FOUND", f"Sync job '{job_id}' was not found.")
    return jsonify(jobs.public_job(job)), 200
