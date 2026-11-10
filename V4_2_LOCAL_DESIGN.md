# VELXTRIA V4.2 — Free local design upgrade

This ZIP is a complete copy of the V4.1 local project with an upgraded Site Studio interface and responsive private website preview. No paid services, new dependencies, production schema changes, external image requests, AI calls, or publishing.

## What changed
- `site_studio.py`: better form layout, larger text fields, modern private preview with responsive hero, abstract CSS artwork, theme palettes, basic navigation, and a placeholder contact section.
- Existing company records and drafts use the same local database schema and ownership checks.
- All other existing project files remain unchanged.

## Running on Windows PowerShell

Extract into a **new folder** and open its `velxy-main` subfolder in Cursor. In its terminal run:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
$env:VELXTRIA_REQUIRE_PERSISTENCE="0"
Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
python portal.py
```

Use a local test account. If you want to **retain your Gerate draft**, copy only your local SQLite database file from your V4.1 project into the corresponding location in V4.2 **while both servers are stopped**; do not copy production data, secrets, or credentials. Alternatively, recreate the test draft in V4.2.

## Limits
This is a visual *design upgrade*, not yet a drag-and-drop editor or a complete website builder. Navigation is demo-only; contact form, real images, AI agents, public publishing, custom domains, and commercial hosting are not implemented. Do not deploy to Render or use real customer data yet.
