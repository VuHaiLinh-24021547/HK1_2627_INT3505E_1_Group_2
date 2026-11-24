"""Mock/seed endpoint: GET /api/v1/players/<puuid>/matches."""
from __future__ import annotations

from typing import Literal

from flask import current_app, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import api_v1
from .auth import require_scopes
from .errors import ApiError, pydantic_errors
from .mock_data import MATCHES, PLAYERS, decode_cursor, encode_cursor


class MatchListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cursor: str | None = Field(default=None, max_length=512)
    limit: int = Field(default=20, ge=1, le=50)
    queueId: int | None = Field(default=None, ge=0)
    championId: int | None = Field(default=None, ge=1)
    sort: Literal["-gameCreation"] = "-gameCreation"


@api_v1.get("/players/<puuid>/matches")
@require_scopes("matches:read")
def list_player_matches(puuid: str):
    if puuid not in PLAYERS:
        raise ApiError(404, "PLAYER_NOT_FOUND", f"Player '{puuid}' does not exist.")

    args = {}
    for key in request.args:
        vals = request.args.getlist(key)
        if len(vals) > 1:
            raise ApiError(400, "DUPLICATE_QUERY_PARAMETER", f"Query parameter '{key}' was supplied more than once.")
        args[key] = vals[0]
    try:
        q = MatchListQuery.model_validate(args)
    except ValidationError as exc:
        errs = pydantic_errors(exc)
        unknown = [e["field"] for e in errs if e["code"] == "extra_forbidden"]
        if unknown:
            raise ApiError(
                400,
                "UNSUPPORTED_QUERY_PARAMETER",
                f"Unsupported query parameter(s): {', '.join(unknown)}.",
                errors=errs,
            ) from None
        raise ApiError(400, "INVALID_QUERY_PARAMETER", "One or more query parameters are invalid.", errors=errs) from None

    filtered = [
        m
        for m in MATCHES
        if (q.queueId is None or m["queueId"] == q.queueId)
        and (q.championId is None or m["player"]["championId"] == q.championId)
    ]

    games = len(filtered)
    wins = sum(1 for m in filtered if m["player"]["win"])
    k = sum(m["player"]["kills"] for m in filtered)
    d = sum(m["player"]["deaths"] for m in filtered)
    a = sum(m["player"]["assists"] for m in filtered)
    cs = sum(m["player"]["csTotal"] for m in filtered)
    dur = sum(m["gameDuration"] for m in filtered)
    summary = {
        "games": games,
        "wins": wins,
        "losses": games - wins,
        "winRate": round(wins * 100 / games, 1) if games else 0.0,
        "avgKda": round((k + a) / max(d, 1), 2) if games else 0.0,
        "avgCsPerMin": round(cs / (dur / 60), 2) if dur else 0.0,
    }

    secret = current_app.config["SECRET_KEY"]
    page_items = filtered
    if q.cursor:
        try:
            gc, mid = decode_cursor(q.cursor, secret)
        except ValueError as exc:
            raise ApiError(400, "INVALID_CURSOR", f"The cursor is invalid or has been tampered with ({exc}).") from None
        page_items = [
            m
            for m in filtered
            if m["gameCreation"] < gc or (m["gameCreation"] == gc and m["matchId"] < mid)
        ]

    has_more = len(page_items) > q.limit
    page_items = page_items[: q.limit]
    next_cursor = (
        encode_cursor(page_items[-1]["gameCreation"], page_items[-1]["matchId"], secret)
        if has_more and page_items
        else None
    )

    return (
        jsonify(
            {
                "data": page_items,
                "summary": summary,
                "pagination": {"limit": q.limit, "nextCursor": next_cursor, "hasMore": has_more},
            }
        ),
        200,
    )
