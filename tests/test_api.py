"""Unit tests for FastAPI endpoints, authentication, and lifespan."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from config import Settings
from main import app, lifespan, require_api_key
from models import ERROR_UNAUTHORIZED


def test_health_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that /health returns status: ok without authentication."""
    monkeypatch.setattr("main.settings", Settings(SCRAPER_API_KEY="test-key"))
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_require_api_key_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that require_api_key succeeds when header matches configured SCRAPER_API_KEY."""
    test_key = "secret-test-key-12345"
    monkeypatch.setattr("main.settings", Settings(SCRAPER_API_KEY=test_key))

    result = require_api_key(x_api_key=test_key)
    assert result == test_key


def test_require_api_key_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that require_api_key raises 401 when header does not match."""
    monkeypatch.setattr("main.settings", Settings(SCRAPER_API_KEY="expected-secret-key"))

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key="wrong-key")

    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["error"]["code"] == ERROR_UNAUTHORIZED


def test_require_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that require_api_key raises 401 when header is missing."""
    monkeypatch.setattr("main.settings", Settings(SCRAPER_API_KEY="expected-secret-key"))

    with pytest.raises(HTTPException) as exc_info:
        require_api_key(x_api_key=None)

    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["error"]["code"] == ERROR_UNAUTHORIZED


@pytest.mark.asyncio
async def test_lifespan_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that lifespan raises RuntimeError when SCRAPER_API_KEY is not set."""
    monkeypatch.setattr("main.settings", Settings(SCRAPER_API_KEY=None))

    with pytest.raises(RuntimeError, match="SCRAPER_API_KEY environment variable must be set"):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that lifespan succeeds when SCRAPER_API_KEY is configured."""
    monkeypatch.setattr("main.settings", Settings(SCRAPER_API_KEY="valid-key"))

    async with lifespan(app):
        assert True
