# Progress Tracker

**To resume in a new session, say:** "Read AGENTS.md, then progress-tracker.md, and resume from Current Goal."

## Current Phase

Phase 2: Base scraper and core engine

## Current Goal

Unit U2: base scraper (`base_scraper.py` HTTP client, rate limiter, semaphore, retry/backoff, UA rotation, robots.txt check, exception types, pagination, refurbished filter, HTML fallback) or Unit U0 live fixture capture by operator from EU network.

## Completed

- **2026-11-02 — U0: Discovery and fixtures (PARTIAL):** Checked `robots.txt` and endpoint behavior on `eu.store.bambulab.com`. The store responds with HTTP 302 Found redirecting to `https://us.store.bambulab.com/` for non-EU requests (Cloudflare CF-RAY KHI), and `/robots.txt` has a malformed redirect to `https://eu.store.bambulab.combots.txt/`. Shopify robots rules permit standard `/collections/` and `/products/` paths; `*.json` endpoints are not blocked. Directory structure `tests/fixtures/` and catalog `tests/fixtures/README.md` created with PENDING LIVE CAPTURE entries per politeness and access-control rules. Live capture to be run from an EU network by operator.
- **2026-11-02 — U1: Project skeleton:** Runnable, lint-clean, type-checked project skeleton created with pinned dependencies (`requirements.txt`), frozen dataclass `Settings` in `config.py`, boundary models in `models.py` (`Money` with integer minor units and uppercase 3-letter currency, `ChangeFlag` enum, `Product` and `Variant` identity stubs), empty category registry `categories/__init__.py`, `pyproject.toml` (ruff rules E, F, W, I, B, UP, line length 100, mypy strict, pytest auto mode), `.gitignore`, and `.env.example`. 100% verified via fresh `.venv` pip install, `ruff check`, `ruff format --check`, `mypy --strict`, offline `pytest` (6 passed), line count limits (<400 lines), and secret check.

## In Progress

None.

## Next Up (build plan, in order)

Specs for each unit go in `context/specs/NN-name.md`. Write each spec only when
its unit is next. Do not write all specs at once.

- [ ] **U0: Discovery and fixtures.** Fetch `robots.txt`. Fetch
      `/collections.json` (all pages). Map collection handles to the 2
      v1 categories and record the mapping in this file's Architecture Decisions.
      Save `products.json` and `products/{handle}.json` samples for one printer
      and one filament product, plus one collection listing for each, under
      `tests/fixtures/`. Record the capture date and URL in a fixture README.
- [ ] **U1: Project skeleton.** `requirements.txt` (pinned), `config.py`
      (Settings, env reading, fail-fast on missing `SCRAPER_API_KEY` when run
      as server), `models.py` (Money, Variant, Product, Media, `ChangeFlag`),
      `ruff` and `mypy` config, `pytest` scaffold, `.gitignore` (includes
      `*.sqlite3`, `.env`).
- [ ] **U2: Base scraper.** `base_scraper.py`: shared async client, token
      bucket rate limiter, semaphore, retry and backoff, `Retry-After`
      handling, UA rotation, robots.txt check, exception types, pagination
      helper, refurbished filter, HTML fallback helper with per-run cache.
      Tests use respx and fixtures.
- [ ] **U3: Database and diff engine.** `database.py`, migration `0001_init.sql`
      with `scrape_runs`, `categories`, `products`, `variants`, `change_events`,
      `schema_version`. Run lifecycle functions. Diff engine with all flags.
      Tests cover every diff rule and invariants 4, 5, and 6.
- [ ] **U4: Printers scraper (full).** `categories/printers.py`: collection
      handles, mapping, product mapping, spec table and compatibility parsing
      from HTML fallback, media extraction. Tests on fixtures.
- [ ] **U5: Filaments scraper (full).** `categories/filaments.py`. Same
      pattern as U4, plus spool type and material option handling. Tests on
      fixtures.
- [ ] **U6: Category registry.** `categories/__init__.py` registers only
      `printers` and `filaments`. Tests check both are registered and that
      any other key is rejected. No other category files are created.
