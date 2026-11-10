# VELXTRIA V52 — Project Titan Intelligence

## What changed
- New read-only `/titan-intelligence` dashboard with an executive briefing and rule-based findings.
- New `/titan-intelligence.json` export with evidence references, recommended human review actions, and limitations.
- Added workspace navigation link and responsive styles.
- Added `test_titan_intelligence_v52.py` for isolation, read-only guarantees, escaping, and evidence.

## Upgrade
1. Back up your existing SQLite database and preserve `VELXTRIA_DATA_DIR`.
2. Extract the entire ZIP and open `velxy-main` in Cursor.
3. Start in local studio mode:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

4. Open `http://127.0.0.1:8878/titan-intelligence` after signing in.

## Limits
This is deterministic rule-based analysis, not a generative AI integration. Reports are based on bounded snapshots of existing modules and may omit records. The system cannot infer causation, guarantee profit, or autonomously change business records. Production security and browser verification are separate tasks.
