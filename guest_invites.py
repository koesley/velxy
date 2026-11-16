"""VELXTRIA guest invitations: one-time, expiring, account-bound tokens.

Invitations do not grant administrator privileges or paid entitlements.
"""
import hashlib
import secrets
import time

def setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS guest_invites (
        token_hash TEXT PRIMARY KEY,
        expires_at BIGINT NOT NULL,
        redeemed_by BIGINT,
        redeemed_at BIGINT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS guest_access (
        user_id BIGINT PRIMARY KEY,
        expires_at BIGINT NOT NULL
    )""")

def create(db, hours=168, clock=None):
    if not isinstance(hours, int) or not 1 <= hours <= 168:
        raise ValueError("Guest invitations must last between 1 and 168 hours")
    now = int(time.time() if clock is None else clock)
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO guest_invites(token_hash,expires_at,redeemed_by,redeemed_at) VALUES (?,?,NULL,NULL)",
               (hashlib.sha256(token.encode()).hexdigest(), now + hours * 3600))
    return token

def redeem(db, token, user_id, clock=None):
    if not isinstance(token, str) or len(token) > 256 or not token:
        return False
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    now = int(time.time() if clock is None else clock)
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.execute("SELECT expires_at,redeemed_by FROM guest_invites WHERE token_hash=?", (digest,)).fetchone()
    if not row or row[1] is not None or row[0] <= now:
        return False
    updated = db.execute("UPDATE guest_invites SET redeemed_by=?,redeemed_at=? WHERE token_hash=? AND redeemed_by IS NULL AND expires_at>?",
                         (user_id, now, digest, now))
    # sqlite3 and psycopg cursors both expose rowcount; reject races.
    if getattr(updated, 'rowcount', getattr(getattr(updated, 'cursor', None), 'rowcount', None)) != 1:
        return False
    db.execute("INSERT INTO guest_access(user_id,expires_at) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at",
               (user_id, row[0]))
    return True

def active(db, user_id, clock=None):
    now = int(time.time() if clock is None else clock)
    row = db.execute("SELECT expires_at FROM guest_access WHERE user_id=?", (user_id,)).fetchone()
    return bool(row and row[0] > now)
