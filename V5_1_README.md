# VELXTRIA V5.1 — Operator execution + visual refinement

## What's new
- Violet/ice-gradient headings, subtle text treatment, consistent button spacing, responsive action rows, and improved keyboard focus styles.
- On `/operator`, approved proposals now offer **Execute approved internal actions**.
- Execution creates individual CRM follow-up review tasks (up to 25), overdue invoice verification tasks (up to 25), or a finance reconciliation checklist task. All tasks are internal. It **does not** send messages, alter invoice balances, edit the public website, or spend money.
- A separate execution verification log records what was created. Repeating the same proposal is blocked.
- All existing V5 routes, approvals, manual records, and website studio remain in place.

## Run locally
1. Back up the original `portal.sqlite3` and any local data directory before switching folders. **Do not overwrite an existing database.** If using a separate extracted folder, set `VELXTRIA_DATA_DIR` to your existing data folder so the same records remain available.
2. Extract this archive and open its `velxy-main` folder in Cursor.
3. Keep the same local-only environment settings used for V5, including `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, `VELXTRIA_REQUIRE_PERSISTENCE=0`, and no `VELXTRIA_DATABASE_URL`.
4. Run `python portal.py`; open `http://127.0.0.1:8878/operator`.
5. Scan, approve, then click **Execute approved internal actions**. Inspect `/workspace` task queue and the operator execution log.
6. For a richer test, create sample leads, invoices or income/expenses first in `/workspace` and scan again.

## Safety and limitations
- The operator is **not** a continuously running autonomous agent. Scans are manual.
- Internal actions require an explicit second click after approval.
- Approval still creates the original summary task, and execution creates specific internal tasks. This preserves V5 behavior.
- Scope is the signed-in user account, not yet separate company-specific workspaces. Use test data; don't deploy publicly as a mature multi-tenant autonomous system.
- No paid AI services or extra Python packages required.
