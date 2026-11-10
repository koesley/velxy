# VELXTRIA V56 — Milestone 10: Executive Intelligence Council 2.0

## What is included
- `sovereign_executive_v56.py`: tenant-scoped, deterministic specialist review, explicit critic objections, evidence fingerprints, durable SQLite review records and audit events.
- `portal.py`: dashboard `/sovereign-executive-v56`, read-only JSON history `/sovereign-executive-v56.json?w=<workspace-id>`, CSRF-protected POST to run a review, navigation and database setup.
- `test_sovereign_executive_v56.py`: inherited regression tests and new review tests.

## Run
Back up your database and keep your existing `VELXTRIA_DATA_DIR`. From `velxy-main`:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Open `http://127.0.0.1:8878/sovereign-executive-v56` and sign in. Import workspace metrics first; select a review objective and click **Run executive review**. Each run is immutable, retains its evidence digest, and is marked stale if the underlying metrics change. Workspace viewers can read but cannot initiate reviews.

## Safety and limitations
This is a deterministic evidence council, not multiple autonomous AI agents or a trained model. It only evaluates workspace-scoped monthly metrics, cannot execute actions, cannot approve spending, and makes no profit predictions. Its observations are not causal conclusions. The dashboard has not been browser-tested or production-validated. Legacy routes elsewhere in the monolith may have separate isolation limitations and need an independent security audit before production deployment.

## Tests
`python -m unittest -q test_sovereign_executive_v56`

## Future
Milestone 11: read-only, consent-based business connectors with incremental synchronization and provenance.
