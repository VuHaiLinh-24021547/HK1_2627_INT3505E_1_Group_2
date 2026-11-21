"""Riot platform vs. regional routing (spec section 3.1)."""
from __future__ import annotations

from dataclasses import dataclass

# region -> (account-v1 cluster, match-v5 cluster)
_ROUTES: dict[str, tuple[str, str]] = {
    "vn2": ("asia", "sea"),
    "sg2": ("asia", "sea"),
    "tw2": ("asia", "sea"),
    "oc1": ("asia", "sea"),
    "kr": ("asia", "asia"),
    "jp1": ("asia", "asia"),
    "euw1": ("europe", "europe"),
    "eun1": ("europe", "europe"),
    "tr1": ("europe", "europe"),
    "ru": ("europe", "europe"),
    "na1": ("americas", "americas"),
    "br1": ("americas", "americas"),
    "la1": ("americas", "americas"),
    "la2": ("americas", "americas"),
}

SUPPORTED_REGIONS = tuple(_ROUTES)


@dataclass(frozen=True)
class RegionRoute:
    region: str
    platform_host: str
    account_host: str
    match_host: str


def normalize_region(region: str) -> str:
    if not isinstance(region, str):
        raise ValueError("Region must be a string")
    value = region.strip().lower()
    if value not in _ROUTES:
        raise ValueError(f"Unsupported region '{region}'. Supported: {', '.join(SUPPORTED_REGIONS)}")
    return value


def resolve(region: str) -> RegionRoute:
    value = normalize_region(region)
    account, match = _ROUTES[value]
    return RegionRoute(
        region=value,
        platform_host=f"{value}.api.riotgames.com",
        account_host=f"{account}.api.riotgames.com",
        match_host=f"{match}.api.riotgames.com",
    )


def region_from_match_id(match_id: str) -> str:
    """'VN2_492817261' -> 'vn2'. Raises ValueError for unknown prefixes."""
    if not match_id or "_" not in match_id:
        raise ValueError(f"Invalid match id '{match_id}'")
    return normalize_region(match_id.split("_", 1)[0])
