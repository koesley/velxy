"""Password reset: a single-use, one-hour token sent to the account email.

Only the token hash is stored, so a database read can never leak a live
reset link. A new request replaces the old token; requests within five
minutes of the last one do not send a second email.
"""
import hashlib
import hmac
import secrets
import time

TOKEN_TTL = 3600
RESEND_WAIT = 300


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS password_resets (
      user_id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL,
      expires INTEGER NOT NULL, created INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id))''')


def request_reset(conn, user_id, email, site_url):
    """Create (or replace) a reset token and queue the email.

    Returns the token when an email was queued, else None (a recent
    request already has an email on its way). Callers always show the
    same message either way, so this never reveals whether an email
    exists.
    """
    import notifications
    setup(conn)
    now = int(time.time())
    row = conn.execute('SELECT created FROM password_resets WHERE user_id=?',
                       (user_id,)).fetchone()
    if row and now - row[0] < RESEND_WAIT:
        return None
    token = secrets.token_urlsafe(32)
    conn.execute(
        'INSERT INTO password_resets(user_id,token_hash,expires,created)'
        ' VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET'
        ' token_hash=excluded.token_hash,expires=excluded.expires,'
        'created=excluded.created',
        (user_id, hashlib.sha256(token.encode()).hexdigest(),
         now + TOKEN_TTL, now))
    link = site_url.rstrip('/') + '/reset?token=' + token
    notifications.queue(
        conn, email, 'Reset your VELXTRIA password',
        'Someone asked to reset the password for this VELXTRIA account. '
        'Use this link within one hour (it works once):\n\n%s\n\n'
        'If that was not you, ignore this email — your password is '
        'unchanged.\n\n— VELXTRIA' % link,
        'password_reset', user_id=user_id)
    return token


def verify_token(conn, token):
    """The user id behind a live reset token, or None."""
    setup(conn)
    if not token:
        return None
    row = conn.execute(
        'SELECT user_id,expires FROM password_resets WHERE token_hash=?',
        (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row or row[1] <= int(time.time()):
        return None
    return row[0]


def consume_token(conn, token):
    """Delete a token after use (single-use). Returns the user id or None."""
    user_id = verify_token(conn, token)
    if user_id is None:
        return None
    conn.execute('DELETE FROM password_resets WHERE user_id=?', (user_id,))
    return user_id


def set_password(conn, user_id, password):
    """Replace the account password (new salt + hash)."""
    import portal
    salt = secrets.token_hex(16)
    conn.execute('UPDATE users SET salt=?,pw_hash=? WHERE id=?',
                 (salt, portal.pw_hash(password, salt), user_id))
