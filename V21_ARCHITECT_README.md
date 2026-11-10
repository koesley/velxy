# VELXTRIA V21 — Project Architect (local pilot)

## Start

Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, preserve the same `VELXTRIA_DATA_DIR` as your previous version, and run `python portal.py`. Visit `/architect` after signing in.

For optional AI generation, install Ollama, run `ollama pull llama3.2`, and ensure the Ollama server is running at `http://127.0.0.1:11434`. Override model with `VELXTRIA_OLLAMA_MODEL` or loopback host with `VELXTRIA_OLLAMA_URL`.

## Workflow

Create an Empire workspace. In Architect, describe a new business app or choose an existing *draft* to request changes. Ollama proposes a name and schema with 1–20 validated fields. An owner reviews the proposal and explicitly approves or rejects it. Approval creates or revises a Genesis Prime **draft**; publication is a separate owner action in Genesis Prime.

## Limitations

This is a local SQLite pilot, not production-ready multi-tenant SaaS. AI model output is untrusted and constrained by schema validation. The model cannot execute code or publish. No automatic workflows, payments, public deployment, or migration of old apps. Existing published apps cannot be revised in Architect. No Ollama model was available in the build environment, so live model output has not been verified. Back up the SQLite database before upgrades.

## Tests

Run `python -m unittest -v test_architect_v21.py` in `velxy-main`.
