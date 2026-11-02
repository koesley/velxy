VELXTRIA V3 — Local report portal with opt-in SMTP delivery queue

Run RUN_PORTAL.bat (Python 3.12), then open http://127.0.0.1:8878.
Register a demo account, upload a CSV with the required headers, and download the report.
To request email delivery, check the email box before upload.

EMAIL DELIVERY (OPTIONAL; NOT LIVE-TESTED):
Configure these environment variables BEFORE launching the server:
VELXTRIA_SMTP_HOST, VELXTRIA_SMTP_PORT (default 587), VELXTRIA_SMTP_USER,
VELXTRIA_SMTP_PASSWORD, VELXTRIA_SMTP_FROM.
Use your provider's approved SMTP credentials; do not commit passwords or screenshots of secrets.
Only user-opted-in reports are queued. Retries up to 3 times.
This is LOCAL TESTING ONLY. Do not deploy publicly or use sensitive customer data.

PAYHIP IS NOT CONNECTED. Demo access does not prove an active subscription.
Before public launch: verified webhook integration, durable worker, production security review,
HTTPS, rate limiting, password reset, backups, data retention and privacy policy.

V2 is preserved in the original ZIP. This package has NO customer database or reports.
