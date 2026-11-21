"""Email notifications: a small outbox the delivery worker sends from.

Report delivery has its own queue (the deliveries table, keyed by
report). Everything else the site emails — a PRO-activation confirmation,
a password-reset link, a PRO renewal reminder — goes through this outbox
instead: queue() inserts a row, the delivery worker picks it up and sends
it. A dedupe_key makes each notification send at most once (one
confirmation per order, one reminder per PRO period), and the same
retry/backoff rules as report delivery apply.

Delivery path: Brevo's HTTPS API first (VELXTRIA_BREVO_API_KEY),
because Render's free tier blocks outbound SMTP ports 25/465/587, so a
direct SMTP connection never leaves Render (it fails with
OSError: [Errno 101] Network is unreachable). SendGrid's HTTPS API is
kept as a second path (its signup's human check blocked the cloud
browser and the owner's phone in Nov 2026, so no SendGrid account
exists). Plain SMTP (VELXTRIA_SMTP_HOST et al) is the fallback for
hosts where SMTP works. Nothing is sent unless one of the three is
configured; rows simply wait queued until then.
"""
import base64
import hashlib
import json
import os
import secrets
import smtplib
import time
import urllib.error
import urllib.request
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


SENDGRID_API_URL = 'https://api.sendgrid.com/v3/mail/send'


def sendgrid_configured():
    return bool(os.getenv('VELXTRIA_SENDGRID_API_KEY', '').strip())


BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def brevo_configured():
    return bool(os.getenv('VELXTRIA_BREVO_API_KEY', '').strip())


def email_configured():
    """True when any delivery path is configured (Brevo, SendGrid, SMTP)."""
    return brevo_configured() or sendgrid_configured() or smtp_configured()


