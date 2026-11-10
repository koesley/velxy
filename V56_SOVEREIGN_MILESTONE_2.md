# Project Sovereign V56 — Milestone 2: Evidence Intelligence Council

## Scope
Adds a bounded deterministic council for revenue, expense, conversion and data-quality analysis. Each evaluation is stored with its input evidence hash; older evaluations are labeled stale after source changes. Supports JSON history export and workspace authorization. No LLM, remote connector, autonomous agent, or external execution is implemented.

## Routes
`GET /sovereign-council-v56?w=<workspace>` — UI
`GET /sovereign-council-v56.json?w=<workspace>` — tenant-scoped JSON history
`POST /sovereign-council-v56` — CSRF-protected analysis with `workspace` and `objective`.

## Database
Non-destructive, idempotent CREATE TABLE `sv56_council_runs` and index `sv56_council_scope`; existing data retained. Back up SQLite and preserve `VELXTRIA_DATA_DIR` before upgrade. Rollback code by restoring the prior package; the additional table is inert in older versions and can remain in the DB.

## Security
Existing authenticated portal sessions, CSRF validation and workspace roles apply. Read requires membership; running analysis requires owner/editor. Findings are computed from workspace-scoped metrics only; HTML is escaped. No external side effects.

## Limitations and next milestone
The five analysis roles are deterministic functions, not AI agents. This release does not provide predictive confidence, external APIs, role-specific tool execution, or full end-to-end browser verification. Next: typed business graph and ingestion-quality provenance with conflict resolution, then a supervised connector action interface.

## Test
`python -m unittest test_sovereign_intelligence_v56 -q`
