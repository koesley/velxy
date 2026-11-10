# VELXTRIA V49 — PROJECT OMNISCIENCE

## Upgrade safely

1. Back up your current SQLite database and the whole `VELXTRIA_DATA_DIR` directory.
2. Extract this project into a **new** folder; do not replace or delete your data directory.
3. Keep your existing `VELXTRIA_DATA_DIR` environment setting.
4. From `velxy-main`, run:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Open `http://127.0.0.1:8878/omniscience` after logging in.

## New features

- Append-only work evidence entries with a date, duration, and narrative.
- Estimated versus actual effort on each milestone.
- Remaining estimated hours, overdue and over-estimate warnings.
- Historical actual/estimated median ratio from completed milestones, applied only with at least three comparable samples and capped at 0.5x–3x.
- Workspace-specific JSON export (`/omniscience.json`).
- Owner/editor-only work logging; viewer read-only; other workspaces inaccessible.

## Caveats

- Manually logged hours are not independently verified.
- The report reads up to the latest 5,000 work entries per workspace; totals may be incomplete beyond this limit.
- No edit/delete of logged entries is available. Check entries before saving.
- Capacity weeks are rough estimates, not delivery promises.
- This is not a financial forecasting or autonomous execution engine.
- Local SQLite studio mode only. Do not expose this prototype directly to the public Internet.

## Testing

```powershell
python -m unittest discover -p "test_*.py" -q
python apex_v37.py run
```

Browser tests, independent security review and production deployment remain outstanding.
