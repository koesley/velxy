# VELXTRIA V5.4 — Project Overmind (local incremental upgrade)

This is an incremental upgrade of the uploaded V5.3 project, **not** a new autonomous AI model.

## Added
- Mission-specific next-step guidance and proposal status counts.
- Editable pending customer follow-up drafts (10–1200 characters), saved to the existing mission-action table.
- Approval and rejection audit events and a mission-specific activity timeline.
- Repeated scans do not regenerate a proposal for the same contact or site within the same mission, even after the draft is edited.
- More spacious mission-action buttons and refined purple controls.

## Install safely
1. Stop the local server. Back up the **actual active database** (and any SQLite WAL/SHM files if present).
2. Extract this ZIP. The ZIP does **not** include a database.
3. Point the new version at the same existing data directory via `VELXTRIA_DATA_DIR`, or carefully retain the existing database in the new `velxy-main` folder after a full backup. Do not overwrite your old database with a blank one.
4. Run locally from `velxy-main` in PowerShell:

```powershell
$env:VELXTRIA_LOCAL_STUDIO='1'
$env:VELXTRIA_DEPLOYMENT_MODE='local'
$env:VELXTRIA_REQUIRE_PERSISTENCE='0'
Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
$env:VELXTRIA_DATA_DIR = "$HOME\Downloads\VELXTRIA_V5_3_Mission_Execution\velxy-main"
python portal.py
```

If your original data directory differs, change `VELXTRIA_DATA_DIR` to that actual folder. Verify the path before starting.

Open `/missions`, then choose **Open mission-specific proposals and execution**. Existing approved/executed actions remain intact. Edit only pending drafts.

## Safety and scope
No external emails, purchases, website publishing, background scheduling, or paid APIs. Existing CRM records remain account-scoped, not company-isolated. Outcomes are not inferred from completed tasks. Test with fictional customers first.
