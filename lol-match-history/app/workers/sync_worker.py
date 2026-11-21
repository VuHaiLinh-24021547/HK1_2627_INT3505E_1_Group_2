"""RQ background worker entrypoint for match sync jobs."""
from __future__ import annotations

import os


def run_job(job_id: str) -> dict | None:
    """RQ task callable: runs inside a fresh Flask application context."""
    from app import create_app
    from app.services.sync_service import run_sync_job

    app = create_app(os.getenv("APP_CONFIG", "dev"))
    with app.app_context():
        return run_sync_job(job_id)


def main() -> None:  # pragma: no cover - CLI entrypoint for RQ worker
    import redis
    from rq import Worker

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    conn = redis.Redis.from_url(redis_url)
    worker = Worker(["sync"], connection=conn)
    worker.work()


if __name__ == "__main__":  # pragma: no cover
    main()
