# VELXTRIA V51 — Project Ascendancy

V51 consolidates the business improvement journey into a single guided customer page with six stages, context-aware actions, stage/priority filters, experiment progress, JSON and CSV exports, and workspace authorization. It preserves all V50 modules and existing data. No background actions or approval bypasses are introduced.

## Upgrade
1. Back up your existing SQLite database and the project before replacing code.
2. Extract this ZIP and open `velxy-main` in Cursor.
3. Preserve `VELXTRIA_DATA_DIR` and your existing environment settings.
4. In PowerShell: `$env:VELXTRIA_LOCAL_STUDIO="1"; $env:VELXTRIA_DEPLOYMENT_MODE="local"; python portal.py`
5. Open `http://127.0.0.1:8878/ascendancy-v51` after signing in.

## Tests
Run `python -m unittest test_ascendancy_v51.py -q` or `python -m unittest discover -p 'test_*.py' -q`.

## Limitations
The command center is read-only. Actual edits, owner approvals, and delivery management occur in existing modules. The report inherits sampling limits of V50. This is not production security certification or an autonomous profit engine.
