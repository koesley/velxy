# VELXTRIA V50 — Project Singularity

V50 unifies the existing evidence → proposal → owner approval → delivery → measurement workflow into a workspace-scoped, read-only command center and JSON export. It does not execute actions, change customer records, or guarantee outcomes.

1. Back up your existing SQLite database and retain `VELXTRIA_DATA_DIR`.
2. Open the `velxy-main` directory in Cursor.
3. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`.
4. Run `python portal.py` and visit `http://127.0.0.1:8878/singularity-v50`.
5. Run `python -m unittest discover -p "test_*.py"` to validate your environment.

Known limitations: bounded historical samples, manual approvals and execution, no browser certification or production security audit.
