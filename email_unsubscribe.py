"""Marketing-email opt-out: one-click unsubscribe for the Automatic
Revenue Engine's sequences.

The site's marketing mail — the welcome sequence, the demo-lead
follow-ups, and the PRO upsells — had no way out: no unsubscribe link
and no suppression list, so a recipient who asked to stop still got
every step. This module is the opt-out:

- email_unsubscribes table: the lowercased email (primary key), a
  random per-email token, and an unsubscribed flag. The token row is
  created when a marketing email is queued (the footer link needs a
  stable token), so row existence alone does NOT mean opted out — only
  the flag does.
- get_or_create_token(conn, email): the token for an email, stable
  across every email sent to that address.
- unsubscribe_url(email, site_url, token): the one-click link.
- append_footer(body, email, site_url, token): the footer every
  marketing body carries.
- is_unsubscribed(conn, email): True only when the flag is set.
- record_unsubscribe(conn, email, token): constant-time token check;
  True only when the token matches the stored one, and records the
  suppression. Idempotent. Returns False for an unknown email or a
  wrong token, without revealing which.

Transactional mail — password resets, PRO confirmations, renewal
reminders, and the "Email me this report" demo email — never consults
this table and always sends.
"""
import hashlib
import hmac
import secrets
import time
import urllib.parse


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS email_unsubscribes (
      email TEXT PRIMARY KEY, token TEXT NOT NULL,
      unsubscribed INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL)''')


def _norm(email):
    return (email or '').strip().lower()


def get_or_create_token(conn, email):
    """The unsubscribe token for an email, creating the row (and a
    fresh token) on first use. The token is stable afterwards, so every
    marketing email to this address carries the same working link."""
    setup(conn)
    email = _norm(email)
    row = conn.execute(
        'SELECT token FROM email_unsubscribes WHERE email=?',
        (email,)).fetchone()
    if row:
        return row[0]
    token = secrets.token_urlsafe(24)
    conn.execute(
        'INSERT INTO email_unsubscribes'
        ' (email, token, unsubscribed, created) VALUES (?,?,0,?)'
        ' ON CONFLICT(email) DO NOTHING',
        (email, token, int(time.time())))
    row = conn.execute(
        'SELECT token FROM email_unsubscribes WHERE email=?',
        (email,)).fetchone()
    return row[0]


def unsubscribe_url(email, site_url, token):
    """The one-click unsubscribe link for an email and its token."""
    return (site_url.rstrip('/') + '/unsubscribe?email='
            + urllib.parse.quote(_norm(email), safe='')
            + '&token=' + urllib.parse.quote(token, safe=''))


def append_footer(body, email, site_url, token):
    """Append the unsubscribe footer to a marketing body."""
    return (body.rstrip('\n') + '\n\nTo stop these emails: '
            + unsubscribe_url(email, site_url, token) + '\n')


def is_unsubscribed(conn, email):
    """True only when this address has opted out. A token row created
    for the footer link does not count — only the flag does."""
    setup(conn)
    row = conn.execute(
        'SELECT unsubscribed FROM email_unsubscribes WHERE email=?',
        (_norm(email),)).fetchone()
    return bool(row and row[0])


def record_unsubscribe(conn, email, token):
    """Record an opt-out when the token matches the stored one.
    Returns True only on a match; False for an unknown email, a
    missing token, or a wrong token — without revealing which. The
    stored token is never logged or returned."""
    setup(conn)
    email = _norm(email)
    if not email or not token:
        return False
    row = conn.execute(
        'SELECT token FROM email_unsubscribes WHERE email=?',
        (email,)).fetchone()
    if not row:
        return False
    if not hmac.compare_digest(token, row[0]):
        return False
    conn.execute(
        'UPDATE email_unsubscribes SET unsubscribed=1 WHERE email=?',
        (email,))
    return True
