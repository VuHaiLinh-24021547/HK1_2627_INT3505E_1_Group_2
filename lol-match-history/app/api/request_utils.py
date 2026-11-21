"""Request parsing helpers: JSON bodies and allowlisted query strings."""
from __future__ import annotations

import json
from typing import TypeVar

from flask import request
from pydantic import BaseModel, ValidationError

from .errors import ApiError, pydantic_errors

M = TypeVar("M", bound=BaseModel)


def json_body(model: type[M], allow_empty: bool = True) -> M:
    raw = request.get_data(cache=True)
    if raw.strip() and not request.is_json:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Request body must be sent as Content-Type: application/json.")
    if not raw.strip():
        if not allow_empty:
            raise ApiError(400, "MALFORMED_JSON", "A JSON request body is required.")
        data = {}
    else:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "MALFORMED_JSON", "Request body is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ApiError(400, "MALFORMED_JSON", "Request body must be a JSON object.")
    return model.model_validate(data)  # ValidationError -> 422 via global handler


def query_params(model: type[M]) -> M:
    """Validate query parameters against an allowlist model; failures are 400 (invalid query syntax)."""
    data = {}
    for key in request.args:
        values = request.args.getlist(key)
        if len(values) > 1:
            raise ApiError(400, "DUPLICATE_QUERY_PARAMETER", f"Query parameter '{key}' was supplied more than once.")
        data[key] = values[0]
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        errors = pydantic_errors(exc)
        unknown = [e["field"] for e in errors if e["code"] == "extra_forbidden"]
        if unknown:
            allowed = ", ".join(model.model_fields)
            raise ApiError(
                400,
                "UNSUPPORTED_QUERY_PARAMETER",
                f"Unsupported query parameter(s): {', '.join(unknown)}. Allowed: {allowed}.",
                errors=errors,
            ) from None
        raise ApiError(400, "INVALID_QUERY_PARAMETER", "One or more query parameters are invalid.", errors=errors) from None
