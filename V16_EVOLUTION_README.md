# VELXTRIA V16 — Evolution

Adds `/evolution` to local SQLite Studio. Exports approved V13/V14/V15 apps with static inspection, checksums, optional Docker-based offline unit-test runner, and release checklist. Does not automatically run generated code or deploy.

## Install
Back up your existing `portal.sqlite3` and keep your existing `VELXTRIA_DATA_DIR` environment variable. Run `python portal.py` in `velxy-main`, then visit `http://127.0.0.1:8878/evolution`.

## Export
Publish an app in Singularity X, then download its Evolution ZIP. Extract it and run `python run_isolated_tests.py` after installing Docker Desktop. The runner uses Docker Compose with network disabled, read-only filesystem, non-root user, CPU/memory/PID limits, and no extra capabilities. Docker is not a perfect sandbox; do not use untrusted code or production secrets.
