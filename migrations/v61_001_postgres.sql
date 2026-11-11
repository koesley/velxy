-- V61 OMEGA: mission plans, tasks, approvals, and immutable activity events.
BEGIN;
CREATE TABLE IF NOT EXISTS v61_missions (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, owner TEXT NOT NULL,
 objective TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','active','paused','completed')),
 created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v61_missions_workspace ON v61_missions(workspace,created DESC);
CREATE TABLE IF NOT EXISTS v61_tasks (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, mission TEXT NOT NULL REFERENCES v61_missions(id),
 role TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('proposed','approved','completed','rejected')),
 created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v61_tasks_workspace ON v61_tasks(workspace,mission);
CREATE TABLE IF NOT EXISTS v61_events (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, mission TEXT NOT NULL,
 actor TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL, created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v61_events_workspace ON v61_events(workspace,mission,created DESC);
COMMIT;
