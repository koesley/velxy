# VELXTRIA V4.1 — local website studio prototype

This is a **local-only, opt-in prototype**, not a production website builder or AI agent. Existing payments and reporting code are retained.

## Start (Windows PowerShell)

From the extracted `velxy-main` directory:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
$env:VELXTRIA_REQUIRE_PERSISTENCE="0"
Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
python portal.py
```

If your app is normally started with `python runner.py`, use that command instead of `python portal.py`. Follow the address printed by the server. Sign in with a local test account and click **Site Studio** on the dashboard.

**Safety:** Use a fresh local folder and test accounts; do not copy `.env` secrets into it. Keep `VELXTRIA_LOCAL_STUDIO` unset on Render. This prototype stores drafts in local SQLite only, and cannot publish websites publicly. It does not migrate production databases. Company data isolation is implemented for these draft routes only; the existing business modules are still user-scoped, not company-scoped. Do not use this for real customer data.

## Implemented
- Create company workspace records linked to the signed-in owner.
- Edit headline, page text, and color theme.
- Private owner-only draft preview, HTML-escaped content.
- CSRF-protected edits, ownership checks, no new dependencies or paid services.

## Not implemented
Public hosting, custom domains, AI chat, agent actions, multi-user roles, site builder blocks, profit optimization, production hardening.
