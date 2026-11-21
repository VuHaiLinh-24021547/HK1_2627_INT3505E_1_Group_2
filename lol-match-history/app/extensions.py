"""Flask extensions shared across the application."""
from __future__ import annotations

from flask import current_app
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.local import LocalProxy


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()


def init_redis(app) -> None:
    if app.config.get("USE_FAKEREDIS"):
        import fakeredis

        client = fakeredis.FakeRedis(decode_responses=True)
    else:
        import redis

        client = redis.Redis.from_url(app.config["REDIS_URL"], decode_responses=True)
    app.extensions["redis"] = client


def _get_redis():
    return current_app.extensions["redis"]


redis_client = LocalProxy(_get_redis)


def get_queue():
    """RQ queue (only used when SYNC_MODE == 'rq'). RQ needs a bytes connection."""
    import redis
    from rq import Queue

    conn = redis.Redis.from_url(current_app.config["REDIS_URL"])
    return Queue("sync", connection=conn)
