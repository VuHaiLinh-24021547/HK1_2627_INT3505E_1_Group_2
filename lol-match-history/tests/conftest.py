from __future__ import annotations

import pytest

from app import create_app
from app.api.auth import issue_access_token
from app.config import DEFAULT_SCOPES


@pytest.fixture
def app():
    application = create_app("test")
    yield application


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
