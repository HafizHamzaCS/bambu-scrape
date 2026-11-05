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
        lambda cat, limit=None, delay_s=1.0, errors=None: [
            {"handle": f"{cat}-1", "variants": [{}, {}]}
        ],
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


def test_partial_run_reports_errors_and_keeps_previous_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.post("/scrape", json={"category": "printers"}, headers=KEY).status_code == 202

    def flaky(cat: str, limit: int | None = None, delay_s: float = 1.0, errors=None):  # type: ignore[no-untyped-def]
        if errors is not None:
            errors.append("old-one: HTTP Error 429: Too Many Requests")
        return [{"handle": "new-one", "variants": [{}]}]

    monkeypatch.setattr(service.scraper, "scrape_category", flaky)
    service._runs.clear()
    resp = client.post("/scrape", json={"category": "printers"}, headers=KEY)
    run = client.get(f"/runs/{resp.json()['data']['run_id']}", headers=KEY).json()["data"]
    assert run["status"] == "partial"
    assert run["error_count"] == 1
    assert "429" in run["error_summary"]
    # "old-one" was never in the earlier catalog (it held "printers-1"), so only the new one remains
    handles = [
        p["handle"] for p in client.get("/catalog?category=printers", headers=KEY).json()["data"]
    ]
    assert handles == ["new-one"]


def test_previous_record_kept_when_product_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.post("/scrape", json={"category": "printers"}, headers=KEY).status_code == 202

    def flaky(cat: str, limit: int | None = None, delay_s: float = 1.0, errors=None):  # type: ignore[no-untyped-def]
        if errors is not None:
            errors.append("printers-1: HTTP Error 429: Too Many Requests")
        return [{"handle": "other", "variants": []}]

    monkeypatch.setattr(service.scraper, "scrape_category", flaky)
    service._runs.clear()
    client.post("/scrape", json={"category": "printers"}, headers=KEY)
    handles = sorted(
        p["handle"] for p in client.get("/catalog?category=printers", headers=KEY).json()["data"]
    )
    assert handles == ["other", "printers-1"]


def test_retry_wait_honours_retry_after() -> None:
    import urllib.error
    from email.message import Message

    headers = Message()
    headers["Retry-After"] = "45"
    err = urllib.error.HTTPError("u", 429, "Too Many", headers, None)
    assert service.scraper._retry_wait_s(err, 1) == 45.0
    assert (
        service.scraper._retry_wait_s(urllib.error.HTTPError("u", 429, "x", Message(), None), 2)
        == 60.0
    )
    assert service.scraper._retry_wait_s(RuntimeError("x"), 3) == 6.0
