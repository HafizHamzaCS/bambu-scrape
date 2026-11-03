# Build Plan (U0–U9)

| Unit | Description | Status |
|---|---|---|
| **U0: Discovery and fixtures** | Fetch `robots.txt`. Fetch `/collections.json` (all pages). Map collection handles to the 2 v1 categories and record the mapping in `progress-tracker.md` Architecture Decisions. Save `products.json` and `products/{handle}.json` samples for one printer and one filament product, plus one collection listing for each, under `tests/fixtures/`. Record the capture date and URL in a fixture README. | Partial (Awaiting live EU capture) |
| **U1: Project skeleton** | `requirements.txt` (pinned), `config.py` (Settings, env reading, fail-fast on missing `SCRAPER_API_KEY` when run as server), `models.py` (Money, Variant, Product, Media, `ChangeFlag`), `ruff` and `mypy` config, `pytest` scaffold, `.gitignore` (includes `*.sqlite3`, `.env`). | Complete (2026-11-02) |
| **U2: Base scraper** | `base_scraper.py`: shared async client, token bucket rate limiter, semaphore, retry and backoff, `Retry-After` handling, UA rotation, robots.txt check, exception types, pagination helper, refurbished filter, HTML fallback helper with per-run cache. Tests use respx and fixtures. | Next Up |
| **U3: Database and diff engine** | `database.py`, migration `0001_init.sql` with `scrape_runs`, `categories`, `products`, `variants`, `change_events`, `schema_version`. Run lifecycle functions. Diff engine with all flags. Tests cover every diff rule and invariants 4, 5, and 6. | Pending |
| **U4: Printers scraper (full)** | `categories/printers.py`: collection handles, mapping, product mapping, spec table and compatibility parsing from HTML fallback, media extraction. Tests on fixtures. | Pending |
| **U5: Filaments scraper (full)** | `categories/filaments.py`. Same pattern as U4, plus spool type and material option handling. Tests on fixtures. | Pending |
| **U6: Category registry** | `categories/__init__.py` registers only `printers` and `filaments`. Tests check both are registered and that any other key is rejected. No other category files are created. | Pending |
| **U7: FastAPI service** | `main.py`: `/health`, `POST /scrape` (202 and 409 behavior), `GET /catalog` with filters, API key dependency, response envelope, startup recovery of stale `running` runs. | Pending |
| **U8: CLI runner** | `run.py` with `--category` and `--all`, exit codes, output layout from `ui-context.md`. | Pending |
| **U9: Deployment** | `Dockerfile` (python:3.12-slim, non-root user), `Procfile` (`web: uvicorn main:app --host 0.0.0.0 --port $PORT`), `README.md` with local run, test, and Railway steps. Railway volume mounted at `DATA_DIR`. | Pending |
