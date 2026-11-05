"""FastAPI application entry point and HTTP service for catalog sync."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import service
import woocommerce
from config import settings
from models import (
    ERROR_INVALID_CATEGORY,
    ERROR_RUN_CONFLICT,
    ERROR_RUN_NOT_FOUND,
    ERROR_UNAUTHORIZED,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate server prerequisites on startup and clean up on shutdown."""
    if not settings.SCRAPER_API_KEY:
        error_msg = "SCRAPER_API_KEY environment variable must be set to start server."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    logger.info("Service initialized. Running catalog sync service.")
    yield
    logger.info("Service shutting down.")


app = FastAPI(
    title="Bambu Lab EU Catalog Sync Service",
    version="0.1.0",
    lifespan=lifespan,
)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate X-API-Key header against configured SCRAPER_API_KEY."""
    if not settings.SCRAPER_API_KEY or not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "data": None,
                "meta": {},
                "error": {
                    "code": ERROR_UNAUTHORIZED,
                    "message": "Missing or invalid X-API-Key header",
                },
            },
        )
    if not secrets.compare_digest(x_api_key, settings.SCRAPER_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "data": None,
                "meta": {},
                "error": {
                    "code": ERROR_UNAUTHORIZED,
                    "message": "Missing or invalid X-API-Key header",
                },
            },
        )
    return x_api_key


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """Health check endpoint open to unauthenticated callers."""
    return {"status": "ok"}


def _envelope(
    data: Any, meta: dict[str, Any] | None = None, error: dict[str, str] | None = None
) -> dict[str, Any]:
    return {"data": data, "meta": meta or {}, "error": error}


def _error(
    code: int, err_code: str, message: str, meta: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content=_envelope(None, meta, {"code": err_code, "message": message}),
    )


class ScrapeRequest(BaseModel):
    """Body of POST /scrape."""

    category: str = "printers"
    limit: int | None = None


@app.post("/scrape", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape(
    body: ScrapeRequest,
    background: BackgroundTasks,
    _key: str = Depends(require_api_key),
) -> Any:
    """Start a background scrape of printers, filaments or all."""
    if body.category not in (*service.CATEGORIES, "all"):
        return _error(
            400, ERROR_INVALID_CATEGORY, f"Category '{body.category}' is not supported in v1"
        )
    run, active_id = service.start_run(body.category, body.limit)
    if run is None:
        return _error(
            409,
            ERROR_RUN_CONFLICT,
            "A scrape is already in progress",
            {"active_run_id": active_id},
        )
    background.add_task(service.execute_run, run["run_id"])
    return _envelope(
        {"run_id": run["run_id"], "status": "running", "category": run["category"]},
        {"started_at": run["started_at"]},
    )


@app.get("/runs/{run_id}")
async def get_run(run_id: str, _key: str = Depends(require_api_key)) -> Any:
    """Inspect the status of a scrape run."""
    run = service.get_run(run_id)
    if run is None:
        return _error(404, ERROR_RUN_NOT_FOUND, f"Run '{run_id}' not found")
    meta = {"started_at": run["started_at"], "finished_at": run["finished_at"]}
    data = {k: v for k, v in run.items() if k not in meta}
    return _envelope(data, meta)


@app.get("/catalog")
async def get_catalog(
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _key: str = Depends(require_api_key),
) -> Any:
    """Return products from the latest successful scrape (JSON, import-ready)."""
    if category is not None and category not in service.CATEGORIES:
        return _error(400, ERROR_INVALID_CATEGORY, f"Category '{category}' is not supported in v1")
    products = service.load_catalog(category)
    return _envelope(
        products[offset : offset + limit],
        {"total_count": len(products), "limit": limit, "offset": offset},
    )


@app.get("/export/woocommerce")
async def export_woocommerce(
    category: str | None = None,
    fmt: str = Query(default="csv", alias="format", pattern="^(csv|json)$"),
    include_prices: bool = False,
    sku_prefix: str = "",
    max_images: int = Query(default=10, ge=1, le=50),
    _key: str = Depends(require_api_key),
) -> Any:
    """Export the latest scrape as a WooCommerce draft-product import (CSV or REST JSON)."""
    if category is not None and category not in service.CATEGORIES:
        return _error(400, ERROR_INVALID_CATEGORY, f"Category '{category}' is not supported in v1")
    opts = woocommerce.ExportOptions(include_prices, sku_prefix, max_images)
    products = service.load_catalog(category)
    if fmt == "json":
        items = woocommerce.to_rest_products(products, opts)
        return _envelope(items, {"count": len(items)})
    return Response(
        content=woocommerce.render_csv(products, opts),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bambu-woocommerce-import.csv"'},
    )
