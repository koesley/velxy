# VELXTRIA V45 — Project Neural Network

## Upgrade
Back up the current SQLite database. Extract the project, keep your existing `VELXTRIA_DATA_DIR`, and launch in local studio mode:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Open `http://127.0.0.1:8878/neural-network`. Use the `w` query parameter to select a workspace. Export JSON using the link on the page.

## What changed
- Read-only experiment outcome classification and quality flags.
- Goal-level pattern aggregation without mixing metric units.
- Conservative opportunity queue requiring repeated completed observations.
- Tenant-scoped JSON evidence export and escaped HTML rendering.
- No schema changes, automated business mutations, model training, or external API calls.

## Testing
`python -m unittest discover -p "test_*.py"`

**Limitations:** Correlation is not causation. Outcomes do not imply guaranteed improvements, financial performance, or autonomous decisions. Browser/production/security certification remain outstanding.
