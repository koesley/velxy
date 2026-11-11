-- V60: additive, tenant-scoped records for six business intelligence capabilities.
BEGIN;
CREATE TABLE IF NOT EXISTS v60_records (
 id TEXT PRIMARY KEY,
 workspace TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('opportunity','knowledge','scenario','command','portal','decision')),
 title TEXT NOT NULL,
 payload TEXT NOT NULL,
 created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v60_records_workspace_kind ON v60_records(workspace,kind,created DESC);
COMMIT;
