"""Bounded, expiring public demo summaries.

Only aggregate report rows are stored; uploads and raw orders are never retained.
"""
import csv
import io
import re
import secrets
import time

SHARE_TTL_DAYS = 30
MAX_SUMMARY_ROWS = 1000
MAX_SUMMARY_COLUMNS = 32
MAX_CELL_CHARS = 4096
MAX_STATS_LINES = 30
MAX_STATS_CHARS = 8192
MAX_CSV_CHARS = 512_000
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32,64}\Z")


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS demo_shares (
      token TEXT PRIMARY KEY, created INTEGER NOT NULL, expires INTEGER NOT NULL,
      monthly_csv TEXT NOT NULL, product_csv TEXT NOT NULL, stats TEXT NOT NULL,
      accepted INTEGER NOT NULL, rejected INTEGER NOT NULL)''')


def _rows_to_csv(rows):
    if not isinstance(rows, (list, tuple)) or len(rows) > MAX_SUMMARY_ROWS:
        raise ValueError("Demo summary exceeds row limit")
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) > MAX_SUMMARY_COLUMNS:
            raise ValueError("Invalid demo summary columns")
        if any(not isinstance(cell, str) or len(cell) > MAX_CELL_CHARS
               for cell in row):
            raise ValueError("Invalid demo summary cell")
        writer.writerow(row)
        if buf.tell() > MAX_CSV_CHARS:
            raise ValueError("Demo summary exceeds storage limit")
    return buf.getvalue()


def _csv_to_rows(value):
    return list(csv.reader(io.StringIO(value)))


def _validate_report(report):
    if not isinstance(report, dict):
        raise ValueError("Invalid demo report")
    monthly = _rows_to_csv(report['monthly_rows'])
    products = _rows_to_csv(report['product_rows'])
    stats = report['stats']
    if (not isinstance(stats, (list, tuple)) or len(stats) > MAX_STATS_LINES
            or any(not isinstance(s, str) or '\n' in s or '\r' in s
                   for s in stats)):
        raise ValueError("Invalid demo statistics")
    stats_text = '\n'.join(stats)
    if len(stats_text) > MAX_STATS_CHARS:
        raise ValueError("Demo statistics exceed storage limit")
    for key in ('accepted', 'rejected'):
        count = report[key]
        if type(count) is not int or count < 0 or count > 1_000_000:
            raise ValueError("Invalid demo record count")
    return monthly, products, stats_text


def create(conn, report):
    """Store bounded aggregated results and return a random public share token."""
    monthly, products, stats = _validate_report(report)
    setup(conn)
    token = secrets.token_urlsafe(24)
    now = int(time.time())
    conn.execute(
        'INSERT INTO demo_shares'
        '(token,created,expires,monthly_csv,product_csv,stats,accepted,rejected)'
        ' VALUES (?,?,?,?,?,?,?,?)',
        (token, now, now + SHARE_TTL_DAYS * 86400,
         monthly, products, stats, report['accepted'], report['rejected']))
    return token


def get(conn, token):
    """Return a live aggregate share, never an expired or malformed token."""
    if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
        return None
    setup(conn)
    now = int(time.time())
    conn.execute('DELETE FROM demo_shares WHERE expires<=?', (now,))
    row = conn.execute(
        'SELECT monthly_csv,product_csv,stats,accepted,rejected'
        ' FROM demo_shares WHERE token=? AND expires>?', (token, now)).fetchone()
    if row is None:
        return None
    return {
        'monthly_rows': _csv_to_rows(row[0]),
        'product_rows': _csv_to_rows(row[1]),
        'stats': [line for line in row[2].splitlines() if line],
        'accepted': row[3],
        'rejected': row[4],
    }
