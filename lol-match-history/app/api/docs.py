"""OpenAPI specification and interactive Swagger UI endpoints."""
from __future__ import annotations

from flask import Response, redirect, send_file, url_for

from ..config import BASE_DIR
from . import api_v1
from .errors import ApiError

OPENAPI_PATH = BASE_DIR / "openapi.yaml"

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RiftReview API v1 — Swagger UI</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    body { margin: 0; background: #fafafa; }
    .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({
        url: "__SPEC_URL__",
        dom_id: "#swagger-ui",
        deepLinking: true,
        persistAuthorization: true,
        displayRequestDuration: true,
        tryItOutEnabled: true
      });
    };
  </script>
</body>
</html>
"""


@api_v1.get("/openapi.yaml")
def openapi_spec():
    if not OPENAPI_PATH.exists():
        raise ApiError(404, "SPEC_NOT_FOUND", "openapi.yaml was not found on the server.")
    resp = send_file(OPENAPI_PATH, mimetype="application/yaml")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@api_v1.get("/docs")
def swagger_ui():
    spec_url = url_for("api_v1.openapi_spec")
    return Response(_SWAGGER_HTML.replace("__SPEC_URL__", spec_url), status=200, mimetype="text/html")


def register_docs_redirect(app) -> None:
    @app.get("/docs")
    def _root_docs_redirect():
        return redirect(url_for("api_v1.swagger_ui"), code=302)
