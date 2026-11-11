-- V62 Execution Engine: immutable run records and internal deliverables.
BEGIN;
CREATE TABLE IF NOT EXISTS v62_runs (
 id TEXT PRIMARY KEY,
 workspace TEXT NOT NULL,
 mission TEXT NOT NULL REFERENCES v61_missions(id),
 task TEXT NOT NULL REFERENCES v61_tasks(id),
 tool TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('completed','failed')),
 output TEXT NOT NULL,
 actor TEXT NOT NULL,
 created BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS v62_runs_workspace_task ON v62_runs(workspace,task,created DESC);
COMMIT;
