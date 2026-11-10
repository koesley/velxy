# VELXTRIA V14 — Prometheus

Built on V13. Local SQLite studio only. Existing V13 apps and records preserved.

Run `python portal.py` with your existing VELXTRIA_DATA_DIR and VELXTRIA_LOCAL_STUDIO=1. Visit /prometheus. Create an app in /singularity-x first.

Optional Ollama: install Ollama, run `ollama pull llama3.2`, and start the local Ollama server at 127.0.0.1:11434. Prometheus requests structured JSON and strictly validates the proposed schema. If Ollama is unavailable, select deterministic fallback.

V14 stores previous schema snapshots before draft redesigns, invalidates stale V13 simulation tests, performs five deterministic static checks, and exports a local-only deployment-preparation JSON manifest. Published apps cannot be redesigned or rolled back, protecting their records. V13 still controls simulation and publication.

This is NOT five independent AI agents, a code compiler, a sandbox, a cloud deployer, or a full security audit. Never expose the local portal publicly without production hardening. Back up the existing SQLite database before upgrading.
