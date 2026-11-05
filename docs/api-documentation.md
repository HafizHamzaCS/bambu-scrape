# Bambu Lab EU Catalog Scraper & Service — API & Architecture Documentation

This document describes the API architecture of the Bambu Lab EU Catalog Scraper and Diff Engine. It covers:
1. **The Scraper Service REST API** — The HTTP interface provided by the service (`main.py`) for health monitoring, triggering catalog syncs, and querying catalog data.
2. **The Bambu Lab EU Storefront Data Endpoints** — How the scraper discovers and extracts data from `https://eu.store.bambulab.com`.
3. **Execution Lifecycle & Invariants** — How background tasks, rate limiting, and diff detection operate.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    Client["Client / External Scheduler / Railway Cron"] -->|HTTP + X-API-Key| FastAPI["FastAPI Gateway (main.py)"]
    FastAPI -->|Check Liveness| Health["GET /health (No Auth)"]
    FastAPI -->|POST /scrape (202 Accepted)| BgTask["Asyncio Background Task"]
    FastAPI -->|Query| DB[("SQLite Database ($DATA_DIR/catalog.sqlite3)")]
    
    subgraph ScraperEngine ["Scraper & Diff Engine"]
        BgTask -->|Rate Limiter (1 req/s, max 2 conn)| BaseScraper["BambuBaseScraper (base_scraper.py)"]
        BaseScraper -->|Collection Discovery| StorefrontCat["Bambu Lab Collections (/en/collections/{handle})"]
        BaseScraper -->|Single-Page Deep Crawl| StorefrontProd["Product Pages (/en/products/{handle})"]
        BaseScraper -->|Parse JSON-LD + Specs + Media| Normalizer["Payload Normalizer"]
        Normalizer -->|Detect Changes| DiffEngine["Diff Engine (models.ChangeFlag)"]
        DiffEngine -->|Atomic Transaction| DB
    end
```

---

## 2. Scraper Service REST API Reference

The service is built on **FastAPI** and served with **Uvicorn** inside a Docker container on Railway.

### 2.1 Base URL & Environment Ports
- **Local Dev:** `http://127.0.0.1:8000`
- **Railway Production:** `https://<your-service-name>.up.railway.app` (Port injected via `$PORT`)

### 2.2 Global Authentication Scheme
All endpoints except `GET /health` require the `X-API-Key` HTTP request header:
```http
X-API-Key: <your-configured-SCRAPER_API_KEY>
```
- Keys are compared in constant time using `secrets.compare_digest` to prevent timing attacks.
- If `SCRAPER_API_KEY` is not set at service startup, the application raises `RuntimeError` and refuses to start (fail-fast security invariant).

### 2.3 Canonical Response Envelope
All API responses follow a strict 3-key JSON envelope (`snake_case`):
```json
{
  "data": {},
  "meta": {},
  "error": null
}
```
- `data`: The requested payload, or `null` if an error occurred.
- `meta`: Operational metadata (pagination, counts, `run_id`, `generated_at`). Empty object `{}` if inapplicable.
- `error`: `null` on success, or an object `{"code": "SNAKE_CASE_CODE", "message": "human-readable text"}` on error.

---

### 2.4 Endpoints Specification

#### 1. Liveness & Health Check
Open unauthenticated endpoint used by Railway and Docker container probes.

- **Route:** `GET /health`
- **Auth:** None
- **Response `200 OK`:**
```json
{
  "status": "ok"
}
```

---

#### 2. Trigger Catalog Scrape
Dispatches an asynchronous catalog scrape in the background.

