# VELXTRIA V4.4 — Local Business Agent Workspace

This is a **rule-based prototype**, not a generative AI model. It costs nothing extra and does not contact outside services.

## Start
Open the `velxy-main` folder in Cursor and run from PowerShell:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
$env:VELXTRIA_REQUIRE_PERSISTENCE="0"
Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
python portal.py
```

Log in, open Site Studio, then **Open Business Agent Workspace**. Enter `set headline to Discover Gerate`, prepare, then approve the proposal. Refresh the preview.

The agent only recognizes `set headline to ...`, `set description to ...`, and `set theme to violet/ocean/forest`. Every change requires owner approval. No automatic deployment.

## Existing local drafts
A new extracted folder has its own local database. To preserve your existing drafts, stop both servers, back up your previous local database and copy it to the equivalent location in this new project before starting. Do not copy `.env` files or production credentials.

**Do not deploy this prototype to Render.**
