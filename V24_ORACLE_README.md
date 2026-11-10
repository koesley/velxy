# VELXTRIA V24 — Oracle (first milestone)

Local SQLite studio only. Back up your existing `portal.sqlite3` and preserve `VELXTRIA_DATA_DIR`. Run `python portal.py`, then visit `/oracle`.

Oracle answers from tenant-scoped, bounded aggregate statistics; optionally asks a local Ollama instance to explain them. Question history is private to the requesting user within a workspace. It does not run SQL supplied by a model, create workflows, forecast revenue, or perform external actions. Data is sampled from the most recent 500 records per app, not a full historical dataset.

Ollama optional: `ollama pull llama3.2`; default URL http://127.0.0.1:11434/api/generate.

Do not expose the local development server to the public internet. Full end-to-end browser and deployment security reviews are not complete.
