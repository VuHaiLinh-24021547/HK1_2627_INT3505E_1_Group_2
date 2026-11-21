from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import create_app
from app.auth.jwt_auth import issue_access_token
from app.auth.keys import generate_rsa_keypair
from app.config import DEFAULT_SCOPES
from app.extensions import db

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rsa_keypair():
    return generate_rsa_keypair()


@pytest.fixture
def app(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    application = create_app("test")
    application.config["JWT_PRIVATE_KEY_PEM"] = private_pem
    application.config["JWT_PUBLIC_KEY_PEM"] = public_pem
    application.extensions["riot_sleep"] = lambda _sec: None
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        application.extensions["redis"].flushdb()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    def _make(scopes: list[str] | None = None, sub: str = "demo-client") -> dict[str, str]:
        with app.app_context():
            token, _ = issue_access_token(sub, scopes if scopes is not None else DEFAULT_SCOPES)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def sample_account():
    return load_fixture("account_v1.json")


@pytest.fixture
def sample_summoner():
    return load_fixture("summoner_v4.json")


@pytest.fixture
def sample_league():
    return load_fixture("league_v4.json")


@pytest.fixture
def sample_match():
    return load_fixture("match_v5_detail.json")


@pytest.fixture
def sample_timeline():
    return load_fixture("match_v5_timeline.json")


@pytest.fixture
def sample_ddragon():
    return load_fixture("ddragon.json")
