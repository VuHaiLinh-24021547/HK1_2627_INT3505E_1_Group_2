"""Application configuration classes (values read from environment / .env)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"

load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_json(name: str, default):
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


DEFAULT_SCOPES = ["players:read", "players:sync", "matches:read", "static:read"]


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JSON_SORT_KEYS = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    API_VERSION = "1.0.0"
    PROBLEM_TYPE_BASE = os.getenv("PROBLEM_TYPE_BASE", "https://lol-match-history.local/errors/")

    # Infrastructure
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://lol:lol@localhost:5432/lol_match_history"
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_FAKEREDIS = False

    # Riot API
    RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")
    RIOT_MAX_RETRIES = _env_int("RIOT_MAX_RETRIES", 2)
    RIOT_HTTP_TIMEOUT = _env_int("RIOT_HTTP_TIMEOUT", 10)
    # (max requests, window seconds) per routing host — development key defaults
    RIOT_RATE_LIMITS = [(20, 1), (100, 120)]
    RIOT_LIMITER_MAX_WAIT_SEC = _env_int("RIOT_LIMITER_MAX_WAIT_SEC", 30)
    DDRAGON_BASE_URL = "https://ddragon.leagueoflegends.com"

    # Sync
    SYNC_COOLDOWN_SEC = _env_int("SYNC_COOLDOWN_SEC", 120)
    SYNC_MODE = os.getenv("SYNC_MODE", "rq")  # rq | thread | inline
    SYNC_JOB_TTL_SEC = 86400
    PROFILE_CACHE_TTL_SEC = 300
    CATALOG_CACHE_TTL_SEC = 86400
    IDEMPOTENCY_TTL_SEC = 86400

    # OAuth 2.0 / JWT
    JWT_ALGORITHMS = ["RS256", "ES256"]
    JWT_ISSUER = os.getenv("JWT_ISSUER", "http://127.0.0.1:5000")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "lol-match-history-api")
    JWT_ACCESS_TTL_SEC = _env_int("JWT_ACCESS_TTL_SEC", 900)
    JWT_PRIVATE_KEY_PATH = os.getenv("JWT_PRIVATE_KEY_PATH", str(INSTANCE_DIR / "keys" / "jwt_private.pem"))
    JWT_PUBLIC_KEY_PATH = os.getenv("JWT_PUBLIC_KEY_PATH", str(INSTANCE_DIR / "keys" / "jwt_public.pem"))
    JWT_PRIVATE_KEY_PEM: str | None = None
    JWT_PUBLIC_KEY_PEM: str | None = None
    JWT_JWKS_URL = os.getenv("JWT_JWKS_URL") or None
    JWT_KID = "lol-match-history-dev"
    ENABLE_TOKEN_ENDPOINT = True
    AUTO_GENERATE_KEYS = True
    OAUTH_CLIENTS = _env_json(
        "OAUTH_CLIENTS",
        {"demo-client": {"secret": "demo-secret", "scopes": DEFAULT_SCOPES}},
    )


class DevConfig(BaseConfig):
    """PostgreSQL + Redis + RQ worker (docker-compose)."""

    DEBUG = True


class DevLiteConfig(BaseConfig):
    """No external services: SQLite file + fakeredis + background thread jobs."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DEVLITE_DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'dev.db'}")
    USE_FAKEREDIS = True
    SYNC_MODE = "thread"


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    USE_FAKEREDIS = True
    SYNC_MODE = "inline"
    RIOT_API_KEY = "RGAPI-test-key"
    AUTO_GENERATE_KEYS = False  # keys are injected in-memory by the test fixtures
    JWT_JWKS_URL = None
    OAUTH_CLIENTS = {
        "demo-client": {"secret": "demo-secret", "scopes": DEFAULT_SCOPES},
        "readonly-client": {"secret": "readonly-secret", "scopes": ["static:read"]},
    }


class ProdConfig(BaseConfig):
    DEBUG = False
    ENABLE_TOKEN_ENDPOINT = False
    AUTO_GENERATE_KEYS = False


CONFIGS = {
    "dev": DevConfig,
    "devlite": DevLiteConfig,
    "test": TestConfig,
    "prod": ProdConfig,
}


def get_config(name: str | None):
    name = (name or os.getenv("APP_CONFIG") or "dev").lower()
    if name not in CONFIGS:
        raise ValueError(f"Unknown config '{name}'. Choose one of {sorted(CONFIGS)}")
    return CONFIGS[name]
