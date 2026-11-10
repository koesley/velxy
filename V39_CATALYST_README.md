# VELXTRIA V39 — Project Catalyst

Major upgrade: actual Chromium-driven authenticated customer workflow, isolated HTTP journey, local recovery rehearsal, fail-closed 24-hour evidence preflight, and protected workspace dashboard.

## Run

```powershell
python -m pip install playwright
python -m playwright install chromium
python catalyst_v39.py run
python portal.py
```

Local studio: set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, preserve `VELXTRIA_DATA_DIR`, and back up your existing SQLite database before upgrading. Dashboard: `/catalyst`.

All active tests use disposable local data. The browser workflow exercises registration/login with Chromium, creates a workspace and an application, publishes it, stores a record, checks mobile/desktop layout, and checks anonymous access. It is not a full usability or security audit.

Evidence uses local SHA-256 checksums, which detect accidental edits but do not authenticate the test operator. A passed preflight is NOT production certification. Real pilot hosting, billing, independent security review, and customer validation remain open.
