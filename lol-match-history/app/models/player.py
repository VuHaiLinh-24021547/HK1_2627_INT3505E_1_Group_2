from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class Player(db.Model):
    __tablename__ = "players"

    puuid: Mapped[str] = mapped_column(String(78), primary_key=True)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    game_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_line: Mapped[str] = mapped_column(String(16), nullable=False)
    profile_icon_id: Mapped[int | None] = mapped_column(Integer)
    summoner_level: Mapped[int | None] = mapped_column(Integer)
    solo_tier: Mapped[str | None] = mapped_column(String(16))
    solo_rank: Mapped[str | None] = mapped_column(String(8))
    solo_lp: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    solo_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    solo_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=func.now(), onupdate=func.now()
    )


Index(
    "idx_players_riotid",
    Player.region,
    func.lower(Player.game_name),
    func.lower(Player.tag_line),
)
