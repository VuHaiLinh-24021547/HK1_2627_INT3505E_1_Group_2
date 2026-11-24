from flask import Blueprint

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def register_blueprints(app) -> None:
    from . import docs, health, matches, oauth, players, static_data, sync_jobs  # noqa: F401

    app.register_blueprint(api_v1)
    docs.register_docs_redirect(app)
