"""Centralized RFC 9457 (Problem Details) error handling."""
from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from flask import Response, current_app, g, json, request
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger("app.errors")

PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        headers: dict[str, str] | None = None,
        errors: list[dict[str, Any]] | None = None,
        **extensions: Any,
    ):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = headers or {}
        self.errors = errors
        self.extensions = extensions


def _type_uri(code: str) -> str:
    base = current_app.config.get("PROBLEM_TYPE_BASE", "about:blank/")
    return base + code.lower().replace("_", "-")


def problem_response(
    status: int,
    code: str,
    detail: str,
    headers: dict[str, str] | None = None,
    errors: list[dict[str, Any]] | None = None,
    **extensions: Any,
) -> Response:
    try:
        title = HTTPStatus(status).phrase
    except ValueError:
        title = "Error"
    body: dict[str, Any] = {
        "type": _type_uri(code),
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.path,
        "traceId": getattr(g, "trace_id", None),
        "code": code,
    }
    if errors:
        body["errors"] = errors
    body.update({k: v for k, v in extensions.items() if v is not None})
    resp = Response(json.dumps(body), status=status, mimetype=PROBLEM_JSON)
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ())) or None
        out.append({"field": loc, "code": err.get("type"), "message": err.get("msg")})
    return out


_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "UNPROCESSABLE_ENTITY",
    429: "TOO_MANY_REQUESTS",
}


def register_error_handlers(app) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return problem_response(exc.status, exc.code, exc.detail, exc.headers, exc.errors, **exc.extensions)

    @app.errorhandler(ValidationError)
    def _validation_error(exc: ValidationError):
        return problem_response(
            422, "VALIDATION_FAILED", "One or more request fields failed validation.", errors=pydantic_errors(exc)
        )

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        status = exc.code or 500
        headers = {}
        valid_methods = getattr(exc, "valid_methods", None)
        if valid_methods:
            headers["Allow"] = ", ".join(valid_methods)
        return problem_response(status, _HTTP_CODES.get(status, "HTTP_ERROR"), exc.description or "", headers)

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):
        log.exception("Unhandled error trace=%s path=%s", g.get("trace_id"), request.path)
        return problem_response(500, "INTERNAL_ERROR", "An unexpected error occurred. Quote the traceId to support.")
