from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL, generic JSON elsewhere (SQLite for tests / devlite)
JSONType = JSON().with_variant(JSONB(), "postgresql")

from .player import Player  # noqa: E402
from .match import Match, MatchParticipant, MatchTimeline  # noqa: E402
from .static_asset import StaticAsset  # noqa: E402

__all__ = ["JSONType", "Player", "Match", "MatchParticipant", "MatchTimeline", "StaticAsset"]
