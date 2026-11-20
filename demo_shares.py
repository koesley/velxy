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

SHARE_TTL_DAYS = 30


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS demo_shares (
      token TEXT PRIMARY KEY, created INTEGER NOT NULL, expires INTEGER NOT NULL,
      monthly_csv TEXT NOT NULL, product_csv TEXT NOT NULL, stats TEXT NOT NULL,
      accepted INTEGER NOT NULL, rejected INTEGER NOT NULL)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_demo_shares_expires ON demo_shares(expires)')


def _rows_to_csv(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def _csv_to_rows(text):
    return list(csv.reader(io.StringIO(text)))


def create(conn, report):
    """Store a demo run's summaries and return its public share token."""
    setup(conn)
    # Expiration cleanup belongs on writes, never on a public read.
    # This keeps valid public links accessible on read-only replicas and
    # prevents every visitor from acquiring a database write lock.
    now = int(time.time())
    conn.execute('DELETE FROM demo_shares WHERE expires<=?', (now,))
    token = secrets.token_urlsafe(24)
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
