# VELXTRIA V17 — Project Phoenix

New `/phoenix` page in local SQLite studio mode. Export approved Singularity X apps with the Evolution V16 inspector and an offline repair-review workbench.

Features: optional localhost Ollama diagnosis of a user-provided test failure report; reviewable code-change proposals for `app.py` and `test_app.py`; SHA-256 baseline and candidate hashes; unified diffs; no automatic application, test execution, or deployment. Existing V16 and prior features are retained.

Use `python portal.py` with the same VELXTRIA_DATA_DIR as your existing installation. Back up your SQLite data before upgrading. Do not copy or replace your database with files from this ZIP.

Limitations: This is the V17.1 review-first milestone, not an autonomous self-repair agent. Docker testing requires local Docker installation and manual invocation. No release automation or rollback manager is included.
