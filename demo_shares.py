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
import json
import secrets
import time

SHARE_TTL_DAYS = 30
SCORECARD_TOP_ISSUES = 3


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS demo_shares (
      token TEXT PRIMARY KEY, created INTEGER NOT NULL, expires INTEGER NOT NULL,
      monthly_csv TEXT NOT NULL, product_csv TEXT NOT NULL, stats TEXT NOT NULL,
      accepted INTEGER NOT NULL, rejected INTEGER NOT NULL,
      top_issues TEXT NOT NULL DEFAULT '')''')
    _ensure_top_issues_column(conn)


def _ensure_top_issues_column(conn):
    """Add the stored top-issues column to shares created before the
    scorecard. Old rows keep an empty list; the percentage, problem
    count and paid revenue are always derivable from the stored
    summaries."""
    import persistent
    if persistent.REMOTE:
        conn.execute("ALTER TABLE demo_shares ADD COLUMN IF NOT EXISTS top_issues TEXT NOT NULL DEFAULT ''")
        return
    cols = [row[1] for row in conn.execute('PRAGMA table_info(demo_shares)').fetchall()]
    if 'top_issues' not in cols:
        conn.execute("ALTER TABLE demo_shares ADD COLUMN top_issues TEXT NOT NULL DEFAULT ''")


def scorecard(report):
    """Aggregate a demo run into its scorecard: % clean, problems found,
    top issue types, paid revenue. Summaries and counts only — the issue
    labels are the engine's generic categories ('duplicate order ID',
    'invalid date', ...), never a raw row, customer name, or file
    content."""
    accepted = report.get('accepted', 0)
    rejected = report.get('rejected', 0)
    source = accepted + rejected
    counts = {}
    for row in (report.get('rejected_rows') or [])[1:]:
        if len(row) > 9:
            for issue in row[9].split(';'):
                issue = issue.strip()
                if issue:
                    counts[issue] = counts.get(issue, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:SCORECARD_TOP_ISSUES]
    paid = ''
    for line in report.get('stats') or []:
        if line.startswith('Paid revenue'):
            paid = line.split(':', 1)[-1].strip()
            break
    return {'clean_pct': round(100 * accepted / source) if source else 100,
            'problems': rejected,
            'top_issues': [[issue, n] for issue, n in top],
            'paid': paid}


def _scorecard_from_stored(accepted, rejected, top_issues_json, stats):
    """Rebuild the scorecard from stored columns."""
    top = []
    try:
        raw = json.loads(top_issues_json) if top_issues_json else []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                top.append([str(item[0]), int(item[1])])
    except (ValueError, TypeError):
        top = []
    paid = ''
    for line in stats:
        if line.startswith('Paid revenue'):
            paid = line.split(':', 1)[-1].strip()
            break
    source = accepted + rejected
    return {'clean_pct': round(100 * accepted / source) if source else 100,
            'problems': rejected,
            'top_issues': top,
            'paid': paid}


def _rows_to_csv(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def _csv_to_rows(text):
    return list(csv.reader(io.StringIO(text)))


def create(conn, report):
    """Store a demo run's summaries and return its public share token."""
    setup(conn)
    token = secrets.token_urlsafe(24)
    now = int(time.time())
    card = scorecard(report)
    conn.execute(
        'INSERT INTO demo_shares'
        '(token,created,expires,monthly_csv,product_csv,stats,accepted,rejected,top_issues)'
        ' VALUES (?,?,?,?,?,?,?,?,?)',
        (token, now, now + SHARE_TTL_DAYS * 86400,
         _rows_to_csv(report['monthly_rows']),
         _rows_to_csv(report['product_rows']),
         '\n'.join(report['stats']),
         report['accepted'], report['rejected'],
         json.dumps(card['top_issues'])))
    return token


def get(conn, token):
    """A shared demo's summaries and scorecard, or None when unknown or
    expired."""
    setup(conn)
    now = int(time.time())
    conn.execute('DELETE FROM demo_shares WHERE expires<=?', (now,))
    row = conn.execute(
        'SELECT monthly_csv,product_csv,stats,accepted,rejected,top_issues'
        ' FROM demo_shares WHERE token=? AND expires>?', (token, now)).fetchone()
    if not row:
        return None
    stats = [line for line in row[2].splitlines() if line]
    return {
        'monthly_rows': _csv_to_rows(row[0]),
        'product_rows': _csv_to_rows(row[1]),
        'stats': stats,
        'accepted': row[3],
        'rejected': row[4],
        'scorecard': _scorecard_from_stored(row[3], row[4], row[5], stats),
    }
