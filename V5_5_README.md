# VELXTRIA V5.5 — Project Ascendancy

This upgrade builds on V5.4 without bundling, replacing, or resetting a database.

## Delivered
- Mission-specific five-step deterministic plan, based on actual recorded mission state.
- Separate, owner-entered outcome evidence for executed actions. Draft preparation, contact, response, and objective achievement are distinct.
- Duplicate identical outcome entries are ignored.
- Persistent account-level business guidance notes (not an AI model and not per-company).
- Repeat Verify progress clicks no longer generate duplicate verification events after the first successful verification.
- Existing V5.4 proposals, history, approval gates, CRM, and Site Studio remain.

## Important limits
- This is not an autonomous AI agent. No LLM, paid API, background scheduler, email delivery, or independent outcome validation is included.
- The outcome form accepts owner-reported observations; the system cannot verify whether a customer was actually contacted or responded.
- The Mark complete button still means owner-declared workflow closure, not independently validated business success.
- Business guidance is account-scoped, not company-isolated.

## Safe local upgrade
1. Stop the old VELXTRIA server with Ctrl+C.
2. Back up your **working** V5.4 `portal.sqlite3` before starting this version.
3. Extract the ZIP to a new folder. Do not delete your old folder.
4. In PowerShell, cd into the extracted `velxy-main` folder.
5. Point `VELXTRIA_DATA_DIR` at the **folder that contains the working database**, e.g. `$env:VELXTRIA_DATA_DIR="$HOME\Downloads\VELXTRIA_V5_3_Mission_Execution\velxy-main"` if that is still your data location. Confirm the path first.
6. Set `$env:VELXTRIA_LOCAL_STUDIO="1"`, `$env:VELXTRIA_DEPLOYMENT_MODE="local"`, `$env:VELXTRIA_REQUIRE_PERSISTENCE="0"`; clear an unused remote DB env var if appropriate.
7. Run `python portal.py` and open `http://127.0.0.1:8878/` in the same browser profile.
8. Open Gerate → Mission-specific proposals and execution. Look for `ASCENDANCY / EVIDENCE-BASED MISSION PLAN` and `Outcome evidence`.

## Database changes
Two new tables are created if missing: `vx55_outcomes` and `vx55_preferences`. No destructive schema migration is performed. Existing mission records are preserved when the app is pointed at the correct working database.
