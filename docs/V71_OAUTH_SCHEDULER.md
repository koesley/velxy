# VELXTRIA V71 — per-workspace OAuth scheduling

V71 connects the V68 daily/weekly schedule preferences to the V70 per-workspace HubSpot OAuth connections. A GitHub Actions job runs hourly and imports contacts only for workspaces that have an active V70 OAuth connection. V69's old hourly shared-token schedule has been disabled.

## Activate

1. Set up HubSpot OAuth as described in `docs/V70_HUBSPOT_OAUTH.md`, and connect each workspace from the V70 dashboard.
2. In GitHub repository **Settings → Secrets and variables → Actions**, configure `VELXTRIA_DATABASE_URL`, `VELXTRIA_SUPABASE_URL`, `VELXTRIA_SUPABASE_SERVICE_KEY`, `VELXTRIA_V70_HUBSPOT_CLIENT_ID`, `VELXTRIA_V70_HUBSPOT_CLIENT_SECRET`, `VELXTRIA_V70_HUBSPOT_REDIRECT_URI`, and `VELXTRIA_V70_ENCRYPTION_KEY`. These must match the running Render app and its stable Fernet encryption key.
3. In each connected workspace, set a **daily** or **weekly** preference in the V68 Sync Control Center.
4. Ensure GitHub Actions is enabled. Workflow `V71 Workspace OAuth Sync` checks hourly; GitHub schedules are best-effort and may be delayed.
5. Review sync history in the V68 dashboard. Failed attempts are logged without revealing tokens or contacts.

## Safety and limits

- The scheduler uses **only** V70 workspace OAuth connections. It does not use the shared V67 HubSpot private-app token or the V69 workspace allowlist.
- Disconnecting a workspace prevents new scheduled runs. Already-running imports may finish.
- Atomic due-slot claims avoid duplicate scheduled claims, but a crash after a claim can skip that interval; there is no retry queue.
- Each run imports up to 100 HubSpot contacts (first page), deduplicating by email. It does not provide complete pagination, two-way synchronization or provider-side writes.
- Scheduled sync requires persistent PostgreSQL and a stable encryption key. Test against a real HubSpot sandbox before broad production rollout.
