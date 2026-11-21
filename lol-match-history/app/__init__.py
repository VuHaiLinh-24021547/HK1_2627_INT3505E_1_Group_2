"""Application factory."""
from __future__ import annotations

import logging
import uuid

from flask import Flask, g

from .config import INSTANCE_DIR, get_config
from .extensions import db, init_redis, migrate


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.from_object(get_config(config_name))
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    from . import models  # noqa: F401  (register models for migrations)

    migrate.init_app(app, db)
    init_redis(app)

    from .auth.keys import init_keys

    init_keys(app)

    @app.before_request
    def _assign_trace_id():
        g.trace_id = uuid.uuid4().hex

    @app.after_request
    def _add_trace_header(response):
        trace_id = getattr(g, "trace_id", None)
        if trace_id:
            response.headers["X-Trace-Id"] = trace_id
        return response

    from .api import register_blueprints
    from .api.errors import register_error_handlers

    register_blueprints(app)
    register_error_handlers(app)

    from .cli import register_cli

    register_cli(app)

    @app.teardown_appcontext
    def _shutdown_session(exc=None):  # pragma: no cover - flask-sqlalchemy handles it too
        if exc is not None:
            db.session.rollback()

    return app
