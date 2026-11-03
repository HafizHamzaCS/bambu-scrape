# Project Overview: Bambu Lab EU Catalog Sync

## One-paragraph overview

This project is a modular, production-ready Python scraper that monitors the
product catalog of the Bambu Lab EU storefront (`https://eu.store.bambulab.com`)
and keeps an internal copy of it in sync. Each run walks the two v1 categories (3D Printers and
Filaments), extracts complete product and variant data, stores
point-in-time snapshots, and compares the result against the previous
successful run. Anything that did not exist before is flagged as a new
product, a new variant, or a new category. The service runs as a FastAPI app
on Railway, and the same code runs from a command line for local work and
testing.

The primary purpose is **catalog synchronization and new-item detection**. A
full product dump is secondary and exists so that diffs have something
complete to compare against.

## Goals (measurable)

1. **Full coverage:** a full run (`--all`) processes both v1 categories and
   produces a record for every non-refurbished product the store exposes
   through its public product endpoints. Products that cannot be assigned to
   a category are stored with `category = "unclassified"` and counted in the
   run summary. None are silently dropped.
2. **Change detection:** every run compares its results against the last
   successful completed run and writes one `change_events` row per new
   product, new variant, new category, or changed price/availability.
   Two identical runs in a row produce zero `IS_NEW_*` events.
3. **Auditability:** every run has a `scrape_runs` row with start time, end
   time, status, counts per category, and error count. Any flagged item can
   be traced to the run that found it.
4. **Deployability:** `git push` to Railway starts the service. `GET /health`
   returns 200 within one second when the service is up.
5. **Politeness:** the scraper never exceeds the rate limit defined in
   `architecture.md` and never bypasses access controls.

## Core user flow

The primary user is the internal operator (or a scheduled job) that keeps our
inventory aligned with the store.

1. The operator triggers a run, either with `python run.py --category printers`,
   `python run.py --all`, or `POST /scrape` with `{"category": "printers"}`
   or `{"category": "all"}`.
2. The scraper checks that no other run is active for the same category. If
   one is, it returns the existing run's ID instead of starting a second run.
3. The scraper discovers the store's collections and maps each one to one of
   the v1 internal categories (printers, filaments) using the mapping defined in that category's
   module.
4. For each collection, the scraper fetches every product page (paginated).
   Products with "refurbished" in their title, handle, or tags are dropped
   here and never fetched in detail.
5. For each remaining product, the scraper fetches the full product record,
   then fills any gaps (breadcrumbs, spec tables, compatibility notes, video
   URLs) from the product's HTML page only where the JSON lacks them.
6. Each product is normalized into typed models with prices stored in minor
   units, and a content hash is computed for each product and each variant.
7. The diff engine compares the normalized results with the database and
   writes change events.
8. The run is marked `completed` (or `partial` / `failed`), and its summary is
   returned.
9. The operator reads results with `GET /catalog`, using filters such as
   `?new_only=true`, `?since=<ISO timestamp>`, or `?category=filaments`.

## Feature list by category

**Discovery and fetching**
- Discover collections from the store and map them to the v1 categories (printers, filaments)
- Paginate through each collection's product list
- Fetch full product detail (JSON first, HTML fallback where needed)
- Retry failed requests with exponential backoff; honor `Retry-After`
- Rate-limit all outbound traffic from one shared client

**Extraction**
- Metadata: title, handle, product ID, URL, breadcrumbs, collection, vendor,
  product type, tags
- Content: body HTML, clean text, specification tables, compatibility notes
- Variants: IDs, option values (color, material, spool type, and so on), SKU,
  barcode, price, compare-at price, currency, availability, weight, dimensions
- Media: full-resolution image URLs, gallery order, video URLs
- Timestamps: store `created_at`, store `updated_at`, and scraper
  `scraped_at` (UTC)

**Change detection**
- Diff against the last completed run
- Flags: `IS_NEW_PRODUCT`, `IS_NEW_VARIANT`, `IS_NEW_CATEGORY`
- Secondary events: `PRICE_CHANGED`, `AVAILABILITY_CHANGED`

**Access**
- CLI runner (`run.py`)
- FastAPI service (`main.py`) with `GET /health`, `POST /scrape`,
  `GET /catalog`
- API key on all endpoints except `/health`

## In scope (v1)

- Full extraction and diffing for **3D Printers** and **Filaments**
- Registration of only these two categories. No other category module,
  stub, or registry entry exists in v1.
- SQLite persistence on a mounted volume (`DATA_DIR`)
- Dockerfile and Procfile for Railway
- Local run and test instructions in `README.md`
- Unit tests that run offline against saved fixtures

## Out of scope (v1). Do not build these.

- AMS, Accessories, Spare Parts, Laser & Crafting, Maker's Supply, and
  Bundles. Deferred to later versions, with no files, stubs, or registrations
  in v1.
- Any end-user web UI, dashboard, or HTML report
- Notifications (email, Slack, webhooks). Flags are readable through the API
  only.
- Scheduling inside the app. Scheduling is handled by Railway cron or an
  external caller that hits `POST /scrape`.
- Checkout, cart, login, customer accounts, or any authenticated store area
- Headless browsers (Playwright, Selenium) and proxy rotation
- Storefront API tokens or any private Shopify API. Public endpoints only.
- Price history charts or analytics
- Scraping any store other than `eu.store.bambulab.com`
- Migration to PostgreSQL. SQLite is the v1 store.
- Bypassing CAPTCHAs, bot challenges, or login walls. If the store blocks us,
  the scraper stops and reports it.

## Success criteria (each must be verifiable)

- [ ] `python run.py --category printers` completes against live store and
      writes a `scrape_runs` row with status `completed`.
- [ ] `python run.py --category filaments` completes the same way.
- [ ] Running the same category twice with no store changes produces zero
      `IS_NEW_*` events on the second run.
- [ ] Adding a product fixture (test) and rerunning produces exactly one
      `IS_NEW_PRODUCT` event for it and one `IS_NEW_VARIANT` per extra variant.
- [ ] No product with "refurbished" in its title, handle, or tags appears in
      `GET /catalog`.
- [ ] `GET /health` returns `{"status": "ok"}` with HTTP 200.
- [ ] `POST /scrape` without a valid API key returns 401.
- [ ] `docker build` succeeds and the container starts and serves `/health`.
- [ ] `pytest` passes fully offline.
- [ ] Deployed on Railway with a persistent volume, and the database survives
      a redeploy.

## Assumptions to verify before coding (tracked in progress-tracker.md)

- The store exposes Shopify's public `/products.json`,
  `/collections.json`, and `/collections/<handle>/products.json` endpoints
  without authentication.
- The 8 categories map to Shopify collections. The exact handles are not
  yet confirmed.
- The store does not block requests from Railway's datacenter IP ranges.
- `robots.txt` and the store's terms permit the planned access pattern.
