# VELXTRIA V5.2 — Mission Control

## Added
- `/missions` navigation and private Mission Control page.
- Persistent mission goals, objective text, pause/resume, manual scan, verification and completion.
- Mission scan reuses V5.1 operator rule-based analysis and prepares proposals for review at `/operator`.
- Verification reads existing operator execution logs and records an auditable snapshot; results are account-wide and **not proof of revenue growth**.
- Mission-specific activity history, workflow progress indicators, responsive dark-violet design, improved button spacing.
- Existing V5.1 workspace, website studio, operator and database schema retained.

## Install safely
1. Back up `portal.sqlite3` and any other local data. Do not overwrite the original database.
2. Extract the ZIP, open `velxy-main` in Cursor. If extracting to a different folder, set `VELXTRIA_DATA_DIR` to the folder containing your existing `portal.sqlite3`, or use your current project folder after backup.
3. Use your existing local environment: `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, `VELXTRIA_REQUIRE_PERSISTENCE=0`; do not set `VELXTRIA_DATABASE_URL` for local SQLite.
4. Run `python portal.py` and open `http://127.0.0.1:8878/missions`.
5. Create a mission, Run operator scan, review and approve relevant proposals at `/operator`, Execute approved internal actions, return to Mission Control and Verify progress.

## Current limitations
- Missions do **not** automatically interpret open-ended objectives, schedule background jobs, or autonomously change websites. Scans are manual, operator decisions require approval, and execution is limited to internal review tasks.
- Mission progress reflects workflow checkpoints, not business performance. Execution counts are account-wide; they may include actions unrelated to the mission.
- User account is the current data boundary; individual companies inside one account are not isolated by this feature.
- No paid APIs or new dependencies. Do not deploy as a mature unattended business operator.
