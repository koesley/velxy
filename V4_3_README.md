# VELXTRIA V4.3 — Free local content sections

This is an incremental upgrade to V4.2, not a full visual editor.

## Changes
- Adds owner-scoped editable Services, Gallery captions, Testimonials and FAQ content blocks.
- Saves sections to a new SQLite table; existing site drafts and business data remain unchanged.
- Renders saved blocks in the private draft preview, escaped to prevent HTML injection.
- Adds per-block removal.
- No AI, public publishing, drag-and-drop, images upload, or multi-page routing yet.

## Run
Open `velxy-main` in Cursor, use the same local environment variables and `python portal.py` commands as V4.2. Sign in, open Site Studio, create a test company, save a section, then open full preview.

## Important
The local SQLite database is not bundled. To preserve Gerate, copy your *local test database* from V4.2 only while both servers are stopped, using the path configured in `persistent.py`. Never copy production credentials or databases. Do not deploy to Render.
