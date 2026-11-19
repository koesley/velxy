# Email delivery setup (SMTP)

Report delivery, PRO-activation confirmations, password resets, and PRO
renewal reminders all send through the same SMTP settings. The code is
live; only the credentials are missing. Without them, reports are
download-only, no confirmation or reset email can go out, and the
forgot-password page says so instead of promising an email that will
never arrive.

## What to set on Render (velxtria-private-preview-tzie service)

| Variable | Value |
| --- | --- |
| `VELXTRIA_SMTP_HOST` | `smtp.gmail.com` |
| `VELXTRIA_SMTP_PORT` | `587` |
| `VELXTRIA_SMTP_FROM` | `vincenthalay2005@gmail.com` |
| `VELXTRIA_SMTP_USER` | `vincenthalay2005@gmail.com` |
| `VELXTRIA_SMTP_PASSWORD` | a Gmail **app password** (see below) — never the Google account password |

All five are read at startup. Set them in the Render dashboard
(Environment), then redeploy. The founder overview on the dashboard
shows `SMTP: configured` once they are set.

## The app password (2 minutes, in Google)

1. Google Account → Security → **2-Step Verification** (must be on).
2. Security → **App passwords** → app name `VELXTRIA`, device `Other`.
3. Copy the 16-character password Google shows. It is shown once.
4. Paste it as `VELXTRIA_SMTP_PASSWORD` on Render.

If the app password ever leaks, revoke it in the same Google page and
make a new one — the Google account password itself never changes.

## What sends once SMTP is live

- **Report delivery:** the dashboard "Email the completed report"
  checkbox queues the ZIP; the background worker sends it (3 attempts,
  backoff) and marks the report `sent`.
- **PRO confirmation:** when a payment settles, the buyer gets "Your
  VELXTRIA PRO is active" with the date PRO runs through. One per order.
- **Password reset:** `/forgot` sends a single-use link (1 hour). Using
  it signs the account out everywhere.
- **Renewal reminders:** the background worker checks hourly and emails
  PRO users whose period ends within 3 days. One per period.
