# VELXTRIA V73 — durable retry queue

Failed V71 scheduled HubSpot OAuth imports now create one durable retry chain per workspace. The hourly GitHub Actions V71 scheduler also processes due retries. Retries use the workspace's own V70 encrypted OAuth credentials, never the shared V67 token.

Retry delays are **5 minutes**, **30 minutes**, and **2 hours**, measured from the last failed attempt. Because GitHub Actions runs hourly, actual retry execution may be later. After three failed retry attempts, the chain becomes `exhausted` and no further automatic attempts occur.

## Limitations

- Retries cover failed **scheduled** OAuth imports only; manual imports do not enqueue retries.
- A running worker crash can leave a retry in `running`; automatic stale-claim recovery is not implemented. Inspect the database or add recovery before high-scale deployment.
- The retry queue does not provide incremental sync or historical cursor persistence. Each attempt re-reads the first 1,000 contacts and deduplicates existing leads.
- Disconnecting a HubSpot OAuth connection prevents pending retries from executing.
- Error details and credentials are intentionally excluded from public logs. Existing V68 sync history records each attempt.
