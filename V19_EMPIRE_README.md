# VELXTRIA V19.1 — PROJECT EMPIRE: Workspace Pilot

This release adds **local SQLite-only** business workspaces, one-time 24-hour invitation codes, owner/editor/viewer roles, and tenant-scoped shared workspace records. Existing V1–V18 modules and their data remain unchanged and account-scoped; they have **not** been migrated to tenant isolation. Do not treat this as a production multi-tenant SaaS.

## Setup
1. Back up `portal.sqlite3` before upgrading. Do not copy a bundled database: none is included.
2. Set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, `VELXTRIA_REQUIRE_PERSISTENCE=0`, and `VELXTRIA_DATA_DIR` to the directory containing your **existing** database.
3. Run `python portal.py` and visit `http://127.0.0.1:8878/empire`.
4. Create a workspace. Create a one-time invite for another account. Test owner/editor/viewer access.

## Limits
- Invite codes are displayed only when created. Share securely, not publicly. No email invitation sending.
- No payments, subscriptions, app marketplace, production tenant migration, or external hosting deployment are included.
- Local prototype only; conduct full security and browser testing before handling real customer data.
