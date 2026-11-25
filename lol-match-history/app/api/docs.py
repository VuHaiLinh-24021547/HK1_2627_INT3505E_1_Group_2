"""OpenAPI specification and interactive Swagger UI endpoints (via flask-swagger-ui)."""
from __future__ import annotations

from flask import redirect, send_file
from flask_swagger_ui import get_swaggerui_blueprint

from ..config import BASE_DIR
from . import api_v1
from .errors import ApiError

OPENAPI_PATH = BASE_DIR / "docs" / "openapi.yaml"
SWAGGER_URL = "/api/v1/docs"
API_URL = "/api/v1/openapi.yaml"


@api_v1.get("/openapi.yaml")
def openapi_spec():
    if not OPENAPI_PATH.exists():
        raise ApiError(404, "SPEC_NOT_FOUND", "openapi.yaml was not found on the server.")
    resp = send_file(OPENAPI_PATH, mimetype="application/yaml")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def register_swagger_ui(app) -> None:
    swaggerui_bp = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={
            "app_name": "RiftReview API v1",
            "deepLinking": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True,
        },
    )
    app.register_blueprint(swaggerui_bp)

    @app.get("/docs")
    def _root_docs_redirect():
        return redirect(f"{SWAGGER_URL}/", code=302)
