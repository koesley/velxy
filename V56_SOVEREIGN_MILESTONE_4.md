# VELXTRIA V56 — Sovereign Milestone 4: Sync & Reconciliation

## Scope
Adds a local, human-triggered synchronization adapter between V56 imported monthly metrics and the typed Digital Twin. It is not a remote provider integration or background synchronization service.

## Files
- `sovereign_sync_v56.py`: setup, preview, apply, status, HTML UI.
- `test_sovereign_sync_v56.py`: regression and security tests.
- `sovereign_twin_v56.py`: adds `metric_period` node type.
- `portal.py`: database setup, authenticated GET/JSON and CSRF-protected POST routes, navigation.

## Use
1. Back up your existing SQLite data directory (including `VELXTRIA_DATA_DIR`, if set).
2. Start the app in local SQLite studio mode.
3. Import valid CSV through `/sovereign-v56`.
4. Open `/sovereign-sync-v56`, inspect the preview, and click **Apply unambiguous records**.
5. Inspect `/sovereign-twin-v56` and JSON export.

## Schema changes
Additive, non-destructive `sv56_sync_runs`, `sv56_sync_links`, and `sv56_sync_conflicts` tables and indexes. No existing rows or columns are modified. Sync creates `metric_period` twin nodes with `sv56_import:<import_id>` provenance. Repeated apply is idempotent for linked periods.

## Security
All read/write operations enforce existing workspace membership and editor/owner write access. The route uses existing session and CSRF validation. Output is HTML-escaped. Conflicting imports are not silently merged or overwritten.

## Limitations
- Local manually uploaded CSV only, not a provider connector or background scheduler.
- No reconciliation resolution UI; conflicting months remain excluded until reviewed using a future explicit resolution mechanism.
- Imported facts create provenance-linked period nodes; no causal business relationships are inferred.
- No full browser/end-to-end or production verification has been performed.

## Verification
`python -m unittest test_sovereign_sync_v56 -q` — 58 tests passed, including inherited tests. Python compilation passed. The complete legacy test suite was not executed.

## Rollback
Stop the server, restore the backed-up database and prior version source. Additive tables can be left in place when rolling back code. Do not delete tables on a live system without a verified backup and migration plan.

## Next milestone
Conflict-resolution decisions with audit trail and source precedence rules, followed by a bounded opportunity engine consuming reconciled Digital Twin data.
