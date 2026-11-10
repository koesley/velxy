# VELXTRIA V33 — Project Evolutionary Core

Local-only release candidate and human-review workflow tied to V32 Horizon improvement plans.

## Run

Preserve your existing `VELXTRIA_DATA_DIR` and back up `portal.sqlite3` before upgrading. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, then run `python portal.py`. Visit `http://127.0.0.1:8878/evolutionary-core`.

## Workflow

1. Record a pilot issue in First Contact.
2. Create a Horizon plan and record baseline, target, and measured result. Mark the plan verified.
3. Create a release candidate linked to that plan.
4. Record human-entered passing test evidence.
5. Workspace owner approves or rejects the release candidate. Decisions are immutable; create a new candidate for further iterations.

## Safeguards and limitations

- Every operation checks workspace membership; only owner/editor can create candidates or record tests; only owner can review.
- POST requests use the existing portal CSRF mechanism.
- This system does not execute tests, run commands, deploy code, validate claimed test evidence, or guarantee release readiness.
- Approval is a review record, not a deployment action or production certification.
- Existing database tables are retained. Only the new `evolution_releases` table and index are created.
- Keep local-only until independent security and full browser testing are complete.
