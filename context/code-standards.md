# Code Standards

These conventions exist so that a module written in session 2 looks like a
module written in session 20. When in doubt, match the nearest existing
module. If no nearby example exists, follow the rules below literally.

## General principles

- Prefer explicit over clever. A reader should understand a function without
  opening three other files.
- Every function that touches the network, the database, or the file system
  is either `async` (network) or documented as blocking (database, file).
  Database calls are synchronous `sqlite3`, and they are only called from
  `database.py` helpers that run them in `asyncio.to_thread` when invoked from
  async code.
- No `print()` anywhere except `run.py`'s output formatter. Use `logging`.
- No bare `except:`. No `except Exception: pass`. Catch the narrowest type,
  log it with context, and re-raise or record it.
- No mutable default arguments. No global mutable state except the single
  `Settings` instance in `config.py`.
- Keep functions short. If a function exceeds about 40 lines or has more than
  one reason to change, split it.

## Python conventions

- Python 3.12 syntax. Use `X | None`, not `Optional[X]`. Use builtin generics
  (`list[str]`, `dict[str, int]`).
- Every function has full type annotations on parameters and return values,
  including `-> None`. `mypy --strict` must pass.
- Modules are `snake_case.py`. Classes are `PascalCase`. Constants are
  `UPPER_SNAKE_CASE`. Private helpers are prefixed with a single underscore.
- Imports are grouped: standard library, third-party, local. One blank line
  between groups. `ruff` enforces this (`I` rule set).
- Use `from __future__ import annotations` only if a forward reference
  actually requires it. Do not add it by default.
- Use `dataclasses.dataclass(frozen=True, slots=True)` for internal value
  objects that are not validated from external input (for example, a
  `RunSummary`). Use Pydantic `BaseModel` for anything parsed from the store
  or the API.
- Timestamps: always timezone-aware UTC `datetime` objects internally. Stored
  and serialized as ISO 8601 strings ending in `Z`. Never use naive
  datetimes. Never use `datetime.utcnow()`. Use `datetime.now(timezone.utc)`.

## Models (`models.py`)

- All external store JSON is parsed through a Pydantic model with
  `model_config = ConfigDict(extra="ignore")`. Unknown fields from the store
  must not break the scraper.
- Field names in Python are `snake_case`. Map Shopify's keys with
  `Field(alias="...")` where they differ.
- Money: parse Shopify's decimal string prices into `Money` with
  `Decimal(str)`, then convert to `*_minor` integers with
  `int((d * 100).quantize(Decimal("1")))`. Never call `float()` on a price.
  Ban a currency value that is not exactly three uppercase letters.
- The `ChangeFlag` enum is the single source of truth for event names:
  `IS_NEW_PRODUCT`, `IS_NEW_VARIANT`, `IS_NEW_CATEGORY`, `PRICE_CHANGED`,
  `AVAILABILITY_CHANGED`. No string literals for event types elsewhere.

## Scraper classes (`base_scraper.py`, `categories/*.py`)

- `BambuBaseScraper` is the only base class. Category scrapers subclass it
  and set class attributes, not override core logic:

  ```python
  class PrintersScraper(BambuBaseScraper):
      CATEGORY_KEY = "printers"
      CATEGORY_LABEL = "3D Printers"
      COLLECTION_HANDLES = frozenset({"...", "..."})  # verified in U0
      EXTRA_FILTERS: tuple[Callable[[Product], bool], ...] = ()
  ```

- Category-specific logic goes in named hook methods on the subclass, such as
  `def map_product(self, raw: ProductRaw) -> Product`. Hook names are defined
  in the base class with a docstring and a default implementation.
- Do not create category modules for categories outside v1. When a later
  unit adds one, it follows the same pattern as printers and filaments and is
  registered at that time.
- Every category module is registered in `categories/__init__.py`'s
  `CATEGORY_REGISTRY` dict. A module that is not registered is a bug.

## HTTP and error handling

- One `httpx.AsyncClient` per process, created in the FastAPI lifespan (or in
  `run.py`'s main coroutine) and closed on shutdown. Never create a client
  per request.
- Errors are typed. Use these exceptions, defined in `base_scraper.py`:
  `ScraperError` (base), `RetryableHTTPError`, `FatalHTTPError`,
  `BotChallengeDetected`, `RateLimitExhausted`, `RobotsDisallowed`.
- Log every retry at WARNING with the URL, attempt number, and status. Log
  every final failure at ERROR with the same plus the exception class.
- Never log full response bodies, cookies, or the API key. Log only the URL
  path, status code, and content length.

## Database (`database.py`)

- Only `database.py` contains SQL strings. Other modules call named functions
  such as `upsert_product`, `insert_change_event`, `start_run`, and
  `finish_run`.
- All queries use parameter binding (`?` placeholders). String formatting
  of SQL is forbidden, even for table names.
- Each public function opens or reuses a connection through one
  `get_connection()` helper that sets `PRAGMA foreign_keys = ON`,
  `PRAGMA journal_mode = WAL`, and `row_factory = sqlite3.Row`.
- Migrations are files named `migrations/NNNN_short_description.sql`, applied
  in order. Each runs in a transaction.
- Timestamps in the database are TEXT, ISO 8601 UTC.

## FastAPI (`main.py`)

- Routes are declared with `APIRouter` and included in the app. Each route
  has a `response_model` and a `status_code`.
- Input models are Pydantic. Path and query parameters are typed.
  `category` accepts only the keys in `CATEGORY_REGISTRY` plus `all`, using a
  `Literal` type generated from the registry.
- The API key check is a single dependency (`require_api_key`) applied at the
  router level, not per route.
- Response envelope for every JSON response:
  ```json
  { "data": <payload or null>, "meta": { ... }, "error": null }
  ```
  On error: `"data": null`, `"error": {"code": "<machine_code>", "message": "<human text>"}`.
- Background work uses FastAPI's `BackgroundTasks` or `asyncio.create_task`
  with a strong reference kept in a module-level set. Never fire and forget an
  un-referenced task, because it can be garbage collected.

## CLI (`run.py`)

- `argparse` only. No Click or Typer in v1.
- Exactly one of `--category <key>` or `--all` is required. Using both is an
  error.
- Exit codes: `0` completed, `2` usage error, `3` partial, `4` failed.

## Tests

- `pytest` with `pytest-asyncio` in auto mode.
- Test files mirror source files: `tests/test_base_scraper.py`,
  `tests/test_database.py`, `tests/categories/test_printers.py`, and so on.
- Fixtures are real saved responses under `tests/fixtures/<category>/`, with
  a `README` line stating the URL and capture date for each file. Fixtures
  are updated by re-capturing, never by hand-editing.
- Every diff rule in `architecture.md` has at least one test. Every
  invariant has at least one test where it can be tested. Invariant 4
  (integer money) and invariant 5 (incomplete runs never deactivate) are
  mandatory tests.
- No real network calls in tests. `respx` mocks are required.
- Database tests use a temporary file path via `tmp_path`, never the real
  `DATA_DIR`.

## Styling and formatting

- `ruff format` is the formatter. Line length 100.
- Docstrings: one-line summary for every public class and function. Add
  Args/Returns sections only when the signature is not obvious. Use the
  Google style.
- Comments explain why, not what. Remove comments that restate the code.

## File organization rules

- No file exceeds about 400 lines. If it does, split by responsibility.
- Test data lives in `tests/fixtures/`, never inline in test files when it
  is larger than about 20 lines.
- No new top-level folder without a matching entry in `architecture.md`.
- No dead code. Delete unused functions rather than commenting them out.
