# Architecture

This is the most important context file. If implementation contradicts it,
stop and update this file first (with a note in progress-tracker.md), then
continue.

## Stack

| Layer | Technology | Role |
|---|---|---|
| Language | Python 3.12 | Runtime for everything |
| HTTP client | `httpx` (async, `AsyncClient`) | Single shared client for all outbound requests; connection pooling and HTTP/2 off |
| Data models | `pydantic` v2 | Validates all external JSON at the boundary and defines internal models |
| HTML fallback | `beautifulsoup4` with `lxml` parser | Extracts breadcrumbs, spec tables, compatibility notes, and video URLs when JSON lacks them |
| Storage | `sqlite3` (standard library) | Single-file database at `$DATA_DIR/catalog.sqlite3`. No ORM in v1 |
| API | `fastapi` + `uvicorn` | HTTP service; served by uvicorn in production |
| Config | Environment variables read once in `config.py` | No config values hard-coded in modules |
| Logging | Standard `logging` with a JSON-line formatter | One logger per module via `logging.getLogger(__name__)` |
| Tests | `pytest`, `pytest-asyncio`, `respx` | Offline tests; `respx` mocks httpx calls against saved fixtures |
| Lint/types | `ruff`, `mypy --strict` | Enforced in CI and before closing any unit |
| Deployment | Dockerfile (python:3.12-slim) + Procfile, on Railway | Persistent volume mounted at `DATA_DIR` |

Why these choices: `sqlite3` is used instead of `sqlmodel` to keep
dependencies small. Async `httpx` is used so both v1 categories can share one
rate limiter without threads. `pydantic` v2 is used for the validation
boundary only, not as an ORM.

## System boundaries (folder ownership)

```
bambu-scraper/
├── requirements.txt          # Dependencies. Only add a package in the unit that first needs it
├── config.py                 # Reads env vars into a frozen Settings object. Only module that reads os.environ
├── models.py                 # Pydantic models: Product, Variant, Media, Money, ChangeFlag enum
├── base_scraper.py           # BambuBaseScraper: HTTP client, rate limiter, retries, UA rotation,
│                             #   collection discovery, pagination, refurbished filter, HTML fallback helper
├── database.py               # SQLite schema, migrations, run lifecycle, diff engine, queries
├── categories/
│   ├── __init__.py           # Registry: CATEGORY_REGISTRY maps category key to scraper class
│   ├── printers.py           # Full implementation. Owns the "printers" collection handles
│   └── filaments.py          # Full implementation. Owns the "filaments" collection handles
│                             #   (v1 has only these two category modules)
├── main.py                   # FastAPI app only: routes, auth dependency, background task dispatch
├── run.py                    # CLI only: argparse wrapper around the same service function main.py uses
├── tests/
│   ├── fixtures/             # Saved live responses (JSON and HTML) used by offline tests
│   └── ...
├── Dockerfile
├── Procfile
└── README.md
```

Ownership rules:

- **`categories/*.py`** are the only modules that contain store-specific
  knowledge, meaning collection handles, category labels, and special
  parsing for that category. Nothing else in the codebase may contain a
  collection handle string.
- **`base_scraper.py`** contains all generic HTTP and extraction logic. No
  category-specific branching lives here.
- **`database.py`** is the only module that executes SQL. Other modules call
  its functions and never open a connection themselves.
- **`main.py`** and **`run.py`** are thin. They parse input, call one shared
  service function (`run_category(key) -> RunSummary` and
  `run_all() -> list[RunSummary]`, which live in `base_scraper.py` or a
  `service.py` if it grows), and format output. They contain no scraping
  logic.

## Scraping strategy (endpoint priority)

The scraper uses the cheapest source that has the data, in this order:

1. **`GET /collections.json?limit=250&page=N`**: discover collections. Each
   collection's `handle` is matched against the category mapping in the
   category modules. Unmapped collections are logged and ignored.
2. **`GET /collections/{handle}/products.json?limit=250&page=N`**: list
   products in a collection. Paginate until an empty `products` array is
   returned. This returns summary data only.
