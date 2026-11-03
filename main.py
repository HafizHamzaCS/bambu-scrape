"""FastAPI application entry point and HTTP service for catalog sync."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, status

from config import settings
from models import ERROR_UNAUTHORIZED

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