- [ ] **U7: FastAPI service.** `main.py`: `/health`, `POST /scrape` (202 and
      409 behavior), `GET /catalog` with filters, API key dependency, response
      envelope, startup recovery of stale `running` runs.
- [ ] **U8: CLI runner.** `run.py` with `--category` and `--all`, exit codes,
      output layout from `ui-context.md`.
- [ ] **U9: Deployment.** `Dockerfile` (python:3.12-slim, non-root user),
      `Procfile` (`web: uvicorn main:app --host 0.0.0.0 --port $PORT`),
      `README.md` with local run, test, and Railway steps. Railway volume
      mounted at `DATA_DIR`.

## Open Questions

- [ ] Q: Which Shopify collection handles correspond to each of the 2 v1
      categories, and does any category live as a `product_type` instead of a
      collection? | Options: collection handle mapping, product_type filter,
      both | Provisional: collection handles, with `product_type` as an
      optional filter per category. Verify in U0.
- [ ] Q: Deferred (not v1): how Bundles map to collections or tags. Revisit
      when the Bundles category is scheduled.
- [ ] Q: Can Railway's datacenter IP addresses reach `eu.store.bambulab.com`
      reliably, or does the store block or throttle them? | Options: direct
      from Railway, route through operator-approved egress | Provisional: test
      from Railway during U9; if blocked, stop and ask the operator. Do not add
      proxies.
- [ ] Q: Does the store expose product video URLs anywhere in the JSON, or only
      in the HTML page? | Options: JSON metadata, HTML `<video>` or `<source>`
      tags, embed scripts | Provisional: HTML fallback. Verify in U0.
- [ ] Q: Should `POST /scrape` be triggered by an external scheduler (Railway
      cron, GitHub Action) or by an in-process timer? | Options: external
      cron, in-process interval | Provisional: external cron only, because
      in-process timers complicate restarts. Operator to confirm.
- [ ] Q: What is the expected full-run runtime budget? The store may have
      several thousand variants. | Options: no limit, 15 minutes, 60 minutes |
      Provisional: no hard limit in code; log per-category duration and review
      after the first full run.
- [ ] Q: Is `SCRAPER_API_KEY` the only auth required, or does the operator want
      IP allow-listing on Railway as well? | Provisional: API key only in v1.
- [ ] Q: Does `eu.store.bambulab.com` enforce GeoIP redirection to `us.store.bambulab.com` for non-EU traffic, and will Railway deployments require an EU region or egress? | Options: Deploy in EU region on Railway (e.g. Frankfurt / London), or route requests via approved EU egress | Provisional: Plan Railway deployment in EU region so outbound requests originate within Europe and avoid 302 redirects.
- [ ] Q: Where should the project root and AGENTS.md reside in the workspace? | Options: Workspace root directly, or inside subfolder 'bambu-scraper/' | Provisional: Project files and 'context/' placed inside 'bambu-scraper/', with AGENTS.md at both 'bambu-scraper/AGENTS.md' and workspace root.
- [ ] Q: Does project-overview.md line 148 contradict the v1 scope of 2 categories by mentioning 8 categories? | Options: Revert to 8 categories, or keep v1 strictly scoped to 2 categories | Provisional: Keep strictly to 2 categories (printers, filaments); line 148 is a legacy draft reference.
- [ ] Q: When should missing SCRAPER_API_KEY trigger an error? | Options: Fail-fast at import in config.py, or optional at import and enforced on server startup in main.py | Provisional: Optional at import in config.py, enforced in main.py on server startup so CLI and tests can import config without setting a key.
- [ ] Q: Where should the orchestrating service functions ('run_category', 'run_all') live? | Options: In 'base_scraper.py', or in a separate 'service.py' module | Provisional: Place in 'base_scraper.py' per architecture.md defaults unless file size requires splitting into 'service.py'.

## Architecture Decisions

These are settled. Change them only with a new entry here and a matching
update to `architecture.md`.

