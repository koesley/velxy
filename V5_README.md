# VELXTRIA V5 — Local Business Operator prototype

## What is implemented
- Authenticated `/operator` page with navigation link.
- Account-scoped operational scans of existing CRM, invoice and manual ledger data.
- Persistent, deduplicated pending proposals with evidence.
- Approval creates a real internal task in the existing Business Workspace task queue.
- Rejection and activity audit history.
- No outbound email, website publishing, payments, autonomous background processing, or paid AI APIs.

## Start safely
1. Back up the current project and your local `portal.sqlite3` database. The ZIP contains no user database.
2. Stop the old server. Extract V5 and open `velxy-main` in Cursor.
3. For local development, run in PowerShell (paste only commands, not Markdown tags):

    $env:VELXTRIA_LOCAL_STUDIO="1"
    $env:VELXTRIA_DEPLOYMENT_MODE="local"
    $env:VELXTRIA_REQUIRE_PERSISTENCE="0"
    Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
    python portal.py

4. Sign in and visit http://127.0.0.1:8878/operator
5. Click Analyze records and prepare actions. Approve one proposal, then verify the new task under Business Workspace.

## Limits and next milestones
This is an **operator foundation**, not a continuously running autonomous AI. A background scheduler, per-company isolation (beyond account scoping), real tool integrations, permissions, idempotent execution and monitoring require additional development and testing. Keep it local; do not deploy to production without a security review.