- **Route:** `POST /scrape`
- **Auth:** Required (`X-API-Key`)
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "category": "printers"
}
```
*Supported `category` values in v1:* `"printers"`, `"filaments"`, `"all"`.

- **Success Response `202 Accepted`:**
```json
{
  "data": {
    "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "status": "running",
    "category": "printers"
  },
  "meta": {
    "started_at": "2026-11-02T19:45:00Z"
  },
  "error": null
}
```

- **Conflict Response `409 Conflict` (Active Run in Progress):**
If a scrape for the specified category is already executing, the request is rejected immediately:
```json
{
  "data": null,
  "meta": {
    "active_run_id": "8a3ef2c1-1234-4567-89ab-cdef01234567"
  },
  "error": {
    "code": "run_conflict",
    "message": "A scrape for category 'printers' is already in progress"
  }
}
```

- **Invalid Category Response `400 Bad Request`:**
```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "invalid_category",
    "message": "Category 'accessories' is not supported in v1"
  }
}
```

---

#### 3. Inspect Run Status
Check execution progress, metrics, and error logs of a scrape run.

- **Route:** `GET /runs/{run_id}`
- **Auth:** Required (`X-API-Key`)
- **Success Response `200 OK`:**
```json
{
  "data": {
    "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "category": "printers",
    "status": "completed",
    "products_seen": 9,
    "variants_seen": 18,
    "error_count": 0,
    "error_summary": null
  },
  "meta": {
    "started_at": "2026-11-02T19:45:00Z",
    "finished_at": "2026-11-02T19:45:34Z"
  },
  "error": null
}
```

---

#### 4. Query Synchronized Catalog
Retrieve normalized products and variant listings from the local SQLite database.

- **Route:** `GET /catalog`
- **Auth:** Required (`X-API-Key`)
- **Query Parameters:**
  - `category` *(optional)*: `"printers"` | `"filaments"`
  - `active_only` *(optional, default `true`)*: Return only currently available items
  - `limit` *(optional, default `50`)*: Number of items per page
  - `offset` *(optional, default `0`)*: Pagination offset
- **Success Response `200 OK`:**
```json
{
  "data": [
    {
      "product_id": 8531193200988,
      "category_key": "printers",
      "handle": "a1-mini",
      "title": "Bambu Lab A1 mini 3D Printer",
      "vendor": "Bambu Lab",
      "url": "https://eu.store.bambulab.com/en/products/a1-mini",
      "is_active": true,
      "scraped_at": "2026-11-02T19:45:20Z",
      "spec_table": [
        ["Body", "Build Volume(W*D*H)", "180*180*180 mm³"],
        ["Toolhead", "Hot End", "All-Metal"],
        ["Nozzle", "Stainless Steel"],
        ["Max Hot End Temperature", "300 °C"]
      ],
      "media": [
        {
          "id": "791594850481876992",
          "url": "https://store.bblcdn.eu/s8/default/bdad2d286ff64b61a355d99d71495e93/A1_mini.jpg",
          "type": "image"
        }
      ],
      "variants": [
        {
          "variant_id": 599117891173982220,
          "title": "Bambu Lab A1 mini 3D Printer - A1 mini Combo",
          "sku": "599117891173982220",
          "price": {
            "amount_minor": 27900,
            "currency": "EUR"
          },
          "compare_at_price": {
            "amount_minor": 29900,
            "currency": "EUR"
          },
          "available": true,
          "image_url": "https://store.bblcdn.eu/s8/default/97fb57895cd04ddcae3dddd5f93d098f/A1_mini_C.jpg"
        }
      ]
    }
  ],
  "meta": {
    "total_count": 9,
    "limit": 50,
    "offset": 0
  },
  "error": null
}
```

---

#### 5. Query Change Events (Diff Feed)
Fetch changes detected across scrape runs.

- **Route:** `GET /changes`
- **Auth:** Required (`X-API-Key`)
- **Query Parameters:** `run_id`, `category`, `event_type` (`IS_NEW_PRODUCT`, `PRICE_CHANGED`, etc.)
- **Success Response `200 OK`:**
```json
{
  "data": [
    {
      "event_id": 142,
      "run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "event_type": "PRICE_CHANGED",
      "category_key": "printers",
      "product_id": 8531193200988,
      "variant_id": 599117891173982220,
      "detail": {
        "old_price_minor": 29900,
        "new_price_minor": 27900,
        "currency": "EUR"
      },
      "detected_at": "2026-11-02T19:45:22Z"
    }
  ],
  "meta": {
    "count": 1
  },
  "error": null
}
```

---

## 3. How the Storefront Extraction Pipeline Works

The Bambu Lab EU store (`eu.store.bambulab.com`) is a modern, headless **Next.js App Router** frontend served over AWS CloudFront and Cloudflare edge caches (`store-fe.bblcdn.eu`), rather than a standard Shopify Liquid storefront.

### 3.1 Storefront Challenges & Solutions

#### A. GeoIP Redirection
- **Challenge:** Non-European requests receive an HTTP `302 Found` redirect to `https://us.store.bambulab.com/`.
- **Solution:** 
  1. All requests append `?skr=yes` (Skip Redirect).
  2. The production service is deployed in Railway's European region (`europe-west3` Frankfurt or `europe-west4` Amsterdam).

