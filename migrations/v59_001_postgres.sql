-- V59 Ascension: PostgreSQL-only, additive schema. Apply to staging first.
-- Requires existing empire_members table; no existing tables are modified.
BEGIN;
CREATE TABLE IF NOT EXISTS v59_contacts (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, name TEXT NOT NULL,
 email TEXT NOT NULL DEFAULT '', created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v59_contacts_workspace ON v59_contacts(workspace);
CREATE TABLE IF NOT EXISTS v59_deals (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
 contact TEXT NOT NULL REFERENCES v59_contacts(id),
 title TEXT NOT NULL, cents BIGINT NOT NULL CHECK (cents >= 0),
 stage TEXT NOT NULL CHECK (stage IN ('lead','contacted','qualified','proposal','won','lost')),
 created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v59_deals_workspace ON v59_deals(workspace,stage);
CREATE TABLE IF NOT EXISTS v59_audits (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, url TEXT NOT NULL,
 findings TEXT NOT NULL, created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v59_audits_workspace ON v59_audits(workspace,created);
CREATE TABLE IF NOT EXISTS v59_workflows (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, name TEXT NOT NULL,
 trigger_kind TEXT NOT NULL, action_kind TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1))
);
CREATE INDEX IF NOT EXISTS v59_workflows_workspace ON v59_workflows(workspace);
CREATE TABLE IF NOT EXISTS v59_runs (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, workflow TEXT NOT NULL,
 status TEXT NOT NULL, details TEXT NOT NULL, created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v59_runs_workspace ON v59_runs(workspace,created);
CREATE TABLE IF NOT EXISTS v59_agents (
 workspace TEXT NOT NULL, kind TEXT NOT NULL,
 installed INTEGER NOT NULL CHECK(installed IN (0,1)),
 PRIMARY KEY(workspace,kind)
);
CREATE TABLE IF NOT EXISTS v59_agent_runs (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
 kind TEXT NOT NULL, report TEXT NOT NULL, created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v59_agent_runs_workspace ON v59_agent_runs(workspace,created);
COMMIT;
