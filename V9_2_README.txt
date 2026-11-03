VELXTRIA V9.2 — manual verified activation staging (NOT automatic billing)

Do not turn on checkout. Existing V9.1 portal.py and subscriptions.py are unchanged.
This release adds subscription_admin.py only. No new folders or dependencies.

WHY: Payhip's webhook signature is not a cryptographic body HMAC. A webhook
claim is not sufficient proof of active payment. The application remains
fail-closed. The operator must independently check the Stripe subscription,
customer identity, exact $49 monthly plan, successful payment, current billing
period, and any cancellation/refund before using the CLI.

IMPORTANT: Database persistence must be verified before activating real users.
If your Render instance is using local SQLite on ephemeral disk, the state can
be lost on redeploy. Use configured persistent Postgres and secure report storage.

Example, only AFTER real verification, with actual values substituted:
python subscription_admin.py activate --email customer@example.com --reference sub_VERIFIED_ID --start 2026-11-03T00:00:00+00:00 --end 2026-12-03T00:00:00+00:00 --note "Verified in Stripe dashboard" --confirm-verified

Revoke if verification shows cancellation/refund or other loss of entitlement:
python subscription_admin.py revoke --email customer@example.com --note "Verified cancellation" --confirm-verified

Never put customer payment details, Stripe keys, or Payhip keys in command args.
Don't execute activation based solely on webhook content or a checkout screenshot.
Do not expose the CLI as a public endpoint. Ensure operator access and keep an
external audit trail of evidence and changes. Renewals and cancellations are NOT
automated; expired access automatically falls back to demo, but cancellations
must be checked and revoked manually. The 50 report limit is per verified period.

Next production milestone: server-side Stripe subscription lookup, authenticated
account linking, durable idempotent reconciliation and renewal/cancellation tests.
