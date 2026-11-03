"""Runtime configuration loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Frozen application configuration loaded from environment variables."""

    DATA_DIR: str = "./data"
    SCRAPER_API_KEY: str | None = None
    BASE_URL: str = "https://eu.store.bambulab.com"
    RATE_LIMIT_INTERVAL_S: float = 1.0
    MAX_CONCURRENCY: int = 2
    REQUEST_TIMEOUT_CONNECT_S: float = 10.0
    REQUEST_TIMEOUT_READ_S: float = 20.0
    MAX_RETRIES: int = 4


def _load_settings() -> Settings:
    """Read configuration from environment variables once at module import."""
    return Settings(
        DATA_DIR=os.environ.get("DATA_DIR", "./data"),
        SCRAPER_API_KEY=os.environ.get("SCRAPER_API_KEY") or None,
        BASE_URL=os.environ.get("BASE_URL", "https://eu.store.bambulab.com"),
        RATE_LIMIT_INTERVAL_S=float(os.environ.get("RATE_LIMIT_INTERVAL_S", "1.0")),
        MAX_CONCURRENCY=int(os.environ.get("MAX_CONCURRENCY", "2")),
        REQUEST_TIMEOUT_CONNECT_S=float(os.environ.get("REQUEST_TIMEOUT_CONNECT_S", "10.0")),
        REQUEST_TIMEOUT_READ_S=float(os.environ.get("REQUEST_TIMEOUT_READ_S", "20.0")),
        MAX_RETRIES=int(os.environ.get("MAX_RETRIES", "4")),
    )


settings: Settings = _load_settings()
