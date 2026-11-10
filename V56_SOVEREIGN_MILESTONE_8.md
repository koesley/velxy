# VELXTRIA V56 Sovereign — Milestone 8: Organizational Memory

## Scope
Adds `sovereign_memory_v56.py`, an append-only workspace-scoped decision and outcome register integrated into the existing Milestone 7 source. UI: `/sovereign-memory-v56`; JSON: `/sovereign-memory-v56.json?w=<workspace-id>`.

## Features
- Human-authored decisions, observations, lessons, and outcomes with validated text fields.
- Outcomes must reference an existing **succeeded** execution job in the same workspace; the strategy ID is inherited from the job.
- Entries can reference a strategy and up to 20 explicitly supplied source IDs via Python API. The current web form exposes job references, not arbitrary source-ID entry.
- Corrections create a new entry linked by `supersedes_id`; original entries remain available in full timeline export.
- Workspace-scoped literal substring search; role enforcement through existing `sovereign_v56.access`.
- Historical JSON timeline includes execution jobs and events; no external writes or model training.

## Database migration
`sovereign_memory_v56.setup(c)` creates `sv56_memory_entries`, `sv56_memory_events`, and indexes if absent. Called by `portal.db()` in local SQLite mode. Existing tables are not dropped or modified. **Back up your SQLite DB before launching.** Roll back the source by restoring the previous package; leave the new tables intact or restore the pre-upgrade DB backup if a full data rollback is required.

## Security and limitations
- Local studio only (`VELXTRIA_LOCAL_STUDIO=1`, no remote DB).
- Existing login and CSRF checks apply to routes. Writes require owner/editor; viewer may read.
- Human-reported outcomes are **not independently verified**, and do not establish causality or profit.
- No automatic outcome extraction, semantic/vector retrieval, external connectors, deletion/retention policy, background workers, or AI learning yet.
- Supersession is one direct replacement per entry. For a later correction, supersede the latest entry.
- Browser end-to-end, production deployment, full legacy suite, concurrency, and PostgreSQL are not verified.

## Test command
`python -m unittest test_sovereign_memory_v56 -q`

## Launch
```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```
Visit `http://127.0.0.1:8878/sovereign-memory-v56`.

## Next milestone
M9: Business Future Simulator — bounded multi-period what-if projections, explicit assumptions, uncertainty and evidence snapshots.
