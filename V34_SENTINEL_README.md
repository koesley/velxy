# VELXTRIA V34 — Project Sentinel

This upgrade adds an operator-controlled automated regression runner, checksum-verified JSON evidence, read-only SQLite integrity/foreign-key diagnostics, and a new `/sentinel` dashboard.

## Run

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python sentinel_v34.py run
python sentinel_v34.py report
python sentinel_v34.py health
python portal.py
```

Visit `http://127.0.0.1:8878/sentinel` after signing in. Preserve `VELXTRIA_DATA_DIR` and back up your existing database before upgrades. Reports are written to `VELXTRIA_DATA_DIR/sentinel_evidence/`, not included in the release ZIP.

## Safety boundaries

- Only the local command-line operator can trigger test execution; the web dashboard is read-only.
- The runner uses a fixed allowlist of bundled `test_*_v*.py` modules; no user-supplied commands, scripts, or arbitrary paths are accepted.
- Test data uses a temporary directory separate from the customer SQLite database.
- Evidence JSON includes a SHA-256 checksum for tamper detection (not an authenticated digital signature).
- A passing run is not production certification. Browser E2E tests, restore rehearsals, and independent security audits are still required.
- V33 manual release approvals remain unchanged; Sentinel does not deploy or automatically approve releases.
