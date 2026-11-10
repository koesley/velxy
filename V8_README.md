# VELXTRIA V8 — Project Sovereign

Adds an actual read-only agent tool execution runtime at `/sovereign`. All diagnostic runs are persisted in `vx8_tool_runs`, scoped by user and mission. Three tools: CRM pipeline, mission action audit, and operations overview. No paid API or Ollama required for these diagnostics. V6 and V7 remain available.

## Install
Back up the existing `portal.sqlite3`. Unzip, open `velxy-main`, set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DATA_DIR` to your existing database directory, run `python portal.py`, visit `http://127.0.0.1:8878/sovereign`.

## Boundaries
No external execution, background agents, autonomous messaging, or financial changes. This is the first safe, useful execution layer—not full autonomous agent orchestration.
