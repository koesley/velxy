# VELXTRIA V69 — scheduled HubSpot synchronization

V69 adds a GitHub Actions scheduler that runs hourly and processes due daily/weekly policies from the V68 Sync Control Center. The worker requires persistent PostgreSQL and uses the existing V67 server-side HubSpot private app token. It imports **read-only** contacts and never writes to HubSpot.

## Activation

1. In GitHub repository Settings → Secrets and variables → Actions, configure the following **repository secrets**: `VELXTRIA_DATABASE_URL`, `VELXTRIA_SUPABASE_URL`, `VELXTRIA_SUPABASE_SERVICE_KEY`, `VELXTRIA_V67_HUBSPOT_TOKEN`, `VELXTRIA_V69_WORKSPACE_ID` (the **only** workspace permitted to import from this HubSpot account). Use the same database and credentials as your Render app. Do not commit them.
2. Ensure GitHub Actions is enabled for the repository, and that your GitHub plan supports scheduled workflows. The workflow `.github/workflows/v69-scheduled-sync.yml` runs hourly (UTC). You can trigger it manually from the Actions tab.
3. In VELXTRIA, set a workspace's sync policy to **daily** or **weekly**. The first automatic run becomes due after the selected interval. **Off** disables it.
4. Inspect the V68 dashboard's sync history and GitHub Actions logs for results.

## Limitations

- **Not self-service OAuth**: all workspaces share the one HubSpot private app token configured by the administrator. Do **not** enable this feature for unrelated customer workspaces; it could import the administrator's HubSpot contacts into those workspaces. Use only in a single-organization deployment until per-workspace OAuth is built.
- A scheduler run may be delayed by GitHub Actions. Failed due slots are not automatically retried until the next cadence.
- Each run imports up to 100 contacts. This is not a full incremental synchronization.
- V68 manual imports remain available.
- No external email sending, CRM writes, or autonomous actions are performed.
