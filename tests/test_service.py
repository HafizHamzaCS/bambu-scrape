"""Tests for /scrape, /runs and /catalog using a stubbed scraper (no network)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import service
from config import Settings
from main import app

KEY = {"X-API-Key": "test-key"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    cfg = Settings(SCRAPER_API_KEY="test-key", DATA_DIR=str(tmp_path), RATE_LIMIT_INTERVAL_S=0.0)
    monkeypatch.setattr("main.settings", cfg)
    monkeypatch.setattr("service.settings", cfg)
    monkeypatch.setattr(service, "_runs", {})
    monkeypatch.setattr(
        service.scraper,
        "scrape_category",
        lambda cat, limit=None, delay_s=1.0: [{"handle": f"{cat}-1", "variants": [{}, {}]}],
    )
    return TestClient(app)


def test_scrape_requires_key(client: TestClient) -> None:
    assert client.post("/scrape", json={"category": "printers"}).status_code == 401
    assert client.get("/catalog").status_code == 401


def test_invalid_category(client: TestClient) -> None:
    resp = client.post("/scrape", json={"category": "bundles"}, headers=KEY)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_category"


def test_scrape_then_catalog(client: TestClient) -> None:
    resp = client.post("/scrape", json={"category": "all"}, headers=KEY)
    assert resp.status_code == 202
    run_id = resp.json()["data"]["run_id"]

    run = client.get(f"/runs/{run_id}", headers=KEY).json()["data"]
    assert run["status"] == "completed"
    assert run["products_seen"] == 2
    assert run["variants_seen"] == 4

    body = client.get("/catalog", headers=KEY).json()
    assert body["meta"]["total_count"] == 2
    only = client.get("/catalog?category=printers", headers=KEY).json()
    assert [p["handle"] for p in only["data"]] == ["printers-1"]


def test_unknown_run(client: TestClient) -> None:
    assert client.get("/runs/nope", headers=KEY).status_code == 404


def test_conflict_when_run_active(client: TestClient) -> None:
    run, _ = service.start_run("printers", None)
    assert run is not None
    resp = client.post("/scrape", json={"category": "printers"}, headers=KEY)
    assert resp.status_code == 409
    assert resp.json()["meta"]["active_run_id"] == run["run_id"]
