# VELXTRIA V70 — HubSpot OAuth

V70 supports owner-initiated HubSpot authorization-code OAuth for individual workspaces. Credentials are encrypted at rest with Fernet and never displayed in HTML. Imports are read-only and limited to 100 contacts per request.

## Setup

1. Create a HubSpot developer app with OAuth enabled and request `crm.objects.contacts.read`. Register the exact HTTPS redirect URL `https://YOUR_DOMAIN/hubspot-oauth-v70/callback`.
2. Set these environment variables **as secrets** in Render:
   - `VELXTRIA_V70_HUBSPOT_CLIENT_ID`
   - `VELXTRIA_V70_HUBSPOT_CLIENT_SECRET`
   - `VELXTRIA_V70_HUBSPOT_REDIRECT_URI` (the registered HTTPS callback)
   - `VELXTRIA_V70_ENCRYPTION_KEY` (generate once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
3. Keep the encryption key safe and stable across deployments; losing it prevents existing tokens from being decrypted.
4. In the V70 HubSpot Connections page, select a workspace and connect. Only workspace owners may connect, import, or disconnect.

## Security and limitations

- OAuth state is one-time and expires after 10 minutes. The user must remain signed into the same VELXTRIA account during authorization.
- Access and refresh tokens are encrypted before database storage. HubSpot access tokens refresh when needed.
- Disconnect deletes the local credentials but does **not** revoke HubSpot authorization. Revoke it in HubSpot if required.
- V69's scheduler still uses the older server-side private-app token, **not** these per-workspace OAuth connections. Automatic OAuth sync is not yet supported.
- Do not enable broad multi-tenant deployment until the integration has been reviewed and production-tested with real HubSpot OAuth accounts.