#### B. Rate Limiting & Politeness Invariants
- Outbound requests share a single async token-bucket limiter in `base_scraper.py`:
  - Rate limit: Minimum **1.0 second** between request starts.
  - Concurrency: Maximum **2 concurrent requests** (`asyncio.Semaphore(2)`).
  - Timeouts: 10s connect, 20s read.
  - Retries: Up to 4 attempts on network errors and 5xx/429 status codes, with exponential backoff and jitter.

---

### 3.2 Category Collection Discovery

The scraper accesses the collection listing URLs:
- **Printers Collection:** `https://eu.store.bambulab.com/en/collections/3d-printer?skr=yes`
- **Filaments Collection:** `https://eu.store.bambulab.com/en/collections/bambu-lab-3d-printer-filament?skr=yes`

#### Extracted Collection Fields:
The collection page embeds the initial catalog state as JSON inside the page HTML (`productList`):
```json
{
  "id": "8531193200988",
  "seoCode": "a1-mini",
  "name": "Bambu Lab A1 mini 3D Printer",
  "lowerPrice": 179,
  "price": 189,
  "currency": "EUR",
  "mediaFiles": [
    "https://store.bblcdn.eu/s8/default/bdad2d286ff64b61a355d99d71495e93/A1_mini.jpg"
  ],
  "isFilament": false,
  "lowerPriceSkuId": "599117891173982224"
}
```
The scraper uses `seoCode` to construct the single-page product URL for detail extraction.

---

### 3.3 Deep Single-Page Product Extraction

To capture full hardware specifications, technical parameters, rich descriptions, and complete variant matrices, the scraper visits `https://eu.store.bambulab.com/en/products/{seoCode}?skr=yes`.

The extraction uses a 3-tier parsing strategy:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Product Page: /en/products/{handle}?skr=yes                           │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 1: Schema.org JSON-LD (<script type="application/ld+json">)       │
│  ├── ProductGroup (ID, Title, Description, Brand)                      │
│  └── hasVariant Array (SKUs, Names, InStock Availability, Offers,     │
│       Current Price, Strikethrough Compare-At Price, Variant Images)   │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 2: HTML Specification Table (<table> ... </table>)               │
│  └── 18+ Technical Parameters (Build Volume, Nozzle, Max Temps,       │
│       Speeds, Accelerations, Filament Compatibility, Dimensions)       │
├────────────────────────────────────────────────────────────────────────┤
│ Tier 3: React Server Components Wire Stream (self.__next_f.push)       │
│  ├── Full High-Resolution Media Gallery (mediaFiles array)             │
│  ├── Product Property Lists & Variant Attributes                       │
│  └── Order & Logistics Terms (orderInfo)                               │
└────────────────────────────────────────────────────────────────────────┘
```

#### Why This Multi-Tier Design?
1. **Zero Flakiness:** Schema.org JSON-LD is standard structured data intended for search engines. It guarantees that product IDs, prices, and variant SKUs remain accurate even if frontend CSS classes change.
2. **Deep Technical Specifications:** Next.js renders the full hardware comparison table as a semantic HTML `<table>`, enabling robust extraction of printer capabilities.
3. **High-Res Media Coverage:** The RSC stream provides direct CDN URLs for all photo angles, dimension diagrams, and marketing graphics without watermarks or downsampling.

---

## 4. The Diff Engine & Change Detection

On each scrape run, normalized product records are compared against the SQLite store:

| Event Type | Condition Triggered |
|---|---|
| `IS_NEW_PRODUCT` | `product_id` is not present in the `products` table. |
| `IS_NEW_VARIANT` | `variant_id` is new, and its parent product previously existed. |
| `IS_NEW_CATEGORY` | `category_key` appears for the first time. |
| `PRICE_CHANGED` | Stored `price_minor` or `compare_at_minor` differs from current run. |
| `AVAILABILITY_CHANGED` | Item transitions between in-stock (`available=1`) and out-of-stock (`available=0`). |
| **Deactivation (`is_active=0`)** | An existing item is absent from the current run. **Rule:** Deactivation occurs **only** on runs with status `completed`. Incomplete runs (`partial` or `failed`) never deactivate items. |

### Money Representation Rule
All monetary values are strictly represented as integers in minor units (cents):
- €179.00 -> `17900`
- €24.99 -> `2499`
Floating-point arithmetic is banned to prevent rounding discrepancies.
