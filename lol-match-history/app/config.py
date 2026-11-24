"""Minimal configuration for the Week 12 mock/seed API scaffold."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_SCOPES = ["players:read", "players:sync", "matches:read", "static:read"]


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "When_you_see_it")
    JSON_SORT_KEYS = False
    API_VERSION = "1.0.0"
    PROBLEM_TYPE_BASE = os.getenv("PROBLEM_TYPE_BASE", "https://lol-match-history.local/errors/")

    SYNC_COOLDOWN_SEC = int(os.getenv("SYNC_COOLDOWN_SEC", "120"))

    JWT_ALGORITHMS = ["RS256", "ES256"]
    JWT_ISSUER = os.getenv("JWT_ISSUER", "http://127.0.0.1:5000")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "lol-match-history-api")
    JWT_ACCESS_TTL_SEC = int(os.getenv("JWT_ACCESS_TTL_SEC", "900"))
    JWT_KID = "lol-match-history-dev"

    OAUTH_CLIENTS = {
        "demo-client": {"secret": "demo-secret", "scopes": DEFAULT_SCOPES},
        "readonly-client": {"secret": "readonly-secret", "scopes": ["matches:read"]},
    }