3. **`GET /products/{handle}.json`**: full product record. This is the
   primary detail source. It provides `body_html`, `tags`, `vendor`,
   `product_type`, `created_at`, `updated_at`, `images`, `variants` (with
   `id`, `sku`, `barcode`, `price` as a decimal string, `compare_at_price`,
   `available`, `weight`, `weight_unit`, option values), and `options`.
4. **`GET /products/{handle}.js`**: used only if the `.json` response is
   missing a variant field we need. Its prices are integer cents, so it must
   be converted carefully.
5. **HTML product page** (`GET /products/{handle}`): used only for fields the
   JSON cannot supply, namely breadcrumbs, spec tables, compatibility notes,
   and video URLs. Parsed through one helper in `base_scraper.py`. Results
   are cached within a run so the same page is never fetched twice.

Field source mapping lives in `base_scraper.py` as a documented table. Any
new field needs a row there.

## Rate limiting and retry policy (defaults, all overridable via config)

- Maximum 2 concurrent requests across the whole process (`asyncio.Semaphore`)
- Minimum 1.0 second between request starts (shared token bucket)
- Timeouts: connect 10 s, read 20 s
- Retries: up to 4 attempts on network errors, 429, and 5xx
- Backoff: `min(30, 1.0 * 2**attempt) + random(0, 0.5)` seconds
- On 429 or 503 with `Retry-After`, sleep for that value (capped at 120 s)
- On 403, 401, or a bot-challenge page: do not retry. Mark the run `partial`
  and stop the affected category
- User-Agent: rotated from a list of current desktop browser strings, one per
  run. Never impersonate a specific real user, and never send cookies or
  credentials

## Storage model

All money is stored as integer minor units (cents) with a currency code. Floats
are never used for money.

**`scrape_runs`**: `run_id` (TEXT PK, UUID4), `category` (TEXT),
`status` (TEXT: `running` | `completed` | `partial` | `failed`), `started_at`,
`finished_at` (TEXT, ISO 8601 UTC), `products_seen` (INT), `variants_seen`
(INT), `error_count` (INT), `error_summary` (TEXT, nullable)

**`categories`**: `category_key` (TEXT PK), `label` (TEXT), `first_seen_run`
(TEXT FK), `last_seen_run` (TEXT FK). Used for `IS_NEW_CATEGORY`.

**`products`**: `product_id` (INT PK, Shopify numeric ID), `category_key`
(TEXT), `handle` (TEXT, unique), `title`, `vendor`, `product_type`,
`tags_json` (TEXT), `url`, `body_html` (TEXT), `body_text` (TEXT),
`breadcrumbs_json`, `spec_table_json`, `compatibility_json`, `media_json`
(TEXT; images with full-resolution URLs and video URLs), `store_created_at`,
`store_updated_at`, `payload_hash` (TEXT, SHA-256 of the normalized product
minus volatile fields), `first_seen_run`, `last_seen_run`, `is_active`
(INT 0/1), `scraped_at` (TEXT)

**`variants`**: `variant_id` (INT PK, Shopify numeric ID), `product_id` (INT
FK), `title`, `options_json` (TEXT), `sku`, `barcode`, `price_minor` (INT),
`compare_at_minor` (INT, nullable), `currency` (TEXT, 3 letters), `available`
(INT 0/1), `weight_g` (INT, nullable), `dimensions_json` (TEXT, nullable),
`payload_hash` (TEXT), `first_seen_run`, `last_seen_run`, `is_active` (INT 0/1)

**`change_events`**: `event_id` (INT PK AUTOINCREMENT), `run_id` (FK),
`event_type` (TEXT: one of the flags below), `category_key`, `product_id`
(nullable), `variant_id` (nullable), `detail_json` (TEXT, e.g. old and new
price), `detected_at` (TEXT)

**`product_snapshots`** (optional in v1, enable only if needed): full
normalized JSON per product per run. Do not build this table in the first
unit that touches the database. Add it later through a migration.

Schema versioning: a `schema_version` table holds one row. `database.py`
applies numbered SQL migrations in order at startup. Migrations are never
edited after they have been released. Add a new one instead.

## Diff engine

