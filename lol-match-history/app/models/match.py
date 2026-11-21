from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from . import JSONType


class Match(db.Model):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    queue_id: Mapped[int] = mapped_column(Integer, nullable=False)
    game_creation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    game_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_version: Mapped[str] = mapped_column(String(16), nullable=False)
    winning_team_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    teams_jsonb: Mapped[list] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=func.now()
    )


class MatchParticipant(db.Model):
    __tablename__ = "match_participants"

    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    puuid: Mapped[str] = mapped_column(String(78), primary_key=True)
    riot_id_name: Mapped[str | None] = mapped_column(String(64))
    riot_id_tagline: Mapped[str | None] = mapped_column(String(16))
    team_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    team_position: Mapped[str | None] = mapped_column(String(16))
    champion_id: Mapped[int] = mapped_column(Integer, nullable=False)
    win: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kills: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    deaths: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    assists: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    cs_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gold_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    damage_to_champs: Mapped[int] = mapped_column(Integer, nullable=False)
    vision_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    items_jsonb: Mapped[list] = mapped_column(JSONType, nullable=False)
    runes_jsonb: Mapped[dict] = mapped_column(JSONType, nullable=False)
    spells_jsonb: Mapped[list] = mapped_column(JSONType, nullable=False)
    game_creation: Mapped[int] = mapped_column(BigInteger, nullable=False)


Index("idx_mp_puuid_recent", MatchParticipant.puuid, MatchParticipant.game_creation.desc())
Index("idx_mp_puuid_champ", MatchParticipant.puuid, MatchParticipant.champion_id)
# Keyset pagination support: (game_creation, match_id) tie-breaker ordering
Index(
    "idx_mp_puuid_gc_match",
    MatchParticipant.puuid,
    MatchParticipant.game_creation.desc(),
    MatchParticipant.match_id.desc(),
)


class MatchTimeline(db.Model):
    __tablename__ = "match_timelines"

    match_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    interval_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=60000, server_default="60000")
    frames_jsonb: Mapped[list] = mapped_column(JSONType, nullable=False)
    events_jsonb: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=func.now()
    )
