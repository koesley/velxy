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

MAX_ROWS = 1000
MAX_COLUMNS = 32
MAX_CELL_CHARS = 4096
MAX_STATS = 50
MAX_STAT_CHARS = 4096
MAX_SERIALIZED_CHARS = 1_000_000

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


def _validated_rows(value, field):
    if not isinstance(value, (list, tuple)) or not value or len(value) > MAX_ROWS:
        raise ValueError(f'{field} has an invalid row count')
    width = None
    for row in value:
        if not isinstance(row, (list, tuple)) or not 1 <= len(row) <= MAX_COLUMNS:
            raise ValueError(f'{field} has an invalid row')
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(f'{field} has inconsistent columns')
        if any(not isinstance(cell, str) or len(cell) > MAX_CELL_CHARS for cell in row):
            raise ValueError(f'{field} has an invalid cell')
    return value


def _validated_report(report):
    if not isinstance(report, dict):
        raise ValueError('Invalid share report')
    monthly = _validated_rows(report.get('monthly_rows'), 'monthly_rows')
    products = _validated_rows(report.get('product_rows'), 'product_rows')
    stats = report.get('stats')
    if not isinstance(stats, (list, tuple)) or len(stats) > MAX_STATS or any(
        not isinstance(s, str) or len(s) > MAX_STAT_CHARS or '\\n' in s or '\\r' in s
        for s in stats
    ):
        raise ValueError('Invalid share statistics')
    accepted, rejected = report.get('accepted'), report.get('rejected')
    if any(type(v) is not int or v < 0 for v in (accepted, rejected)):
        raise ValueError('Invalid share counters')
    monthly_csv = _rows_to_csv(monthly)
    product_csv = _rows_to_csv(products)
    stats_text = '\\n'.join(stats)
    if sum(map(len, (monthly_csv, product_csv, stats_text))) > MAX_SERIALIZED_CHARS:
        raise ValueError('Share summary is too large')
    return monthly_csv, product_csv, stats_text, accepted, rejected


def create(conn, report):
    """Store a demo run's summaries and return its public share token."""
    monthly_csv, product_csv, stats_text, accepted, rejected = _validated_report(report)
    setup(conn)
    token = secrets.token_urlsafe(24)
    now = int(time.time())
    conn.execute('DELETE FROM demo_shares WHERE expires<=?', (now,))
    conn.execute(
        'INSERT INTO demo_shares'
        '(token,created,expires,monthly_csv,product_csv,stats,accepted,rejected)'
        ' VALUES (?,?,?,?,?,?,?,?)',
        (token, now, now + SHARE_TTL_DAYS * 86400,
         monthly_csv, product_csv, stats_text, accepted, rejected))
    return token


def get(conn, token):
    """A shared demo's summaries, or None when unknown or expired."""
    if not isinstance(token, str) or not 16 <= len(token) <= 128 or any(
        ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for ch in token
    ):
        return None
    setup(conn)
    now = int(time.time())
    conn.execute('DELETE FROM demo_shares WHERE expires<=?', (now,))
    row = conn.execute(
        'SELECT monthly_csv,product_csv,stats,accepted,rejected'
        ' FROM demo_shares WHERE token=?', (token,)).fetchone()
    if not row:
        return None
    return {
        'monthly_rows': _csv_to_rows(row[0]),
        'product_rows': _csv_to_rows(row[1]),
        'stats': [line for line in row[2].splitlines() if line],
        'accepted': row[3],
        'rejected': row[4],
    }
