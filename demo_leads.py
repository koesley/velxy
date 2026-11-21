"""Demo lead capture: email the instant-demo report to the runner.

The demo converts far worse than it should: hundreds of demo runs produce
almost no signups, because the result page's only next step for an
anonymous runner is a small "create a free account" link — and once they
leave, they are gone (anonymous, no way to follow up). This module records
who asked for their demo report by email, so the report lands in their
inbox with a signup link and the founder has a lead to follow up.

Abuse bounds: the endpoint sends email to an address the requester
chooses, so it is capped — one email per (address, demo) ever, and at
most 3 demo emails to the same address per day. A resubmit past either
cap is a silent no-op (the caller still shows the same confirmation,
so the cap cannot be probed).
"""
import time

DAILY_CAP = 3
# Anonymous public form: bound abuse across many recipient addresses and
# across many different public demo links, not just per recipient.
SHARE_DAILY_CAP = 25
SITE_DAILY_CAP = 500
DAY = 86400


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS demo_leads (
      email TEXT NOT NULL, share_token TEXT NOT NULL, created INTEGER NOT NULL,
      PRIMARY KEY (email, share_token))''')


def record(conn, email, share_token, now=None):
    """Record a demo-report email request. Returns True when this is a
    new (email, demo) pair under all three daily caps and the email should
    be sent; False for duplicates or exhausted budgets."""
    setup(conn)
    email = email.strip().lower()
    if not email or not share_token:
        return False
    now = int(time.time()) if now is None else int(now)
    # One SQL statement checks all three budgets and inserts only if eligible.
    # This is portable to SQLite and PostgreSQL, avoids multiple read/write
    # round trips, and retains the existing unique-pair idempotency rule.
    cur = conn.execute(
        'INSERT INTO demo_leads (email, share_token, created) '
        'SELECT ?, ?, ? WHERE '
        '(SELECT COUNT(*) FROM demo_leads WHERE email=? AND created>?) < ? '
        'AND (SELECT COUNT(*) FROM demo_leads WHERE share_token=? AND created>?) < ? '
        'AND (SELECT COUNT(*) FROM demo_leads WHERE created>?) < ? '
        'ON CONFLICT(email, share_token) DO NOTHING',
        (email, share_token, now,
         email, now - DAY, DAILY_CAP,
         share_token, now - DAY, SHARE_DAILY_CAP,
         now - DAY, SITE_DAILY_CAP))
    claimed = cur.cursor.rowcount if hasattr(cur, 'cursor') else cur.rowcount
    return claimed == 1


def format_email_body(shared, share_link, site_url):
    """Plain-text body for the emailed demo report: headline stats, the
    monthly and product summaries, the share link, and the signup call
    to action. Only the aggregated summaries — never the file or a raw
    row."""
    lines = ['Your VELXTRIA demo report is ready.',
             '',
             'Accepted %d rows · flagged %d rows.' % (
                 shared['accepted'], shared['rejected']),
             '']
    if shared['stats']:
        lines.append('Headline:')
        lines.extend(shared['stats'])
        lines.append('')
    if shared['monthly_rows']:
        lines.append('Monthly summary:')
        for row in shared['monthly_rows']:
            lines.append(' | '.join(row))
        lines.append('')
    if shared['product_rows']:
        lines.append('Product summary:')
        for row in shared['product_rows']:
            lines.append(' | '.join(row))
        lines.append('')
    lines.append('View it online: ' + share_link)
    lines.append('The link shows only these summaries — never your file or '
                 'a raw row — and works for 30 days.')
    lines.append('')
    lines.append('Keep your reports: create a free account (3 free reports) '
                 'at ' + site_url.rstrip('/') + '/register — then claim this '
                 'demo from your dashboard.')
    lines.append('')
    lines.append('— VELXTRIA')
    return '\n'.join(lines)
