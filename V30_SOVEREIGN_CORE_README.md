# VELXTRIA V30 — Sovereign Core

This is a **local-only** reliability milestone built on V29. It adds `/sovereign-core`, a read-only release gate with module table presence, SQLite integrity, and deployment mode checks. Browser end-to-end and independent security review are **explicitly blocked**, not assumed passed.

## Run

Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`; preserve `VELXTRIA_DATA_DIR`; run `python portal.py`; open `http://127.0.0.1:8878/sovereign-core`.

## Regression suite

Run `python -m unittest discover -p 'test_*_v*.py'` from `velxy-main`. Tests may require local dependencies. Run against an isolated test directory, never production data.

## Important

No database restoration, automatic deployment, or production certification is implemented. Back up your database before upgrading. A passing schema check does not prove correctness or tenant isolation in every legacy module.
