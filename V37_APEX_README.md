# VELXTRIA V37 — Project Apex

A major authenticated HTTP integration-testing milestone built on V36 Titanium.

## Run

```powershell
python apex_v37.py run
python apex_v37.py report
python portal.py
```

The read-only dashboard is at `/apex` after signing in. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local` to run the portal locally. Keep the existing `VELXTRIA_DATA_DIR` and back up the SQLite database before upgrading.

## Tested journey

The CLI starts a temporary local portal and database, registers a test user, logs in, checks CSRF enforcement, creates a business workspace, creates and publishes an inventory application, saves a record, loads eleven business pages, and attempts cross-workspace access and record insertion. Test reports are saved in `VELXTRIA_DATA_DIR/titanium_evidence/` with SHA-256 integrity checks. No customer records are changed by the journey test.

## Limitations

This is authenticated HTTP integration testing, **not** browser automation. It does not validate JavaScript, visual layouts, accessibility, payment flows, production hosting, or all business actions. Test report checksums are not independent attestations. Run an independent security review and browser-driven customer testing before public deployment.
