from __future__ import annotations

import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, g

from .config import Config


def _generate_rsa_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json.sort_keys = False
    app.json.ensure_ascii = False
    if config_name == "test":
        app.config["TESTING"] = True

    priv, pub = _generate_rsa_pair()
    app.config["JWT_PRIVATE_KEY_PEM"] = priv
    app.config["JWT_PUBLIC_KEY_PEM"] = pub

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
    from .api.mock_data import reset_mock_store

    reset_mock_store()
    register_blueprints(app)
    register_error_handlers(app)

    return app