Identity is the Shopify numeric ID for products and variants, never the
handle or title. Handles can change, and the ID stays stable.

Per run, per category, after normalization:

- **New product**: `product_id` not present in `products`. Insert it and
  write `IS_NEW_PRODUCT`. Its variants are not flagged separately.
- **New variant**: `variant_id` not present in `variants`, and its parent
  product existed before this run. Insert it and write `IS_NEW_VARIANT`.
- **New category**: `category_key` not present in `categories`. Insert it and
  write `IS_NEW_CATEGORY`.
- **Price changed**: `price_minor` or `compare_at_minor` differs from the
  stored value. Update it and write `PRICE_CHANGED` with old and new values.
- **Availability changed**: `available` differs. Update it and write
  `AVAILABILITY_CHANGED`.
- **Removed**: a product or variant in the database that was not seen in this
  run is marked `is_active = 0`. This happens **only** when the run's status
  is `completed`. A `partial` or `failed` run never deactivates anything.

Writes for one category run in a single SQLite transaction. If the
transaction fails, nothing from that category is written, and the run is
marked `failed`.

## Auth and access model

- `GET /health`: open, no auth
- All other endpoints require the header `X-API-Key`. The value must match
  `SCRAPER_API_KEY` from the environment. Comparison uses
  `secrets.compare_digest`.
- If `SCRAPER_API_KEY` is unset, the app refuses to start (exits with a clear
  error). It does not fall back to running unauthenticated.
- The scraper itself has no user accounts and no store login.

## Run lifecycle and concurrency

- `POST /scrape` validates input, creates a `scrape_runs` row with status
  `running`, starts a background task, and returns `202 Accepted` with the
  `run_id`. It never waits for the scrape to finish.
- Only one run per category may be `running` at once. A second request for the
  same category returns `409 Conflict` with the active `run_id`.
- `run.py` runs the same service function in the foreground and prints the
  summary.
- On startup, any `scrape_runs` row still marked `running` is set to
  `failed` with the reason "interrupted by restart". Then the service starts.

## AI and background task model

No AI or LLM components are part of this system. Background work is plain
asyncio tasks inside the uvicorn process. There is no task queue or worker
service in v1. If runs start to exceed the HTTP host's time limits, move
execution to a separate worker in a later version. Do not add that now.

## Invariants (hard rules; never violate)

1. **Store knowledge stays in `categories/`.** No collection handle, category
   label, or store-specific string appears outside `categories/` and
   `config.py` (for base URL only).
2. **One HTTP path.** Every outbound request goes through the shared client
   in `BambuBaseScraper`. No module calls `httpx` directly. The client
   enforces the rate limit, timeouts, retries, and UA rotation.
3. **Refurbished items never persist.** The refurbished filter runs before any
   detail fetch, and it runs again at normalization. A refurbished item never
   reaches `database.py`.
4. **Money is integer minor units.** Prices are stored as `*_minor` integers
   with a currency code. Floats are banned for money, including in tests.
5. **Incomplete runs never deactivate.** Only a `completed` run may set
   `is_active = 0`. A `partial` or `failed` run never does.
6. **Each category write is atomic.** One transaction per category per run.
7. **HTTP handlers never scrape inline.** `main.py` routes return `202` and
   dispatch a background task. They never await a scrape.
8. **No bypassing access controls.** No CAPTCHA solving, no challenge
   bypass, no login, no cookie injection, no spoofed identity. On a
   bot-challenge response the scraper stops and reports `partial`.
9. **`robots.txt` is honored.** `base_scraper.py` fetches and checks
   `robots.txt` at startup of each run. A disallowed path is skipped and
   logged.
10. **The database lives outside the repo.** The file is at
    `$DATA_DIR/catalog.sqlite3`, and `DATA_DIR` is a Railway volume in
    production. No `.sqlite3` file is ever committed.
11. **Schema changes are migrations.** No ad-hoc `ALTER TABLE` outside a
    numbered migration.
12. **Fixtures, not live calls, in tests.** Unit tests never make network
    calls. Live verification is a separate manual step recorded in
    progress-tracker.md.
