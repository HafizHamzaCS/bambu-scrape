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


def execute_run(run_id: str) -> None:
    """Blocking scrape; meant to run in a worker thread."""
    run = _runs[run_id]
    categories = list(CATEGORIES) if run["category"] == "all" else [run["category"]]
    try:
        for cat in categories:
            products = scraper.scrape_category(
                cat, limit=run["limit"], delay_s=settings.RATE_LIMIT_INTERVAL_S
            )
            payload = {
                "category": cat,
                "scraped_at": _now(),
                "run_id": run_id,
                "products": products,
            }
            if products:
                (_data_dir() / "catalog" / f"{cat}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            else:
                run["error_count"] += 1
                run["error_summary"] = (
                    f"No products extracted for '{cat}'; catalog file not updated"
                )
            run["products_seen"] += len(products)
            run["variants_seen"] += sum(len(p.get("variants") or []) for p in products)
        run["status"] = "failed" if run["error_count"] == len(categories) else "completed"
    except Exception as exc:
        logger.exception("Scrape run %s failed", run_id)
        run["status"] = "failed"
        run["error_count"] += 1
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
