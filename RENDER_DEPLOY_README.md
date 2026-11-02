# VELXTRIA V3 — Render PRIVATE PREVIEW

This build is for a **private, disposable demo only**. It is not a customer-ready subscription product.

## Deployment
1. Upload the CONTENTS of this folder to a new private GitHub repository. Do not upload credentials, local databases, customer files, or `.env`.
2. In Render, choose **New > Blueprint**, connect that GitHub repository, and apply the included `render.yaml`.
3. Set `VELXTRIA_PREVIEW_PASSWORD` to a long, unique password in Render's environment settings. Do not reuse a Payhip or Gmail credential.
4. Open the assigned `onrender.com` URL. When the browser asks for Basic Authentication, username is `velxtria` and password is the preview password you chose.
5. Create a TEST demo account and upload only synthetic/sample CSV data.
6. Check `/healthz` to verify the app responds. This route is intentionally public and returns only `ok`.

## Important limitations
- Render Free web services sleep after idle time; waking can be slow.
- Local SQLite database and report ZIPs are **ephemeral** on Render Free: deploys/restarts can erase them. Do not rely on this for paying customers.
- Gmail SMTP port 587 is not available on Render Free; the local SMTP email workflow remains for local use only. Do not configure Gmail credentials here.
- Payhip receiver is **staging-only**, does not grant access and has not been connected to Payhip. Do not enter your exposed Payhip API key in Render.
- Browser Basic Auth is an additional preview gate, not production-grade application security. Use HTTPS on Render.
- Demo account creation and report uploads are available only behind the preview password. No sensitive or real customer data.
- Before launch: durable database/object storage, transactional email service, secure subscription reconciliation, abuse protections, security review and end-to-end billing tests.

## Local run (unchanged default)
`py -3.12 portal.py` on Windows. Local mode binds 127.0.0.1:8878. Existing local database and reports are not included in this ZIP.
