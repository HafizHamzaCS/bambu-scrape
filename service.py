"""Run management: executes scraper.py in the background and stores results as JSON files."""

import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import scraper
from config import settings

logger = logging.getLogger(__name__)

CATEGORIES = tuple(scraper.CATEGORY_HANDLES)

_lock = threading.Lock()
_runs: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _data_dir() -> Path:
    path = Path(settings.DATA_DIR)
    (path / "catalog").mkdir(parents=True, exist_ok=True)
    (path / "runs").mkdir(parents=True, exist_ok=True)
    return path


def _save_run(run: dict[str, Any]) -> None:
    (_data_dir() / "runs" / f"{run['run_id']}.json").write_text(json.dumps(run), encoding="utf-8")


def start_run(category: str, limit: int | None) -> tuple[dict[str, Any] | None, str | None]:
    """Register a run. Returns (run, None) or (None, active_run_id) when one is already active."""
    with _lock:
        for active in _runs.values():
            if active["status"] == "running":
                return None, active["run_id"]
        run: dict[str, Any] = {
            "run_id": str(uuid.uuid4()),
            "category": category,
            "limit": limit,
            "status": "running",
            "started_at": _now(),
            "finished_at": None,
            "products_seen": 0,
            "variants_seen": 0,
            "error_count": 0,
            "error_summary": None,
        }
        _runs[run["run_id"]] = run
        return run, None


def _previous_products(cat: str) -> list[dict[str, Any]]:
    path = _data_dir() / "catalog" / f"{cat}.json"
    if path.is_file():
        return list(json.loads(path.read_text(encoding="utf-8"))["products"])
    return []


def execute_run(run_id: str) -> None:
    """Blocking scrape; meant to run in a worker thread.

    Products that fail to scrape (e.g. HTTP 429) are listed as errors and their previous
    record, if any, is kept so a partial run never shrinks the catalog.
    """
    run = _runs[run_id]
    categories = list(CATEGORIES) if run["category"] == "all" else [run["category"]]
    all_errors: list[str] = []
    try:
        for cat in categories:
            errors: list[str] = []
            products = scraper.scrape_category(
                cat, limit=run["limit"], delay_s=settings.RATE_LIMIT_INTERVAL_S, errors=errors
            )
            all_errors += [f"[{cat}] {e}" for e in errors]
            run["products_seen"] += len(products)
            run["variants_seen"] += sum(len(p.get("variants") or []) for p in products)
            if not products:
                all_errors.append(f"[{cat}] no products extracted; catalog file not updated")
                continue
            failed = {e.split(":", 1)[0] for e in errors}
            fresh = {p["handle"] for p in products}
            kept = [p for p in _previous_products(cat) if p["handle"] in failed - fresh]
            payload = {
                "category": cat,
                "scraped_at": _now(),
                "run_id": run_id,
                "products": products + kept,
            }
            (_data_dir() / "catalog" / f"{cat}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        run["error_count"] = len(all_errors)
        run["error_summary"] = "; ".join(all_errors[:10]) or None
        if not all_errors:
            run["status"] = "completed"
        else:
            run["status"] = "partial" if run["products_seen"] else "failed"
    except Exception as exc:
        logger.exception("Scrape run %s failed", run_id)
        run["status"] = "failed"
        run["error_count"] = len(all_errors) + 1
        run["error_summary"] = str(exc)[:500]
    finally:
        run["finished_at"] = _now()
        _save_run(run)


def get_run(run_id: str) -> dict[str, Any] | None:
    if run_id in _runs:
        return _runs[run_id]
    path = _data_dir() / "runs" / f"{run_id}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_catalog(category: str | None) -> list[dict[str, Any]]:
    """Return products from the latest successful run of one category, or all categories."""
    products: list[dict[str, Any]] = []
    for cat in [category] if category else CATEGORIES:
        path = _data_dir() / "catalog" / f"{cat}.json"
        if path.is_file():
            products.extend(json.loads(path.read_text(encoding="utf-8"))["products"])
    return products
