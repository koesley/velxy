# VELXTRIA V12 — Project Omnipotence (Core Intelligence foundation)

This release builds on V11 and adds `/omnipotence` in local SQLite studio mode.

## Implemented
- Persistent per-account workflow definitions with an allowlisted set of read-only business checks.
- Explicit preview, approval and rejection states with audit logs.
- Customer, Nexus, Genesis and mission counts where a compatible user-scoped table is available.
- No third-party network access or arbitrary AI-generated code execution.

## Not implemented yet
- Ollama-based tool selection, branching, retries, outbound webhooks, marketplace, external connectors or payment automation.
- The workflow system is a safe, manual foundation, **not** a fully autonomous AI agent.

## Run
1. Back up your working `portal.sqlite3` before changing versions.
2. Extract this archive; open `velxy-main` in Cursor.
3. Set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, `VELXTRIA_REQUIRE_PERSISTENCE=0`, and set `VELXTRIA_DATA_DIR` to the directory containing your **existing** `portal.sqlite3`.
4. Run `python portal.py`, sign in, visit `http://127.0.0.1:8878/omnipotence`.
5. Create a workflow using `app_count,summary`; prepare a preview, inspect, approve or reject.

The V12 feature uses only local SQLite. Existing schema and customer records are not intentionally modified except for creating the two new `v12_` tables and their indexes.