def send_via_brevo(recipient, subject, body, attachment=None):
    """Send one plain-text email through Brevo's HTTPS API.

    attachment is (filename, data_bytes, mimetype). Raises RuntimeError
    with the API's status and message on a non-201 response, so the
    outbox retry/backoff treats it like any other send failure. Brevo
    answers 201 with a messageId on success; the sender must be a
    verified Brevo sender or the API rejects the send."""
    sender = os.environ.get('VELXTRIA_SMTP_FROM', '').strip()
    if not sender:
        raise RuntimeError('VELXTRIA_SMTP_FROM is not set (it must match '
                           'the verified Brevo sender)')
    payload = {
        'sender': {'email': sender, 'name': 'VELXTRIA'},
        'to': [{'email': recipient}],
        'subject': subject,
        'textContent': body,
    }
    if attachment is not None:
        filename, data, _mimetype = attachment
        payload['attachment'] = [{
            'content': base64.b64encode(data).decode('ascii'),
            'name': filename,
        }]
    req = urllib.request.Request(
        BREVO_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'api-key': os.environ['VELXTRIA_BREVO_API_KEY'],
                 'Content-Type': 'application/json',
                 'accept': 'application/json'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 201:
                raise RuntimeError('Brevo %s' % resp.status)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode('utf-8', 'replace')[:160]
        except Exception:
            detail = ''
        raise RuntimeError('Brevo %s: %s' % (exc.code, detail or exc.msg))


def send_via_sendgrid(recipient, subject, body, attachment=None):
    """Send one plain-text email through SendGrid's HTTPS API.

    attachment is (filename, data_bytes, mimetype). Raises RuntimeError
    with the API's status and message on a non-202 response, so the
    outbox retry/backoff treats it like any other send failure."""
    sender = os.environ.get('VELXTRIA_SMTP_FROM', '').strip()
    if not sender:
        raise RuntimeError('VELXTRIA_SMTP_FROM is not set (it must match '
                           'the verified SendGrid sender)')
    payload = {
        'personalizations': [{'to': [{'email': recipient}]}],
        'from': {'email': sender},
        'subject': subject,
        'content': [{'type': 'text/plain', 'value': body}],
    }
    if attachment is not None:
        filename, data, mimetype = attachment
        payload['attachments'] = [{
            'content': base64.b64encode(data).decode('ascii'),
            'filename': filename,
            'type': mimetype,
            'disposition': 'attachment',
        }]
    req = urllib.request.Request(
        SENDGRID_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + os.environ['VELXTRIA_SENDGRID_API_KEY'],
                 'Content-Type': 'application/json'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 202:
                raise RuntimeError('SendGrid %s' % resp.status)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode('utf-8', 'replace')[:160]
        except Exception:
            detail = ''
        raise RuntimeError('SendGrid %s: %s' % (exc.code, detail or exc.msg))


def send_mail(recipient, subject, body, attachment=None):
    """Send one plain-text email.

    Brevo's HTTPS API first when its key is set (Render's free tier
    blocks outbound SMTP, so SMTP can never work there); SendGrid's
    HTTPS API second; plain SMTP otherwise. attachment is
    (filename, data_bytes, mimetype)."""
    if brevo_configured():
        send_via_brevo(recipient, subject, body, attachment)
        return
    if sendgrid_configured():
        send_via_sendgrid(recipient, subject, body, attachment)
        return
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.environ['VELXTRIA_SMTP_FROM']
    msg['To'] = recipient
    msg.set_content(body)
    if attachment is not None:
        filename, data, mimetype = attachment
        maintype, _, subtype = mimetype.partition('/')
        msg.add_attachment(data, maintype=maintype or 'application',
                           subtype=subtype or 'octet-stream',
                           filename=filename)
    host = os.environ['VELXTRIA_SMTP_HOST']
    port = int(os.getenv('VELXTRIA_SMTP_PORT', '587'))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(os.environ['VELXTRIA_SMTP_USER'],
                   os.environ['VELXTRIA_SMTP_PASSWORD'])
        smtp.send_message(msg)


def queue(conn, recipient, subject, body, kind, dedupe_key=None, user_id=None,
          send_at=None):
    """Queue an email. With a dedupe_key, a second queue for the same key
    is a no-op. Returns True when a row was queued. send_at is a Unix
    timestamp for a scheduled send; the delivery worker only picks a row
    up once its next_attempt has arrived, so a future send_at makes this
    a scheduled follow-up instead of an immediate send."""
    setup(conn)
    due = int(time.time()) if send_at is None else int(send_at)
    cur = conn.execute(
        'INSERT INTO email_outbox'
        '(id,user_id,recipient,subject,body,kind,dedupe_key,status,next_attempt,created)'
        ' VALUES (?,?,?,?,?,?,?,?,?,?)'
        ' ON CONFLICT(dedupe_key) DO NOTHING',
        (secrets.token_hex(16), user_id, recipient, subject, body, kind,
         dedupe_key, 'queued', due, int(time.time())))
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
        # Commit before re-raising: the delivery worker calls process_one
        # inside a transaction that rolls back when the error propagates,
        # which would undo this retry/backoff UPDATE and leave the row
        # 'queued' with 0 attempts, so the worker retries it every loop
        # instead of backing off (observed live: a Brevo 401 retried
        # every ~7s for 13 minutes). Committing first keeps the backoff.
        conn.commit()
        raise
    conn.execute("UPDATE email_outbox SET status='sent',last_error=''"
                 " WHERE id=?", (ident,))
    return True


STALE_SENDING_SECONDS = 300


def reclaim_stale(conn, stale_after=STALE_SENDING_SECONDS, now=None):
    """Return rows stuck in 'sending' to the queue.

    process_one marks a row 'sending' before it calls SMTP. If the process
    is killed mid-send (a redeploy, a spin-down), the row stays 'sending'
    forever because process_one only picks 'queued'/'retry' rows. A row
    still 'sending' after stale_after seconds was abandoned: send it again
    when attempts remain, else mark it failed. Returns how many rows were
    reclaimed.
    """
    setup(conn)
    now = int(time.time()) if now is None else now
    cur = conn.execute(
        "UPDATE email_outbox SET status=CASE WHEN attempts<3 THEN 'retry'"
        " ELSE 'failed' END, next_attempt=? WHERE status='sending'"
        " AND next_attempt<=?",
        (now, now - stale_after))
    claimed = cur.cursor.rowcount if hasattr(cur, 'cursor') else cur.rowcount
    return claimed


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
