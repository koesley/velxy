"""Email notifications: a small outbox the delivery worker sends from.

Report delivery has its own queue (the deliveries table, keyed by
report). Everything else the site emails — a PRO-activation confirmation,
a password-reset link, a PRO renewal reminder — goes through this outbox
instead: queue() inserts a row, the delivery worker picks it up and sends
it with the same SMTP settings. A dedupe_key makes each notification
send at most once (one confirmation per order, one reminder per PRO
period), and the same retry/backoff rules as report delivery apply.

Nothing is sent unless SMTP is configured (VELXTRIA_SMTP_HOST); rows
simply wait queued until it is.
"""
import hashlib
import os
import secrets
import smtplib
import time
from email.message import EmailMessage

RENEWAL_REMINDER_DAYS = 3


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS email_outbox (
      id TEXT PRIMARY KEY, user_id INTEGER, recipient TEXT NOT NULL,
      subject TEXT NOT NULL, body TEXT NOT NULL, kind TEXT NOT NULL,
      dedupe_key TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'queued',
      attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
      next_attempt INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL)''')


def smtp_configured():
    return bool(os.getenv('VELXTRIA_SMTP_HOST', '').strip())


def send_mail(recipient, subject, body):
    """Send one plain-text email with the configured SMTP settings."""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.environ['VELXTRIA_SMTP_FROM']
    msg['To'] = recipient
    msg.set_content(body)
    host = os.environ['VELXTRIA_SMTP_HOST']
    port = int(os.getenv('VELXTRIA_SMTP_PORT', '587'))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(os.environ['VELXTRIA_SMTP_USER'],
                   os.environ['VELXTRIA_SMTP_PASSWORD'])
        smtp.send_message(msg)


def queue(conn, recipient, subject, body, kind, dedupe_key=None, user_id=None):
    """Queue an email. With a dedupe_key, a second queue for the same key
    is a no-op. Returns True when a row was queued."""
    setup(conn)
    cur = conn.execute(
        'INSERT INTO email_outbox'
        '(id,user_id,recipient,subject,body,kind,dedupe_key,status,next_attempt,created)'
        ' VALUES (?,?,?,?,?,?,?,?,?,?)'
        ' ON CONFLICT(dedupe_key) DO NOTHING',
        (secrets.token_hex(16), user_id, recipient, subject, body, kind,
         dedupe_key, 'queued', int(time.time()), int(time.time())))
    claimed = cur.cursor.rowcount if hasattr(cur, 'cursor') else cur.rowcount
    return claimed == 1


def process_one(conn):
    """Send one queued notification, if any. Returns True when one was sent."""
    setup(conn)
    row = conn.execute(
        "SELECT id,recipient,subject,body,attempts FROM email_outbox"
        " WHERE status IN ('queued','retry') AND next_attempt<=? AND attempts<3"
        " ORDER BY next_attempt LIMIT 1", (int(time.time()),)).fetchone()
    if not row:
        return False
    ident, recipient, subject, body, attempts = row
    conn.execute("UPDATE email_outbox SET status='sending', attempts=attempts+1"
                 " WHERE id=?", (ident,))
    try:
        send_mail(recipient, subject, body)
    except Exception as exc:
        retry = (attempts + 1) < 3
        conn.execute(
            'UPDATE email_outbox SET status=?,last_error=?,next_attempt=?'
            ' WHERE id=?',
            ('retry' if retry else 'failed', str(exc)[:160],
             int(time.time()) + min(3600, 60 * 2 ** attempts), ident))
        raise
    conn.execute("UPDATE email_outbox SET status='sent',last_error=''"
                 " WHERE id=?", (ident,))
    return True


def queue_pro_confirmation(conn, user_id, email, period_end, order_id):
    """Confirm a settled PRO payment by email. One per order, ever."""
    from datetime import datetime, timezone
    end = datetime.fromtimestamp(period_end, timezone.utc).strftime('%Y-%m-%d')
    return queue(
        conn, email, 'Your VELXTRIA PRO is active',
        'Your $49 PRO payment settled. PRO is active through %s — 50 reports '
        'per billing cycle, paid with Bitcoin.\n\n'
        'Sign in at your dashboard to generate reports. If PRO ever lapses, '
        'renewing from the dashboard extends your current period.\n\n'
        '— VELXTRIA' % end,
        'pro_activated', dedupe_key='pro-activated:' + order_id,
        user_id=user_id)


def scan_renewal_reminders(conn, now=None):
    """Queue a renewal reminder for every PRO period ending within 3 days.

    One per user per period end (dedupe_key), so repeated scans never
    re-send. Returns how many reminders were queued."""
    now = int(time.time()) if now is None else now
    rows = conn.execute(
        'SELECT u.id,u.email,s.period_end FROM subscriptions s'
        ' JOIN users u ON u.id=s.user_id'
        " WHERE s.status='active' AND s.period_end>? AND s.period_end<=?",
        (now, now + RENEWAL_REMINDER_DAYS * 86400)).fetchall()
    queued = 0
    for user_id, email, period_end in rows:
        from datetime import datetime, timezone
        end = datetime.fromtimestamp(period_end, timezone.utc).strftime('%Y-%m-%d')
        if queue(
                conn, email, 'Your VELXTRIA PRO ends soon',
                'Your VELXTRIA PRO ends on %s. Renew from your dashboard for '
                'another 30 days — the new period starts when the current one '
                'ends, so you lose no days.\n\n— VELXTRIA' % end,
                'renewal_reminder',
                dedupe_key='renewal-reminder:%d:%d' % (user_id, period_end),
                user_id=user_id):
            queued += 1
    return queued


def reset_token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()
