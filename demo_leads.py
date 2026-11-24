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
DAY = 86400


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS demo_leads (
      email TEXT NOT NULL, share_token TEXT NOT NULL, created INTEGER NOT NULL,
      PRIMARY KEY (email, share_token))''')


def record(conn, email, share_token, now=None):
    """Record a demo-report email request. Returns True when this is a
    new (email, demo) pair under the daily cap and the email should be
    sent; False when it is a duplicate or the address is over its cap."""
    setup(conn)
    now = int(time.time()) if now is None else now
    row = conn.execute(
        'SELECT COUNT(*) FROM demo_leads WHERE email=? AND created>?',
        (email, now - DAY)).fetchone()
    if row and row[0] >= DAILY_CAP:
        return False
    cur = conn.execute(
        'INSERT INTO demo_leads (email, share_token, created) VALUES (?,?,?)'
        ' ON CONFLICT(email, share_token) DO NOTHING',
        (email, share_token, now))
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
    lines.append('Recommended next step:')
    from demo_guidance import recommend
    lines.append(recommend(shared['accepted'], shared['rejected'], channel='email'))
    lines.append('')
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
    lines.append('Turn this demo into a report you can revisit:')
    lines.append('1. Create a free account (1 free report) at ' +
                 site_url.rstrip('/') + '/register')
    lines.append('2. Claim this demo from your dashboard.')
    lines.append('3. Revisit your sales summaries and use them to review '
                 'monthly performance and product results.')
    lines.append('Your demo link remains available without registering.')
    lines.append('')
    lines.append('— VELXTRIA')
    return '\n'.join(lines)
