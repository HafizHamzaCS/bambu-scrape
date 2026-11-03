# Spec: Unit U0 — Discovery and Fixtures

## Goal
Confirm that the Bambu Lab EU store's public Shopify endpoints behave as expected, identify real collection handles for printers and filaments, and capture initial offline fixtures.

## Design
Discovery executes against `https://eu.store.bambulab.com` honoring strict politeness rules: a custom, non-impersonating desktop User-Agent, minimum 1-second delay between requests, and zero bypass techniques. If `robots.txt` disallows required paths or an access barrier (403, CAPTCHA, challenge) is encountered, the process halts immediately and logs to `progress-tracker.md`. Responses are saved as pristine JSON fixtures under `tests/fixtures/` and documented in `tests/fixtures/README.md`. No scraper application code is authored in this unit.

## Implementation
1. **Robots.txt audit:** Fetch `https://eu.store.bambulab.com/robots.txt` and verify access rules for `/collections/`, `/products/`, and `*.json`. Document status in Session Notes.
2. **Collection discovery:** If network is accessible, fetch `/collections.json?limit=250&page=1` (and subsequent pages if present). Parse collection titles and handles to isolate 3D Printers and Filaments handles.
3. **Product listings capture:** For identified printer and filament collection handles, fetch `/collections/{handle}/products.json?limit=250&page=1`. Save raw responses as fixtures.
4. **Product detail capture:** For one printer and one filament product, fetch `/products/{handle}.json`. Save raw responses as fixtures.
5. **Fixtures documentation:** Create `tests/fixtures/README.md` cataloging file paths, source URLs, status codes, and capture timestamps.
6. **Decisions & Tracker updates:** Record mapped collection handles in `progress-tracker.md` Architecture Decisions.

## Dependencies
- Standard library `urllib.request` / `json` or python script for one-off capture
- Network connectivity to `https://eu.store.bambulab.com`

## Verification checklist
- [ ] `robots.txt` checked and findings recorded in `progress-tracker.md` Session Notes
- [ ] Collection handles for printers and filaments identified and recorded in Architecture Decisions
- [ ] Fixtures directory structure created (`tests/fixtures/printers/` and `tests/fixtures/filaments/`)
- [ ] `tests/fixtures/README.md` created with URL and capture date for each fixture (or marked PENDING LIVE CAPTURE if network unavailable)
- [ ] No application scraper code authored
- [ ] Status codes and any `Retry-After` headers documented
