# Bambu Lab EU Catalog Scraper & Diff Engine

A robust, modular, and type-safe catalog synchronization service and diff engine for the Bambu Lab EU store (`https://eu.store.bambulab.com`), featuring SQLite persistence, FastAPI HTTP service, and background catalog diff tracking.

---

## 1. Project Overview

- **Language & Runtime:** Python 3.12
- **Framework:** FastAPI with Uvicorn
- **Storage:** SQLite3 (`$DATA_DIR/catalog.sqlite3`)
- **Containerization:** Docker (`python:3.12-slim`), non-root execution (`appuser`), persistent volume support
- **Target Platform:** [Railway](https://railway.app) (European region recommended)

---

## 2. Local Setup & Testing

### Prerequisites
- Python 3.12+
- Git

### Installation
```bash
# Clone the repository
git clone https://github.com/Hassan-Buger/bambu-scrape.git
cd bambu-scrape

# Create and activate a virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt
```

### Running Tests and Quality Checks
```bash
# Run offline unit tests
pytest -v

# Run lint checks
ruff check .

# Check formatting
ruff format --check .

# Run strict type checking
mypy --strict config.py models.py main.py categories/__init__.py tests/test_config.py tests/test_api.py
```

### Running Locally
```bash
# Copy example environment variables
cp .env.example .env

# Set SCRAPER_API_KEY in .env or via terminal:
export SCRAPER_API_KEY="your-local-secret-key"

# Run Uvicorn dev server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Test health endpoint:
```bash
curl http://127.0.0.1:8000/health
# Response: {"status":"ok"}
```

---

## 3. Deploying to Railway (Step-by-Step)

### Step 1: Connect GitHub Repository
1. Log in to [Railway](https://railway.app).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select `Hassan-Buger/bambu-scrape` (or your repository fork).

### Step 2: Set Deployment Region (Critical)
> [!IMPORTANT]
> The Bambu Lab EU store (`eu.store.bambulab.com`) enforces GeoIP redirection. Traffic originating from outside Europe may be redirected via HTTP 302 to `us.store.bambulab.com`.
1. In your Railway Service settings, navigate to **Settings** -> **Region**.
2. Select **Europe West** (e.g. Frankfurt or Amsterdam).

### Step 3: Attach Persistent Volume
The SQLite catalog database must persist across container restarts and deployments:
1. Under your service in Railway, go to the **Volumes** tab.
2. Click **Add Volume**.
3. Set the Mount Path to `/app/data` (matches `DATA_DIR`).
4. Volume size: 1 GB (sufficient for sqlite catalog storage).

### Step 4: Configure Environment Variables
In Railway -> **Variables**, add the following environment variables:

| Variable | Recommended Value | Description |
|---|---|---|
| `SCRAPER_API_KEY` | *(Generate a secure random string)* | Master API Key required for authenticated sync/scrape calls (`X-API-Key` header). Service will refuse to start if omitted. |
| `DATA_DIR` | `/app/data` | Path to persistent volume mount directory where `catalog.sqlite3` is stored. |
| `BASE_URL` | `https://eu.store.bambulab.com` | Base storefront URL. |
| `RATE_LIMIT_INTERVAL_S` | `1.0` | Minimum seconds between outbound requests (rate limit governor). |
| `MAX_CONCURRENCY` | `2` | Maximum concurrent HTTP connections. |
| `REQUEST_TIMEOUT_CONNECT_S` | `10.0` | Connection timeout in seconds. |
| `REQUEST_TIMEOUT_READ_S` | `20.0` | Read timeout in seconds. |
| `MAX_RETRIES` | `4` | Maximum retry attempts on network errors and 5xx/429 status codes. |

### Step 5: Generate Public Domain
1. In Railway, go to **Settings** -> **Networking** -> **Public Networking**.
2. Click **Generate Domain** (e.g., `bambu-scrape-production.up.railway.app`).

### Step 6: Verify Live Service
Verify your service health check without authentication:
```bash
curl https://<your-railway-domain>/health
# Output: {"status":"ok"}
```

Verify authenticated API requests using the `X-API-Key` header:
```bash
curl -H "X-API-Key: <your-configured-SCRAPER_API_KEY>" https://<your-railway-domain>/health
```

---

## 4. Architecture Invariants
- **Money is integer minor units:** All monetary values are processed as integers in cents (e.g., `€24.99` -> `2499`) without floating-point inaccuracies.
- **Fail-fast authentication:** Server startup fails immediately if `SCRAPER_API_KEY` is not defined in the environment.
- **Non-root container execution:** Docker runs under the unprivileged `appuser` (UID 1000) with write permissions restricted to `/app/data`.
- **Zero secrets stored in code:** All secrets and credentials are read strictly from environment variables at runtime.
