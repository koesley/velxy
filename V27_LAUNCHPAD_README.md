# VELXTRIA V27 — Project Launchpad

Local-only customer pilot onboarding at `/launchpad`. Builds on V26.

Features: tenant-scoped pilots and feedback, role-checked writes, real-data onboarding checklist (published app, application record, business goal), owner-only pilot completion, HTML-escaped user text, CSRF-protected POSTs, no autonomous customer contact or external actions.

Start: set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, preserve your existing `VELXTRIA_DATA_DIR`, and run `python portal.py`. Make a separate backup before upgrading.

Not production-ready: full legacy security audit, browser end-to-end tests, invitation/email automation, payment flow, recovery UI, and external hosting are not included. Use test data during pilot evaluation.
