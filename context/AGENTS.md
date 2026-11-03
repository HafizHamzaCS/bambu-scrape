# Agent Entry Point: Bambu Lab EU Catalog Scraper

This file is read first in every session. Before doing anything else, read the
following files in this order:

1. `context/project-overview.md`: what we are building, goals, scope, and
   what is out of scope
2. `context/architecture.md`: stack, folder ownership, storage model, diff
   engine, and invariants (hard rules)
3. `context/code-standards.md`: naming, typing, HTTP, database, and test
   conventions
4. `context/ai-workflow-rules.md`: how to work, what to touch, what to ask
5. `context/ui-context.md`: JSON, CLI, and log output formats
6. `context/progress-tracker.md`: current phase, current goal, next unit, open
   questions

If `context/specs/` exists, read `00-build-plan.md` and the spec for the current
unit.

## Standing rules

- Work on one unit at a time, as defined in the build plan.
- Do not add dependencies, features, or endpoints that the current unit does
  not list.
- Never bypass rate limits, robots.txt, bot challenges, or access controls.
- Never commit or print secrets, the API key, or the SQLite database.
- Record every unanswered question in `context/progress-tracker.md` under
  Open Questions. Do not guess.
- After each meaningful change, update `context/progress-tracker.md`.
- If a change alters the architecture, scope, or standards documented in a
  context file, update that file in the same change and log it in the tracker's
  Architecture Decisions.
- A unit is closed only when its verification checklist passes (see
  `context/ai-workflow-rules.md`, section 8).

## Quick start for a new session

Say: "Read AGENTS.md and context/progress-tracker.md, then resume from the
Current Goal. Summarize the phase and goal before writing code."
