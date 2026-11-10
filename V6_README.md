# VELXTRIA V6 — PROJECT SINGULARITY (local AI preview)

This release adds an actual local-model strategy generator to V5.5. It does **not** add autonomous execution or scheduled background work. Three reviewer perspectives are generated in one structured Ollama request, not by three independent agents.

## Windows installation

1. **Back up the working `portal.sqlite3` first.** Do not replace or delete the V5.5 data directory.
2. Extract this ZIP to a **new folder**. This release does not include a database.
3. Install Ollama from https://ollama.com/download and in PowerShell run `ollama pull llama3.2` (or another model appropriate to your hardware). Keep Ollama running. It may take minutes to download the model.
4. Open `velxy-main` in Cursor. In PowerShell:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
$env:VELXTRIA_REQUIRE_PERSISTENCE="0"
Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
# CHANGE THIS PATH to your actual existing data folder:
$env:VELXTRIA_DATA_DIR="$HOME\Downloads\VELXTRIA_V5_3_Mission_Execution\velxy-main"
python portal.py
```

5. Visit `http://127.0.0.1:8878/singularity`, sign in, select your mission and local model, and request a plan. The first response may be slow on a CPU-only PC.

## Boundaries

- Ollama is accessed only at `127.0.0.1:11434`; no API key and no paid model calls.
- V6 planning is disabled outside local studio mode and on remote database deployments.
- Generated plans are saved per user and mission in the new `vx6_plans` table. Existing tables are untouched.
- AI plans are advisory and may contain errors. They cannot execute tools, contact customers, publish content, spend money or run in the background.
- Mission history, owner guidance and owner-reported outcomes are included as context. Do not use real sensitive customer data in this local prototype.
- No hardware requirement was assumed. Use a smaller Ollama model if memory is limited.
