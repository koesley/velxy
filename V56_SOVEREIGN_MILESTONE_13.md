# VELXTRIA V56 — Milestone 13: Natural Language Command Center

## Scope
A polished, deterministic, **read-only** local question interface. It recognizes six supported areas (Guardian alerts, connector batches, strategy evaluations, execution jobs, memory records, future simulation runs), shows workspace-scoped counts and underlying table evidence, and links to the relevant existing module. Ambiguous, unsupported, and action-oriented questions are explicitly rejected. No LLM, paid API, external connection, SQL generation from user text, autonomous execution, or invented conclusions.

## Launch
Back up your database, extract the ZIP, run from `velxy-main` with `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, then open `/sovereign-command-v56`. Add `?w=<workspace-id>&q=How%20many%20alerts%3F` to prefill a question. `/sovereign-command-v56.json` returns structured JSON and requires the same authenticated workspace membership.

## Security
Only authenticated workspace members may read records. Every count query is parameterized by workspace ID. Table names are fixed constants, not generated from input. No write routes exist. Existing session/CSRF mechanisms and all prior modules are retained.

## Limitations
This is a deterministic command center foundation, not a conversational LLM agent. It currently answers a limited set of questions with counts, not multi-table financial analysis. No production security or end-to-end browser audit is claimed. Some older portal routes may have separate tenant-isolation issues requiring a broader audit before public deployment.

## Tests
Run `python -m unittest -v test_sovereign_command_v56.py` and existing Sovereign test suites.
