"""Data Dragon static data: versions, champions, items, runes, summoner spells."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import httpx
from flask import current_app
from sqlalchemy import select

from ..extensions import db, redis_client
from ..models import StaticAsset

log = logging.getLogger(__name__)

DDRAGON = "https://ddragon.leagueoflegends.com"
DEFAULT_LANGS = ("vi_VN", "en_US")
FILES = {
    "champions": "champion.json",
    "items": "item.json",
    "runes": "runesReforged.json",
    "spells": "summoner.json",
}
PATCH_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")
LANG_RE = re.compile(r"^[a-z]{2}_[A-Z]{2}$")


class DDragonError(Exception):
    pass


def _base() -> str:
    try:
        return current_app.config.get("DDRAGON_BASE_URL", DDRAGON)
    except RuntimeError:
        return DDRAGON


# ---------------------------------------------------------------- parsing
def parse_latest_version(versions: list[str]) -> str:
    if not versions or not isinstance(versions, list):
        raise DDragonError("versions.json is empty or malformed")
    return str(versions[0])


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", version))


def build_champion_map(champions_data: dict, version: str, base: str = DDRAGON) -> dict[str, dict]:
    """Map numeric championId (the ``key`` field) -> name + image URL."""
    out: dict[str, dict] = {}
    for champ in champions_data.values():
        key = str(champ["key"])
        out[key] = {
            "id": int(key),
            "alias": champ["id"],
            "name": champ["name"],
            "title": champ.get("title"),
            "imageUrl": f"{base}/cdn/{version}/img/champion/{champ['image']['full']}",
        }
    return out


def build_item_map(items_data: dict, version: str, base: str = DDRAGON) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for item_id, item in items_data.items():
        out[str(item_id)] = {
            "id": int(item_id),
            "name": item.get("name"),
            "gold": (item.get("gold") or {}).get("total"),
            "imageUrl": f"{base}/cdn/{version}/img/item/{item.get('image', {}).get('full', f'{item_id}.png')}",
        }
    return out


def build_rune_map(runes_data: list, base: str = DDRAGON) -> dict[str, dict]:
    """Flatten runesReforged.json: rune trees (styles) and every perk inside them."""
    out: dict[str, dict] = {}
    for style in runes_data:
        out[str(style["id"])] = {
            "id": style["id"],
            "name": style["name"],
            "type": "style",
            "imageUrl": f"{base}/cdn/img/{style['icon']}",
        }
        for slot_index, slot in enumerate(style.get("slots", [])):
            for rune in slot.get("runes", []):
                out[str(rune["id"])] = {
                    "id": rune["id"],
                    "name": rune["name"],
                    "type": "keystone" if slot_index == 0 else "rune",
                    "styleId": style["id"],
                    "imageUrl": f"{base}/cdn/img/{rune['icon']}",
                }
    return out


def build_spell_map(spells_data: dict, version: str, base: str = DDRAGON) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for spell in spells_data.values():
        key = str(spell["key"])
        out[key] = {
            "id": int(key),
            "alias": spell["id"],
            "name": spell["name"],
            "imageUrl": f"{base}/cdn/{version}/img/spell/{spell['image']['full']}",
        }
    return out


def build_catalog(asset: StaticAsset, base: str | None = None) -> dict:
    base = base or _base()
    v = asset.patch_version
    return {
        "patch": v,
        "lang": asset.lang,
        "champions": build_champion_map(asset.champions_jsonb, v, base),
        "items": build_item_map(asset.items_jsonb, v, base),
        "runes": build_rune_map(asset.runes_jsonb, base),
        "spells": build_spell_map(asset.spells_jsonb, v, base),
    }


# ---------------------------------------------------------------- network
def fetch_latest_version(http: httpx.Client | None = None) -> str:
    http = http or httpx.Client(timeout=10)
    resp = http.get(f"{_base()}/api/versions.json")
    if resp.status_code != 200:
        raise DDragonError(f"versions.json returned HTTP {resp.status_code}")
    return parse_latest_version(resp.json())


def fetch_static_files(version: str, lang: str, http: httpx.Client | None = None) -> dict:
    http = http or httpx.Client(timeout=20)
    out = {}
    for name, filename in FILES.items():
        resp = http.get(f"{_base()}/cdn/{version}/data/{lang}/{filename}")
        if resp.status_code != 200:
            raise DDragonError(f"{filename} ({lang}) returned HTTP {resp.status_code}")
        payload = resp.json()
        out[name] = payload if name == "runes" else payload.get("data", {})
    return out


def upsert_static_asset(version: str, lang: str, files: dict) -> StaticAsset:
    asset = db.session.get(StaticAsset, (version, lang))
    if asset is None:
        asset = StaticAsset(patch_version=version, lang=lang)
        db.session.add(asset)
    asset.champions_jsonb = files["champions"]
    asset.items_jsonb = files["items"]
    asset.runes_jsonb = files["runes"]
    asset.spells_jsonb = files["spells"]
    asset.synced_at = datetime.now(timezone.utc)
    db.session.commit()
    _invalidate_cache(version, lang)
    return asset


def sync_patch(version: str | None = None, langs=DEFAULT_LANGS, http: httpx.Client | None = None) -> str:
    http = http or httpx.Client(timeout=20)
    version = version or fetch_latest_version(http)
    for lang in langs:
        upsert_static_asset(version, lang, fetch_static_files(version, lang, http))
    log.info("Data Dragon patch %s synced for %s", version, ", ".join(langs))
    return version


# ---------------------------------------------------------------- lookup
def _cache_key(patch: str, lang: str) -> str:
    return f"catalog:{patch}:{lang}"


def _invalidate_cache(version: str, lang: str) -> None:
    for key in (_cache_key(version, lang), _cache_key("latest", lang)):
        redis_client.delete(key)


def resolve_asset(patch: str, lang: str) -> StaticAsset | None:
    versions = db.session.scalars(select(StaticAsset.patch_version).where(StaticAsset.lang == lang)).all()
    if not versions:
        return None
    if patch == "latest":
        chosen = max(versions, key=version_key)
    elif patch in versions:
        chosen = patch
    else:
        prefixed = [v for v in versions if v.startswith(patch + ".")]
        if not prefixed:
            return None
        chosen = max(prefixed, key=version_key)
    return db.session.get(StaticAsset, (chosen, lang))


def get_catalog(patch: str, lang: str) -> dict | None:
    key = _cache_key(patch, lang)
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    asset = resolve_asset(patch, lang)
    if asset is None:
        return None
    catalog = build_catalog(asset)
    ttl = current_app.config.get("CATALOG_CACHE_TTL_SEC", 86400)
    redis_client.set(key, json.dumps(catalog, ensure_ascii=False), ex=ttl)
    return catalog
