from flask import Blueprint

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def register_blueprints(app) -> None:
    from . import docs, oauth, players, sync_jobs  # noqa: F401

    app.register_blueprint(api_v1)
    docs.register_swagger_ui(app)
