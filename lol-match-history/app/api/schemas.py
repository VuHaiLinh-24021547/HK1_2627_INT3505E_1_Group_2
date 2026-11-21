"""Request DTOs (Pydantic v2, unknown fields rejected)."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MATCH_ID_RE = re.compile(r"^[A-Za-z0-9]{2,5}_\d{1,20}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SyncJobRequest(StrictModel):
    region: str | None = Field(default=None, max_length=10)
    count: int = Field(default=20, ge=1, le=100, strict=True)
    queueId: int | None = Field(default=None, ge=0, strict=True)

    @field_validator("region")
    @classmethod
    def _region(cls, v):
        if v is None:
            return v
        from ..services import routing

        return routing.normalize_region(v)


class MatchListQuery(StrictModel):
    cursor: str | None = Field(default=None, max_length=512)
    limit: int = Field(default=20, ge=1, le=50)
    queueId: int | None = Field(default=None, ge=0)
    championId: int | None = Field(default=None, ge=1)
    sort: Literal["-gameCreation"] = "-gameCreation"


class ReviewQuery(StrictModel):
    region: str | None = Field(default=None, max_length=10)
    focusPuuid: str | None = Field(default=None, max_length=78)


class CatalogQuery(StrictModel):
    lang: str = Field(default="vi_VN", pattern=r"^[a-z]{2}_[A-Z]{2}$")


class TokenRequest(StrictModel):
    grant_type: str
    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None


class RevocationRequest(StrictModel):
    token: str
    token_type_hint: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
