# Email delivery setup

Report delivery, PRO-activation confirmations, password resets, and PRO
renewal reminders all send through the same delivery settings. The code
is live; only the credentials are missing. Without them, reports are
download-only, no confirmation or reset email can go out, and the
forgot-password page says so instead of promising an email that will
never arrive.

## Why Brevo, not Gmail SMTP (read first)

Render's **free tier blocks outbound SMTP ports 25, 465, and 587** — a
connection to Gmail's mail server never leaves Render, so every send
fails with `OSError: [Errno 101] Network is unreachable` no matter how
correct the Gmail settings are. That is what happened all morning on
Nov 20, 2026: the app password was verified correct and one reset email
did get through at 08:08 ET, but every other attempt failed at the
network, before Gmail ever saw a login.

Brevo's API travels over **HTTPS (port 443)** — the same port the
site already uses for BTCPay — so it is not blocked. When its key is
set, the site sends through Brevo; SendGrid's API stays as a second
path and plain SMTP as the fallback for hosts where SMTP works.

## What to set on Render (velxtria-private-preview-tzie service)

| Variable | Value |
| --- | --- |
| `VELXTRIA_BREVO_API_KEY` | the Brevo API key (starts with `xkeysib-`, see below) |
| `VELXTRIA_SMTP_FROM` | `vincenthalay2005@gmail.com` — must match the verified Brevo sender |

Set them in the Render dashboard (Environment), then redeploy. The
founder overview on the dashboard shows `Email: configured` once a
delivery path is set, and the startup log says which one is active
(`Email delivery queue enabled (Brevo)`).

## Brevo setup (about 5 minutes, free tier: 300 emails/day)

1. Create a free account at https://www.brevo.com (no credit card).
   Sign up with any email, then verify it.
2. **Verify the sender:** Dashboard → Settings → Senders & IP →
   **Senders** → **Add a sender**. Enter
   `vincenthalay2005@gmail.com`. Brevo emails a verification link to
   that Gmail address — click it. No domain is needed; emails then
   appear to come from the Gmail address.
3. **API key:** Dashboard → Settings → SMTP & API → **API Keys** →
   **Generate a new API key**. Name it `VELXTRIA`. Copy the key now —
   it is shown once and starts with `xkeysib-`.
4. Paste the API key as `VELXTRIA_BREVO_API_KEY` on Render.

If the key ever leaks, delete it in the same API Keys page and make a
new one — the Gmail account password never changes.

## SendGrid (alternate path, currently unused)

SendGrid's API would work the same way (key `VELXTRIA_SENDGRID_API_KEY`,
free tier 100 emails/day, sender verified under Settings → Sender
Authentication → Verify a Single Sender). It is unused because its
signup's human check blocked both the cloud browser and the owner's
phone in Nov 2026, so no SendGrid account exists.

## The Gmail SMTP fallback (hosts where SMTP works)

| Variable | Value |
| --- | --- |
| `VELXTRIA_SMTP_HOST` | `smtp.gmail.com` |
| `VELXTRIA_SMTP_PORT` | `587` |
| `VELXTRIA_SMTP_FROM` | `vincenthalay2005@gmail.com` |
| `VELXTRIA_SMTP_USER` | `vincenthalay2005@gmail.com` |
| `VELXTRIA_SMTP_PASSWORD` | a Gmail **app password** — never the Google account password |

The app password: Google Account → Security → 2-Step Verification
(must be on) → App passwords → app `VELXTRIA`, device `Other`. Copy
the 16-character password Google shows. It is shown once. On Render
Free this fallback can never send (see above) — it is kept for a paid
host or local runs only.

## What sends once email is live

- **Report delivery:** the dashboard "Email the completed report"
  checkbox queues the ZIP; the background worker sends it (3 attempts,
  backoff) and marks the report `sent`.
- **PRO confirmation:** when a payment settles, the buyer gets "Your
  VELXTRIA PRO is active" with the date PRO runs through. One per order.
- **Password reset:** `/forgot` sends a single-use link (1 hour). Using
  it signs the account out everywhere.
- **Renewal reminders:** the background worker checks hourly and emails
  PRO users whose period ends within 3 days. One per period.
