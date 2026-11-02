VELXTRIA V3 - Payhip webhook staging (LOCAL DEVELOPMENT ONLY)

This is an incremental patch to V3; Gmail delivery is preserved.
Webhook endpoint: POST /webhooks/payhip

IMPORTANT: This is NOT a production subscription integration.
- Webhook payloads are validated using Payhip's documented sha256(API_KEY)
  signature and stored for manual review in portal.sqlite3 / payhip_events.
- Payhip's documented signature is NOT a cryptographic signature over the
  payload body. An attacker who learns the static signature could forge events.
- No event grants access, cancels access, or charges anyone.
- No Payhip API key is included in this ZIP.
- The service binds 127.0.0.1 only. Do not publish it as-is.
- Payhip does not offer a general subscription lookup endpoint in its
  documented public API. Payment/subscription matching needs additional
  verified reconciliation before production access can be automated.

For local testing, stop the app, back up your current folder/database,
then replace only portal.py and add payhip_integration.py. Keep your
existing Gmail SMTP settings. In the same PowerShell session:
  $env:VELXTRIA_PAYHIP_API_KEY = Read-Host 'Payhip API key' -MaskInput
  py -3.12 portal.py

NEVER screenshot or paste your Payhip API key, Gmail App Password, or any
full webhook payload containing a signature.

Do not fill in Payhip's webhook URL until secure public hosting and
reconciliation are designed and tested.
