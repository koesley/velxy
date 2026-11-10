# VELXTRIA V36 — Project Titanium

V36 adds an operator-only **recovery rehearsal** and **real HTTP smoke test**, plus a read-only `/titanium` evidence dashboard. It preserves V35 and all prior modules.

## Run

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python titanium_v36.py all
python titanium_v36.py report
python portal.py
```

Visit http://127.0.0.1:8878/titanium after signing in and joining a workspace.

`restore` requires an existing `portal.sqlite3` under `VELXTRIA_DATA_DIR`. It takes a consistent SQLite online backup, restores **only into a temporary directory**, compares table counts, checks integrity and foreign keys, and deletes temporary copies. It never restores over the live database. `smoke` starts the real portal on localhost with a temporary data directory and checks public pages and anonymous access to protected modules. It does not use real customer accounts.

Reports are stored in `VELXTRIA_DATA_DIR/titanium_evidence`. Checksums detect accidental modifications but do not attest independent trust. Browser-driven authenticated journeys, disaster recovery operations, penetration testing, and production deployment checks remain unverified. Back up existing data before upgrades.
