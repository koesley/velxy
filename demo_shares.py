"""Shareable demo results: every instant demo gets a public link.

A demo run stores only the aggregated summaries (monthly + product rows
and headline stats) under a random token — never the uploaded file, never
a raw row. Anyone with the link sees the same summaries on a public page
with a "try it with your own CSV" call to action, so every demo is an
ad for the next user. Links expire after 30 days; expired rows are
dropped on the next share lookup.
"""
import csv
import io
import secrets
import time

MAX_TOKEN_LENGTH = 128
CLEANUP_BATCH = 100

SHARE_TTL_DAYS = 30


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS demo_shares (
      token TEXT PRIMARY KEY, created INTEGER NOT NULL, expires INTEGER NOT NULL,
      monthly_csv TEXT NOT NULL, product_csv TEXT NOT NULL, stats TEXT NOT NULL,
      accepted INTEGER NOT NULL, rejected INTEGER NOT NULL)''')


def _rows_to_csv(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def _csv_to_rows(text):
    return list(csv.reader(io.StringIO(text)))


def cleanup_expired(conn, now=None, batch=CLEANUP_BATCH):
    """Bound expiration cleanup to a small batch on write paths only."""
    if not isinstance(batch, int) or not 1 <= batch <= 1000:
        raise ValueError('invalid cleanup batch')
    cutoff = int(time.time()) if now is None else int(now)
    tokens = conn.execute(
        'SELECT token FROM demo_shares WHERE expires<=? '
        'ORDER BY expires, token LIMIT ?', (cutoff, batch)).fetchall()
    if not tokens:
        return 0
    conn.executemany('DELETE FROM demo_shares WHERE token=? AND expires<=?',
                     [(row[0], cutoff) for row in tokens])
    return len(tokens)


def create(conn, report):
    """Store a demo run's summaries and return its public share token."""
    setup(conn)
    cleanup_expired(conn)
    token = secrets.token_urlsafe(24)
    now = int(time.time())
    conn.execute(
        'INSERT INTO demo_shares'
        '(token,created,expires,monthly_csv,product_csv,stats,accepted,rejected)'
        ' VALUES (?,?,?,?,?,?,?,?)',
        (token, now, now + SHARE_TTL_DAYS * 86400,
         _rows_to_csv(report['monthly_rows']),
         _rows_to_csv(report['product_rows']),
         '\n'.join(report['stats']),
         report['accepted'], report['rejected']))
    return token


def get(conn, token):
    """A shared demo's summaries, or None when unknown or expired."""
    setup(conn)
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH or not all(c.isalnum() or c in '-_' for c in token):
        return None
    now = int(time.time())
    row = conn.execute(
        'SELECT monthly_csv,product_csv,stats,accepted,rejected'
        ' FROM demo_shares WHERE token=? AND expires>?', (token, now)).fetchone()
    if not row:
        return None
    return {
        'monthly_rows': _csv_to_rows(row[0]),
        'product_rows': _csv_to_rows(row[1]),
        'stats': [line for line in row[2].splitlines() if line],
        'accepted': row[3],
        'rejected': row[4],
    }
