# VELXTRIA V56 Milestone 14 — Project Genesis

## Run

Back up the existing SQLite database and retain VELXTRIA_DATA_DIR. In local SQLite studio mode run `python portal.py`; open `/sovereign-genesis-v56`. Existing modules are preserved.

## Scope

- Possibility Engine: five deterministic business-model hypotheses based on verified latest-period metrics.
- Parallel Worlds: cautious, balanced, ambitious six-month sensitivity scenarios using the existing future calculator. These are NOT predictions.
- Blind Spot Detector: missing data required to test each idea.
- Adversarial Council: explicit critic, defender and referee arguments, all deterministic templates, not independent LLM agents.
- Evolution Lab: workspace-scoped draft → approved → completed/stopped experiments, owner-only transitions, manually entered observed outcomes with provenance notes. Approval tracks the experiment; it does not execute any business action.
- Source snapshot and SHA-256 evidence digest, stale-session blocking, audit events, read-only JSON history.

## Security and limits

Local SQLite studio only. Workspace membership is checked for all operations; only owner can approve/complete/stop. CSRF is enforced by the portal's existing POST handler. No external API, background workers, spend, generated SQL or autonomous execution. Outcomes are observations, not causal proof. Template suggestions may be inappropriate without additional data. Existing account-scoped legacy routes require a separate multi-tenant security audit before production use.

## Test

`python -m unittest -v test_sovereign_genesis_v56`

`python -m py_compile portal.py sovereign_genesis_v56.py`
