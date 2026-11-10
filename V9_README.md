# VELXTRIA V9 — Project Constellation

A coordinated mission dossier combining three read-only account-scoped Sovereign V8 diagnostics. Each dossier saves the raw source evidence and explicit recommendations; no invented external outcomes, autonomous emails, or paid APIs.

## Install
1. Back up the working `portal.sqlite3` database.
2. Extract this ZIP separately; do not replace your database.
3. Set `VELXTRIA_DATA_DIR` to the verified existing data directory containing your current database.
4. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`.
5. Run `python portal.py` and open `http://127.0.0.1:8878/constellation`.

V9 also repairs the V8 `/sovereign` POST handler placement so its diagnostic buttons work correctly. The new dossier is deterministic, not LLM-directed agent autonomy.
