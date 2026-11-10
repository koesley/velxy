# VELXTRIA V4.2 — CSP stylesheet fix

This update moves Site Studio and private preview CSS to external, local stylesheets (`site-studio.css` and `site-preview.css`). It preserves the existing `style-src 'self'` CSP and keeps the studio local-only.

## Run
1. Stop the previous server (Ctrl+C).
2. Open this ZIP’s `velxy-main` folder in Cursor.
3. Start with the same local environment variables used for V4.2 and `python portal.py`.
4. Sign in, open Site Studio and your private preview. Refresh with Ctrl+Shift+R if needed.

**Note:** The ZIP does not contain your local SQLite data. If you need the existing Gerate draft, copy the local database from your prior V4.2 folder with both servers stopped, after backing it up. Never copy a production database or secrets.

No production deployment or paid services are required.
