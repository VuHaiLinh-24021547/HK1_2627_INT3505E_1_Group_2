from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from . import JSONType


class StaticAsset(db.Model):
    __tablename__ = "static_assets"

    patch_version: Mapped[str] = mapped_column(String(16), primary_key=True)
    lang: Mapped[str] = mapped_column(String(10), primary_key=True, default="vi_VN", server_default="vi_VN")
    champions_jsonb: Mapped[dict] = mapped_column(JSONType, nullable=False)
    items_jsonb: Mapped[dict] = mapped_column(JSONType, nullable=False)
    runes_jsonb: Mapped[list] = mapped_column(JSONType, nullable=False)
    spells_jsonb: Mapped[dict] = mapped_column(JSONType, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=func.now()
    )