- **2026-11-02:** Use `sqlite3` from the standard library. `sqlmodel` is not
  used, to keep dependencies small.
- **2026-11-02:** Use async `httpx` with one shared client and one shared rate
  limiter for the whole process.
- **2026-11-02:** Use Shopify's `.json` product endpoints as the primary data
  source. `.js` endpoints are a fallback only. HTML is a fallback only for
  fields the JSON lacks.
- **2026-11-02:** Store all money as integer minor units with a currency code.
- **2026-11-02:** Identify products and variants by Shopify numeric IDs. Handles
  are not identities.
- **2026-11-02:** `run.py` is the CLI, and `main.py` is the FastAPI app. Both
  call the same service function. The spec's mention of `main.py` as "server
  and CLI" is resolved this way.
- **2026-11-02:** Deactivation of missing items happens only on `completed`
  runs.
- **2026-11-02:** No end-user UI in v1.
- **2026-11-02:** Use the `AGENTS.md` filename for the entry point. Antigravity
  reads it from the workspace root. Use the same content as `CLAUDE.md` if a
  different agent is used.

## Session Notes

- **2026-11-02:** Context system created (six files plus `AGENTS.md`). Phase 0
  begins. No application code written. Next step is U0, which requires live
  store access from the operator's network. Open Questions Q1 to Q4 must be
  answered during U0.
- **2026-11-02 (scope change):** v1 is limited to 3D Printers and Filaments.
  The other six categories are deferred, with no skeleton files, stubs, or
  registry entries. The U6 unit and the Bundles question were revised to
  match.
- **2026-11-02 (Unit U0 Discovery):** Tested endpoints on `eu.store.bambulab.com`. The server returns HTTP 302 Found redirecting to `https://us.store.bambulab.com/` due to GeoIP location (CF-RAY KHI), and `/robots.txt` has a server-side malformed redirect `Location: https://eu.store.bambulab.combots.txt/`. Checked Shopify `robots.txt` on `bambulab.com`: paths for `/collections/` and `/products/` are permitted for normal catalog discovery; `*.json` endpoints are not blocked. Per politeness and access control invariants, avoided bypassing or altering IP/headers. Created `tests/fixtures/` subfolders (`printers/`, `filaments/`) and `tests/fixtures/README.md` with PENDING LIVE CAPTURE entries. Marked U0 partial; continuing to U1. Operator will execute live capture from EU network.
- **2026-11-02 (Unit U1 Skeleton):** Implemented project skeleton according to spec U1. Created `requirements.txt` with pinned dependencies, `config.py` with frozen `Settings` dataclass reading environment once at import, `models.py` with `Money` (integer minor units and uppercase 3-letter currency validator), `ChangeFlag` enum, and `Product`/`Variant` stubs with `extra="ignore"`, `categories/__init__.py` with empty registry, `tests/test_config.py`, `pyproject.toml`, `.gitignore`, and `.env.example`. Installed dependencies into a clean `.venv` (Python 3.12). Ran full verification checklist: `ruff check .` (passed), `ruff format --check .` (passed), `mypy --strict config.py models.py categories/__init__.py tests/test_config.py` (passed, 0 issues), `pytest` (6 passed in 2.53s offline), line limits confirmed (<400 lines across all files), and git diff verified free of any secrets. Unit U1 marked complete. Next unit is U2 (Base scraper) or U0 live fixture capture.
- **2026-11-02 (Railway Deployment Setup):** Created production deployment configuration for Railway. Added `Dockerfile` (Python 3.12-slim, non-root `appuser`, persistent volume directory `/app/data`, curl healthcheck), `.dockerignore`, `Procfile` (`web: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`), `railway.json` (build schema, deploy restart policy, `/health` endpoint check), comprehensive `README.md` documenting setup, volume mount at `/app/data`, Europe West deployment region requirement, and environment variables. Added `tests/test_api.py` covering `/health`, `require_api_key` authentication, and `lifespan` fail-fast validation. Verified all 12 tests pass, `ruff check` & `ruff format` pass 100%, and `mypy --strict` passes with 0 issues across all 6 source files.
