# Offline Test Fixtures

These fixtures provide deterministic offline HTTP responses for unit tests using `respx`.
Per project rules, fixtures are recorded from real store responses and are never hand-edited or invented.

## Required Fixtures

### Printers (`tests/fixtures/printers/`)
| Fixture File | Source Endpoint / URL | Capture Date | Status |
|---|---|---|---|
| `collections_printers.json` | `https://eu.store.bambulab.com/en/collections/3d-printer?skr=yes` | 2026-11-02 | Captured (9 3D printers, live catalog component state) |
| `product_printer_detail.json` | `https://eu.store.bambulab.com/en/products/a1-mini?skr=yes` | 2026-11-02 | Captured (A1 mini with 2 combo variants, 7 media assets, 18 specs) |
| `product_printer_page.html` | `https://eu.store.bambulab.com/en/products/a1-mini?skr=yes` | 2026-11-02 | Captured (Full product page HTML with schema.org & specs table) |

### Filaments (`tests/fixtures/filaments/`)
| Fixture File | Source Endpoint / URL | Capture Date | Status |
|---|---|---|---|
| `collections_filaments.json` | `https://eu.store.bambulab.com/en/collections/bambu-lab-3d-printer-filament?skr=yes` | 2026-11-02 | Captured (12 filament families) |
| `product_filament_detail.json` | `https://eu.store.bambulab.com/en/products/pla-basic-filament?skr=yes` | 2026-11-02 | Captured (PLA Basic with 43 color/spool variants) |
| `product_filament_page.html` | `https://eu.store.bambulab.com/en/products/pla-basic-filament?skr=yes` | 2026-11-02 | Captured (Full product page HTML with schema.org) |

### General Catalog Discovery
| Fixture File | Source Endpoint / URL | Capture Date | Status |
|---|---|---|---|
| `collections_all_page1.json` | `https://eu.store.bambulab.com/collections.json?limit=250&page=1` | Pending | PENDING LIVE CAPTURE |

## Capture Instructions for Operator (EU Region / Egress)
1. Run from an EU-based IP (or proxy configured with approval) to prevent Cloudflare GeoIP 302 redirects to `us.store.bambulab.com`.
2. Fetch with polite desktop `User-Agent` and minimum 1.0s delay between requests.
3. Save raw unmodified responses into the matching paths above.
