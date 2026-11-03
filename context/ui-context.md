# UI Context

## Scope of the interface

v1 has **no end-user web UI**. There is no dashboard, no HTML page, and no
frontend build step. The only human-facing surfaces are:

1. **JSON responses** from the FastAPI service (`main.py`)
2. **Plain-text CLI output** from `run.py`
3. **Log lines** written to stdout (read in the Railway log viewer)

This file defines the visual and format decisions for those three surfaces so
that the agent never has to invent a format. If a dashboard is added in a
later version, it gets its own section here, and its tokens are defined
before any markup is written.

## 1. JSON output conventions (API surface)

**Naming:** `snake_case` keys everywhere. Never camelCase, even though
Shopify uses snake_case too, so there is no conversion step.

**Envelope:** every response has this shape:

```json
{
  "data": {},
  "meta": {},
  "error": null
}
```

- `data`: the payload, or `null` on error
- `meta`: paging, counts, `run_id`, `generated_at`. Use `{}` if nothing applies
- `error`: `null` on success, or `{"code": "SNAKE_CASE_CODE", "message": "text"}`

**Timestamps:** ISO 8601 UTC with a trailing `Z`, for example
`2026-11-02T10:51:00Z`. Milliseconds are omitted in API output.

**Money:** an object, never a bare number or string:

```json
{ "amount_minor": 34900, "currency": "EUR" }
```

`amount_minor` is the integer in cents. The client does the formatting.

**Change flags:** exact string values from the `ChangeFlag` enum:
`IS_NEW_PRODUCT`, `IS_NEW_VARIANT`, `IS_NEW_CATEGORY`, `PRICE_CHANGED`,
`AVAILABILITY_CHANGED`. Do not add lowercase or alias forms.

**Booleans:** real JSON `true` and `false`. Never `"true"` strings, never 0 or
1 in API output (SQLite's 0 and 1 are converted in `database.py`).

**Null handling:** omit nothing. A missing optional field is `null`. An empty
list is `[]`, never `null`.

**Status codes:**

| Code | Used for |
|---|---|
| 200 | Successful read (`GET /health`, `GET /catalog`) |
| 202 | Scrape accepted and running in background (`POST /scrape`) |
| 400 | Invalid category or malformed body |
| 401 | Missing or wrong `X-API-Key` |
| 404 | Unknown `run_id` |
| 409 | A run for this category is already running (body includes the active `run_id`) |
| 500 | Unexpected internal error (never includes a stack trace in the response) |

**Error codes** (snake_case strings in `error.code`):
`invalid_category`, `unauthorized`, `run_conflict`, `run_not_found`,
`internal_error`.

## 2. CLI output conventions (`run.py`)

Plain text. No ANSI colors by default. If the environment variable
`FORCE_COLOR` is set, colors may be added, and they must be disabled when
`NO_COLOR` is set (https://no-color.org). Colors are never required to read
the output.

**Status labels** (fixed-width, left-aligned, 9 characters including
brackets). These are the only status tokens the CLI prints:

| Token | Meaning |
|---|---|
| `[OK     ]` | Category or item processed without error |
| `[NEW    ]` | A `IS_NEW_*` event was written |
| `[CHANGED]` | A `PRICE_CHANGED` or `AVAILABILITY_CHANGED` event was written |
| `[SKIP   ]` | Item skipped on purpose (refurbished, robots.txt, unmapped collection) |
| `[WARN   ]` | Retry happened, or a partial result |
| `[FAIL   ]` | Error that stopped a category or the run |

**Summary block** printed at the end of each run, in this exact order and
layout:

```
Run      : <run_id>
Category : <key> (<label>)
Status   : <completed|partial|failed>
Started  : <ISO UTC>
Finished : <ISO UTC>
Products : <n> seen, <n> new, <n> updated
Variants : <n> seen, <n> new
Skipped  : <n> refurbished, <n> other
Errors   : <n>
```

Labels are left-aligned to the width of `Finished` (8 characters followed by
` :`). Numbers are plain integers, with no thousands separators.

## 3. Log line format (stdout, JSON lines)

One JSON object per line. Required keys: `ts` (ISO UTC), `level`, `logger`,
`msg`. Optional context keys: `run_id`, `category`, `url_path`, `status`,
`attempt`, `duration_ms`. Never include `sku`, `barcode`, or any secret in
logs unless it is needed to debug a specific item, and then only at DEBUG.

## 4. Layout and component rules for any future UI (reference only)

If a dashboard is added later, these rules apply. Do not build any of this in
v1.

- Single column. Maximum content width 960 px. Padding 16 px on mobile and 24
  px on desktop.
- Typography: system UI font stack (`ui-sans-serif, system-ui, -apple-system,
  "Segoe UI", Roboto, sans-serif`). One size scale: 12, 14, 16, 20, 24 px.
- Color: a single neutral gray ramp plus one accent for "new" items. The accent
  token is `--color-new` and is used only for `IS_NEW_*` flags.
- Radius: 6 px for cards and inputs, 9999 px for badges.
- Tables for catalog lists, with sticky header row and horizontal scroll on
  narrow screens. No card grids for catalog data.
- Icons: none in v1.
- Accessibility: WCAG 2.1 AA contrast. Every status is conveyed by text, never
  by color alone.

## 5. Source of truth for the strings the user sees

Every human-readable message from the API or CLI comes from a constant in one
place: `models.py` for error messages and `run.py` for CLI labels. Do not
write inline English messages in route handlers or in category modules.
