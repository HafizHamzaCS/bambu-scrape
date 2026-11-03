# Spec: Unit U1 — Project Skeleton

## Goal
Establish a runnable, lint-clean, type-checked project skeleton with strict configuration, core data models, and test harnesses, containing no scraping logic.

## Design
The skeleton defines fundamental configuration and boundary data structures while deferring scraping, database, and API logic to later units.
- `config.py` encapsulates a frozen dataclass `Settings` reading environment variables once at module import.
- `models.py` defines immutable data structures using Pydantic v2 with `extra="ignore"`, integer-minor `Money`, and the canonical `ChangeFlag` enum, plus minimal stub models for `Product` and `Variant` (retaining only identity attributes `product_id` and `variant_id` until U2–U4).
- `categories/__init__.py` declares an empty `CATEGORY_REGISTRY` mapping.
- Tooling configuration (`pyproject.toml`, `.gitignore`, `.env.example`) enforces Python 3.12 syntax, ruff linting/formatting (line length 100, rule sets E, F, W, I, B, UP), mypy strict typing, and pytest configuration with `asyncio_mode = "auto"`.

## Implementation
1. **`requirements.txt`**: Pin exact versions for `httpx`, `fastapi`, `uvicorn`, `pydantic`, `beautifulsoup4`, `lxml`, `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`.
2. **`config.py`**: Frozen `Settings` dataclass reading `DATA_DIR`, `SCRAPER_API_KEY` (optional at import), `BASE_URL`, `RATE_LIMIT_INTERVAL_S`, `MAX_CONCURRENCY`, `REQUEST_TIMEOUT_CONNECT_S`, `REQUEST_TIMEOUT_READ_S`, `MAX_RETRIES`. Only module reading `os.environ`.
3. **`models.py`**:
   - `Money`: `amount_minor: int`, `currency: str` (validated as 3 uppercase ASCII letters).
   - `ChangeFlag(str, Enum)`: `IS_NEW_PRODUCT`, `IS_NEW_VARIANT`, `IS_NEW_CATEGORY`, `PRICE_CHANGED`, `AVAILABILITY_CHANGED`.
   - `Product` stub: `product_id: int` (identity only, docstring documenting expansion in U2-U4).
   - `Variant` stub: `variant_id: int`, `product_id: int` (identity only, docstring documenting expansion in U2-U4).
   - All external models use `ConfigDict(extra="ignore")`.
4. **`categories/__init__.py`**: Empty dictionary `CATEGORY_REGISTRY: dict[str, type] = {}`.
5. **`tests/test_config.py`**: Offline tests verifying default settings and custom environment variable overrides (`MAX_CONCURRENCY`, `RATE_LIMIT_INTERVAL_S`).
6. **`pyproject.toml`**: `ruff` configuration (line-length 100, select E, F, W, I, B, UP), `mypy` strict mode, `pytest` asyncio auto mode.
7. **`.gitignore`**: Ignore `data/`, `*.sqlite3*`, `.env`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.venv/`.
8. **`.env.example`**: Placeholder environment variables without secrets.

## Dependencies
- Python 3.12
- Pinned packages in `requirements.txt`

## Verification checklist
- [ ] `pip install -r requirements.txt` succeeds in `.venv`
- [ ] `ruff check .` passes with zero errors
- [ ] `ruff format --check .` passes
- [ ] `mypy --strict config.py models.py categories/__init__.py` passes
- [ ] `pytest` passes with no network calls
- [ ] No file exceeds 400 lines
- [ ] Git diff contains no secrets (searching for KEY, TOKEN, SECRET)
- [ ] No scraping, database, or API logic created prematurely
