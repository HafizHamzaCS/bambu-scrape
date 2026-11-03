# AI Workflow Rules

These are direct instructions to the coding agent (Antigravity, or any other
agent working in this repo). They are not suggestions.

## 1. Start-of-session procedure

1. Read `AGENTS.md` at the repo root.
2. Read all six files in `context/` in this order: `project-overview.md`,
   `architecture.md`, `code-standards.md`, `ai-workflow-rules.md`,
   `ui-context.md`, `progress-tracker.md`.
3. Read `context/specs/00-build-plan.md` if it exists, then read the spec file
   for the current unit if one exists.
4. State the current phase, current goal, and the next unit in one short
   paragraph before writing any code.
5. If `progress-tracker.md` and the repo disagree (for example, the tracker
   says a unit is complete but its files are missing), stop and record the
   mismatch under Open Questions. Do not guess which is right.

## 2. Scope rules

- **Work on one unit at a time.** A unit is defined in the build plan. Do not
  start unit N+1 until unit N passes its verification checklist and has been
  closed in `progress-tracker.md`.
- **No speculative changes.** Do not add features, abstractions, flags, or
  configuration options that the current unit does not require. "Might be
  useful later" is not a reason.
- **No scope creep into out-of-scope items.** The list in
  `project-overview.md` under "Out of scope" is binding. If a task seems to
  require an out-of-scope item, stop and record it as an Open Question.
- **Build only the two v1 categories (printers and filaments).** Do not
  create, stub, or register any other category unless a unit explicitly says so.
- **Do not add a dependency unless the current unit lists it.** If a needed
  package is missing from the unit's Dependencies list, stop and record it as
  an Open Question.

## 3. Splitting work

- If a unit would require changing more than about 6 files or more than about
  400 lines of new code, split it into two sub-steps, complete the first, run
  its verification, and record the split in `progress-tracker.md`.
- Never mix these in one change: database schema changes, HTTP client
  changes, and category-specific parsing. Each is its own step.
- Schema changes are always a new numbered migration file. Never edit an
  existing migration that has been applied in any environment.

## 4. Missing or ambiguous requirements

Do not resolve ambiguity by picking the option that is easiest to code. Use
this procedure:

1. If the question is answerable from `context/` files, answer it from them
   and cite the file and section.
2. If it is not answerable from `context/`, add it to **Open Questions** in
   `progress-tracker.md` with: the question, the options considered, and what
   you did provisionally. Use the format:
   `- [ ] Q: <question> | Options: A, B | Provisional: A (reason)`
3. If the provisional choice is safe to proceed with, proceed and keep the
   provisional choice isolated (one function or one config value) so it can be
   changed easily.
4. If the choice is not safe to proceed with (for example, it affects what
   data is stored or whether requests comply with `robots.txt`), stop and ask
   the operator. Do not write code past that point.

Known open questions at project start are listed in `progress-tracker.md`.
Do not silently resolve them. Resolve them only through a recorded decision.

## 5. Files that must not be touched without explicit instruction

| File or folder | Rule |
|---|---|
| `context/*.md` (except progress-tracker.md) | Edit only when an implementation change makes a documented fact wrong. Record the change in progress-tracker.md Session Notes |
| `context/specs/*` | Read-only during implementation. Change a spec only by explicit operator instruction |
| `migrations/*.sql` already applied | Never edit. Add a new migration |
| `Dockerfile`, `Procfile` | Change only in the deployment unit or when explicitly told |
| `requirements.txt` | Add or pin a package only in the unit that lists it |
| `tests/fixtures/**` | Re-capture only through the documented capture script. Do not hand-edit |
| `config.py` default values | Change only with a recorded Architecture Decision |
| Any `.env` file, Railway settings, or secrets | Never create, read aloud, print, or commit. Reference variable names only |

## 6. Live-store rules

- Live requests to `eu.store.bambulab.com` happen only in two places: the
  U0 fixture-capture step and an explicit manual `run.py` invocation by the
  operator. Do not add live calls to tests or to any automated step.
- Before any live request in a session, confirm `robots.txt` allows the path.
- Use the configured rate limit even for manual testing. Never bypass it,
  never parallelize beyond the configured concurrency, and never loop
  retries outside the shared client.
- If the store returns a bot challenge, a CAPTCHA, a login page, or a 403,
  stop. Record it in progress-tracker.md Session Notes and Open Questions. Do
  not try alternate headers, cookies, or IP tricks.

## 7. Keeping docs in sync

- After every meaningful implementation change, update
  `progress-tracker.md`: move items between Completed, In Progress, and Next
  Up, and add a dated line to Session Notes.
- If the change alters a stack choice, a boundary, a storage field, an
  invariant, or a code convention, update the matching `context/` file in the
  same change, and add an entry to Architecture Decisions in
  `progress-tracker.md`.
- If a README or CLI help text describes a command that changed, update it in
  the same change.

## 8. Verification checklist (required before closing any unit)

Run every item. Record the result in progress-tracker.md. If an item fails,
the unit is not closed.

- [ ] `ruff check .` passes with no errors
- [ ] `ruff format --check .` passes
- [ ] `mypy --strict` passes on the package
- [ ] `pytest` passes with no network access (confirm no live calls by running
      with network disabled, or by confirming respx is active)
- [ ] Every item in the unit's spec Verification checklist is checked
- [ ] No new file exceeds about 400 lines
- [ ] No `print()` in library code; no secrets in the diff (search the diff for
      `KEY`, `TOKEN`, `SECRET`, `sqlite3`, and `.env`)
- [ ] Money fields are integers; no `float` touches a price
- [ ] `progress-tracker.md` updated and unit marked complete or partial with a
      reason

## 9. Reporting back to the operator

- At the end of each unit, report in this order: what changed (files), what
  was verified (checklist results), what is still open (Open Questions added),
  and the next unit.
- Keep the report short. Do not paste whole files. Name the files.
- If a unit could not be completed, say exactly which checklist item failed
  and why. Do not mark it complete.

## 10. Things the agent must never do

- Commit or push secrets, API keys, Railway tokens, or the SQLite database.
- Run scraping against the live store in a loop or in parallel with another
  scrape.
- Remove or weaken the refurbished filter, the rate limiter, the robots.txt
  check, or the API key check to make a test pass.
- Mark a test as skipped or xfail to get a green build.
- Replace a failing fixture-based test with a live-call test.
- Rewrite a context file to match code that violates it, without first
  recording the decision.
