# VELXTRIA V72 — paginated CRM imports and integration health

V72 expands V70 manual and V71 scheduled HubSpot OAuth imports to a bounded maximum of 10 pages × 100 contacts = 1,000 contacts per run. Duplicate contacts are skipped by case-insensitive email within each workspace. Only the configured HubSpot OAuth connection for that workspace is used.

The **Integration Health V72** page displays connection presence, access-token expiry status, daily/weekly schedule, next due time and the last recorded scheduled sync outcome.

## Operational limitations

- Pagination is bounded, not a complete historical backfill if a HubSpot account contains more than 1,000 contacts.
- Imports are read-only to HubSpot. VELXTRIA lead additions are committed as part of the workspace database transaction.
- No exponential retry or full queue processing has been added; GitHub Actions timing remains best effort.
- A token shown as `refresh_due` can still be refreshed at the next import; this is not necessarily an authentication failure.
- The V72 health page shows the current workspace only; it does not expose other tenants' credentials or status.
- A failed page fetch prevents the import transaction from completing, but earlier network pages may already have been fetched.
