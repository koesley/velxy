# VELXTRIA V74 — interrupted retry recovery and reliability metrics

The V71 hourly OAuth scheduler now reclaims V73 retry jobs left in `running` for over 30 minutes. Recovery is compare-and-swap guarded and counts the interrupted attempt against the existing maximum of three retry attempts. Recoverable jobs return to `pending` after the configured backoff; exhausted jobs are marked `exhausted`.

The V72 Integration Health page now includes V74 workspace-scoped counts of pending, running, exhausted, and stale retries, plus successful and failed results among the 30 latest sync runs.

## Operational cautions

- The lease is 30 minutes. If a worker genuinely takes longer, recovery can schedule a later duplicate import. Imports deduplicate contacts by email.
- A crash after the V71 due-policy claim but before a V73 retry is enqueued can still skip that schedule slot. V74 recovery covers **retry jobs**, not all primary scheduled runs.
- Incremental HubSpot synchronization is **not implemented**; the importer still fetches the first 1,000 contacts per run. Avoid describing the import as a complete CRM mirror.
- GitHub Actions execution is best effort. Live Render and real HubSpot integration require separate verification.
