# VELXTRIA V75 — resumable contact synchronization

Scheduled HubSpot OAuth imports and retries now save a workspace-scoped cursor after each successfully committed contact page. Each scheduled run processes up to ten pages (1,000 contacts), then resumes from the saved cursor on its next run. If a page fails, previously committed pages remain saved and a retry starts from the last checkpoint.

The integration dashboard displays page count, imported contact count, and completed scans. When the HubSpot paging cursor ends, the checkpoint resets to the first page for a future scan.

**Important limits:** This is resumable pagination, not HubSpot's true incremental change feed. Existing contacts are deduplicated by email and are not updated if their properties change. Very large contact lists may change during pagination; a full backfill is not guaranteed to be a consistent snapshot. A workspace can only be imported safely by one worker at a time; competing manual/scheduled operations are not serialized by V75. A page is limited to 100 contacts and an import to 10 pages. No HubSpot writes or automatic emails are performed. Render and HubSpot live deployment require verification.
