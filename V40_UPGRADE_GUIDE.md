# VELXTRIA V40 — Genesis Reborn

This release retains the existing portal and all prior business modules. It focuses on local SQLite maintenance and connection lifecycle reliability rather than introducing a new AI feature.

## New capabilities

- `persistent.ManagedSQLiteConnection` closes connections after `with` blocks. A failed block rolls back before closing. Existing code that explicitly calls `close()` still works.
- Compatible SQLite indexes are created idempotently for sessions, reports, deliveries, memberships, applications, and records. Tables/columns that do not exist are skipped.
- `genesis_reborn_v40.py check` reads the database without modifying it and reports quick integrity, foreign-key violations, page utilization, and installed V40 indexes.
- `genesis_reborn_v40.py optimize` adds compatible indexes and updates SQLite query statistics with `ANALYZE`. It does not VACUUM, delete records, or restore backups.
- `/genesis-reborn` provides a local-studio-only, admin-only, read-only health dashboard.

## Upgrade steps

1. Stop VELXTRIA and make a verified backup of the entire `VELXTRIA_DATA_DIR` directory, including `portal.sqlite3` and its WAL/SHM files if present. Prefer an SQLite online backup while the server is running, or stop the server first.
2. Extract the archive into a new directory; do not overwrite your data directory. Preserve environment settings and secrets.
3. Run `python -m unittest discover -p "test_*.py"`.
4. Start the portal with your usual local-studio environment settings.
5. Run `python genesis_reborn_v40.py check` and inspect the result. For an external data directory, set `VELXTRIA_DATA_DIR` or use `--db PATH`.
6. Optionally, after backup and during a maintenance window, run `python genesis_reborn_v40.py optimize`.
7. Visit `/genesis-reborn` as an administrator in local studio mode.

## Limits

- This does not make the product production-ready or solve all resource warnings in older modules and tests. Direct `sqlite3.connect()` calls elsewhere can still leak if not closed.
- SQLite-only maintenance is intentionally unavailable in remote PostgreSQL mode.
- Quick integrity checks are not substitutes for backups or a complete `PRAGMA integrity_check` and a tested disaster recovery procedure.
- No Playwright/Chromium browser test was executed as part of the V40 validation.
