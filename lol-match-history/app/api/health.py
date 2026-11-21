from flask import current_app, jsonify
from sqlalchemy import text

from ..extensions import db, redis_client
from ..services.timeutil import iso, utcnow
from . import api_v1


@api_v1.get("/health")
def health():
    database = redis = "up"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - requires a broken DB
        db.session.rollback()
        database = "down"
    try:
        redis_client.ping()
    except Exception:  # pragma: no cover - requires a broken Redis
        redis = "down"
    ok = database == "up" and redis == "up"
    body = {
        "status": "ok" if ok else "degraded",
        "database": database,
        "redis": redis,
        "version": current_app.config["API_VERSION"],
        "syncMode": current_app.config["SYNC_MODE"],
        "riotApiKeyConfigured": bool(current_app.config.get("RIOT_API_KEY")),
        "timestamp": iso(utcnow()),
    }
    return jsonify(body), 200 if ok else 503
