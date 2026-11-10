# VELXTRIA V56 — Project Sovereign, Milestone 6

## Implemented

A deterministic, read-only strategy simulation module (`sovereign_strategy_v56.py`) built on the Milestone 5 opportunity detector. The module requires a currently eligible opportunity supported by synchronized, unconflicted monthly CSV evidence. Three templates per supported opportunity category (revenue decline, expense increase, conversion decline) provide conservative, balanced, and aggressive hypothetical scenarios. Each scenario shows revenue, expenses, margin proxy, implementation cost, stress-tested downside, and a transparent illustrative score. No LLM, external API, external execution, or autonomous profit-making behavior is implemented.

## Interface

- GET `/sovereign-strategies-v56` — authenticated, local-studio-only dashboard.
- GET `/sovereign-strategies-v56.json?w=WORKSPACE_ID` — workspace-scoped JSON history.
- POST `/sovereign-strategies-v56` — existing CSRF-protected authenticated form with `workspace` and `opportunity_key` fields. Requires workspace editor or owner role.
- Module functions: `setup`, `simulate`, `snapshot`, `run`, `history`, `render`.

## Model and formulas

For baseline revenue R and expenses E, assumptions r (revenue change), e (expense change), and c (implementation cost as fraction of baseline expenses):

- Hypothetical revenue = R × (1 + r)
- Hypothetical expenses = E × (1 + e) + E × c
- Margin proxy = hypothetical revenue − hypothetical expenses
- Downside: revenue change r − 0.10, expense change e + 0.05; implementation cost unchanged
- Illustrative score = hypothetical margin delta + 0.25 × downside margin delta − R × risk penalty, where risk penalties are 0%, 2%, 5% for conservative, balanced, aggressive.

All template parameters are deliberately illustrative. They are not measured effect sizes, predicted returns, accounting profits, or causal conclusions. The highest illustrative score is **only** a review candidate. No strategy is approved or executed.

## Evidence and data integrity

The engine uses the current opportunity snapshot and checks its source-import link against the unconflicted, synchronized monthly metrics. A SHA-256 digest covers the opportunity discovery evidence, current baseline, opportunity key, and simulation policy version. History is stored in `sv56_strategy_runs`, scoped by workspace. A run is marked stale if its supporting evidence or policy changes or the opportunity is no longer eligible. Old results remain available and are not silently recalculated.

## Security

Existing authenticated sessions and CSRF validation are reused in `portal.py`. Workspace membership is checked on reads and editor/owner permission on simulation creation. The UI HTML-escapes all dynamic data. Form fields are bounded by the existing multipart parser. Feature is gated by `VELXTRIA_LOCAL_STUDIO=1` and local SQLite mode. The module does not expose external execution or connector writes.

## Install / run

Back up your SQLite database and retain the existing `VELXTRIA_DATA_DIR`. Extract the package and from `velxy-main` run:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Open `http://127.0.0.1:8878/sovereign-strategies-v56`. Import monthly CSV metrics in Sovereign Foundation, synchronize them, then discover opportunities. Only then run strategy simulation.

## Migration / rollback

`setup(c)` adds `sv56_strategy_runs` and an index using `CREATE TABLE IF NOT EXISTS`. Existing tables are not rewritten. To roll back, stop the app and restore the backed-up source and database; optionally drop the new table and index only after exporting desired history. Do not delete existing business data.

## Verification

- `python -m unittest test_sovereign_strategy_v56 -q` — 86 tests passed, including inherited Sovereign tests.
- Python compilation and ZIP integrity checked.
- Full application regression, live HTTP/browser flows, production security review, external integrations, and PostgreSQL deployment **not verified**.

## Next milestone

Milestone 7 should introduce a separate, permissioned execution center with explicit approval gates, idempotency, and a kill switch. This milestone does not grant approval or execution permissions.
