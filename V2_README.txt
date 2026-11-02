VELXTRIA CUSTOMER PORTAL V2 — LOCAL PROTOTYPE

1. Double-click RUN_PORTAL.bat (Python 3.12) or run: py -3.12 portal.py
2. Visit http://127.0.0.1:8878
3. Create a demo account, sign in, and upload a CSV with the eight required headers.
4. Download the report ZIP from your dashboard.
5. For sample data, use the demo_sales.csv from V1 inbox.

WORKING: account registration/login, password hashing, session cookies, CSRF tokens, customer-isolated reports, upload validation, 5MB / 20k-line / 50 monthly report limits, CSV processing with original V1 automate.py, report ZIP downloads, founder overview scaffold, and error reporting.

NOT IMPLEMENTED: Payhip subscription verification, public hosting, HTTPS, password resets, production email delivery, background scheduled customer imports, secure anti-abuse/rate limiting, customer deletion/privacy workflows, operational monitoring, payment webhooks. Demo access is NOT paid access. The customer portal does NOT send email automatically; V1 runner.py separately supports optional fixed-recipient SMTP.

SECURITY: local loopback only. DO NOT port-forward or deploy this prototype publicly, and DO NOT upload real/sensitive customer files. Production requires a proper security review, hardened sessions and HTTPS, persistent secure storage, authentication safeguards, data retention and deletion, and verified Payhip integration.

The report engine accepts only the eight specified sales CSV columns and emits CSV/TXT files in a ZIP. No Excel .xlsx upload or output yet. No AI API costs.
