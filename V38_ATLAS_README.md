# VELXTRIA V38 — Project Atlas

## Major changes
- Guided launch center (`/atlas`) for authorized local workspaces.
- Customer journey stages with links to existing modules and evidence-based progress.
- Release evidence dashboard: authenticated HTTP tests, HTTP smoke, recovery rehearsal, and real Chromium browser smoke.
- Optional Playwright browser runner with disposable server/database, mobile and desktop checks.
- Explicit SKIP when Playwright or Chromium is unavailable; never misrepresents an unrun browser test as a pass.
- Read-only release evidence UI; operator-only test commands.

## Start
Keep your existing `VELXTRIA_DATA_DIR` and back up SQLite before upgrading.

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```
Open `http://127.0.0.1:8878/atlas`.

## Browser testing (optional)
```powershell
python -m pip install playwright
python -m playwright install chromium
python atlas_v38.py browser
python atlas_v38.py report
```
The browser runner creates a temporary data directory and launches a separate local portal. It does not modify your existing database. Browser tests are not equivalent to a complete security audit or production validation.

## Existing checks
```powershell
python apex_v37.py run
python titanium_v36.py all
python sentinel_v34.py run
```

## Known limits
- Browser smoke checks registration, login, protected navigation, and mobile/desktop rendering; they do not cover every business workflow.
- Release evidence is local and checksum-protected, not independently attested.
- Production hosting, payments, and full security assessment remain unverified.
