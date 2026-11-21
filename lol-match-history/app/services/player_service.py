"""Player profile lookup: Redis cache -> PostgreSQL -> Riot Account/Summoner/League APIs."""
from __future__ import annotations

import math

from flask import current_app
from sqlalchemy import func, select

from ..api.errors import ApiError
from ..extensions import db, redis_client
from ..models import Player
from . import routing
from .riot_client import RiotClient, get_riot_client
from .timeutil import as_utc, iso, utcnow


def _cache_key(region: str, game_name: str, tag_line: str) -> str:
    return f"player:riotid:{region}:{game_name.lower()}:{tag_line.lower()}"


def validate_riot_id(game_name: str, tag_line: str) -> tuple[str, str]:
    game_name = (game_name or "").strip()
    tag_line = (tag_line or "").strip().lstrip("#")
    errors = []
    if not 1 <= len(game_name) <= 64:
        errors.append({"field": "gameName", "code": "length", "message": "gameName must be 1-64 characters."})
    if not 1 <= len(tag_line) <= 16:
        errors.append({"field": "tagLine", "code": "length", "message": "tagLine must be 1-16 characters."})
    if errors:
        raise ApiError(400, "INVALID_RIOT_ID", "Riot ID must look like gameName#tagLine.", errors=errors)
    return game_name, tag_line


def parse_region(region: str) -> str:
    try:
        return routing.normalize_region(region)
    except ValueError as exc:
        raise ApiError(400, "INVALID_REGION", str(exc), supportedRegions=list(routing.SUPPORTED_REGIONS)) from None


def apply_summoner_and_league(player: Player, summoner: dict | None, entries: list | None) -> None:
    if summoner:
        player.profile_icon_id = summoner.get("profileIconId")
        player.summoner_level = summoner.get("summonerLevel")
    solo = next((e for e in (entries or []) if e.get("queueType") == "RANKED_SOLO_5x5"), None)
    if solo:
        player.solo_tier = solo.get("tier")
        player.solo_rank = solo.get("rank")
        player.solo_lp = solo.get("leaguePoints", 0)
        player.solo_wins = solo.get("wins", 0)
        player.solo_losses = solo.get("losses", 0)
    elif entries is not None:
        player.solo_tier = player.solo_rank = None
        player.solo_lp = player.solo_wins = player.solo_losses = 0
    player.updated_at = utcnow()


def get_or_fetch_player(region: str, game_name: str, tag_line: str, client: RiotClient | None = None) -> Player:
    region = parse_region(region)
    game_name, tag_line = validate_riot_id(game_name, tag_line)
    key = _cache_key(region, game_name, tag_line)

    puuid = redis_client.get(key)
    if puuid:
        player = db.session.get(Player, puuid)
        if player is not None:
            return player

    player = db.session.scalars(
        select(Player).where(
            Player.region == region,
            func.lower(Player.game_name) == game_name.lower(),
            func.lower(Player.tag_line) == tag_line.lower(),
        )
    ).first()

    if player is None:
        client = client or get_riot_client()
        account = client.get_account_by_riot_id(region, game_name, tag_line)
        if not account:
            raise ApiError(404, "PLAYER_NOT_FOUND", f"Riot ID '{game_name}#{tag_line}' was not found in {region}.")
        puuid = account["puuid"]
        player = db.session.get(Player, puuid)
        if player is None:
            player = Player(puuid=puuid, region=region)
            db.session.add(player)
        player.region = region
        player.game_name = account.get("gameName") or game_name
        player.tag_line = account.get("tagLine") or tag_line
        apply_summoner_and_league(
            player, client.get_summoner_by_puuid(region, puuid), client.get_league_entries(region, puuid)
        )
        db.session.commit()

    redis_client.set(key, player.puuid, ex=current_app.config["PROFILE_CACHE_TTL_SEC"])
    return player


def cooldown_remaining(player: Player) -> int:
    last = as_utc(player.last_synced_at)
    if last is None:
        return 0
    cooldown = current_app.config["SYNC_COOLDOWN_SEC"]
    remaining = cooldown - (utcnow() - last).total_seconds()
    return max(0, int(math.ceil(remaining)))


def serialize_player(player: Player) -> dict:
    remaining = cooldown_remaining(player)
    games = (player.solo_wins or 0) + (player.solo_losses or 0)
    return {
        "puuid": player.puuid,
        "region": player.region,
        "gameName": player.game_name,
        "tagLine": player.tag_line,
        "riotId": f"{player.game_name}#{player.tag_line}",
        "profileIconId": player.profile_icon_id,
        "summonerLevel": player.summoner_level,
        "soloTier": player.solo_tier,
        "soloRank": player.solo_rank,
        "soloLp": player.solo_lp,
        "soloWins": player.solo_wins,
        "soloLosses": player.solo_losses,
        "soloWinRate": round(player.solo_wins * 100 / games, 1) if games else None,
        "lastSyncedAt": iso(player.last_synced_at),
        "updatedAt": iso(player.updated_at),
        "canSync": remaining == 0,
        "cooldownRemainingSec": remaining,
    }
