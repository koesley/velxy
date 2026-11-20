"""Built-in, privacy-friendly site analytics for VELXTRIA.

No cookies, no third-party tracker, no IP addresses, no user agents, no
personal data. One append-only table records funnel events — landing
views, demo runs, sign-ups, reports generated, checkout starts, paywall
views, PRO activations — with a short non-personal detail string. The
founder reads them on /founder-stats; nothing leaves the site's own
database, and a failed write never breaks the request it was logging.
"""

import time
import html
import math
from datetime import datetime, timezone

EVENTS = ('landing_view', 'about_view', 'demo_run', 'signup',
          'report_generated', 'checkout_started', 'paywall_shown',
          'pro_activated')

# The funnel, in order: each step's conversion is measured against the
# one before it on the stats page.
FUNNEL = ('landing_view', 'demo_run', 'signup', 'report_generated',
          'checkout_started', 'pro_activated')

LABELS = {
    'landing_view': 'Landing page views',
    'about_view': 'About page views',
    'demo_run': 'Demo reports generated',
    'signup': 'Accounts created',
    'report_generated': 'Reports generated (signed in)',
    'checkout_started': 'BTCPay checkouts started',
    'paywall_shown': 'Free-limit paywall views',
    'pro_activated': 'PRO activations',
}


def ensure(conn):
    """Create the events table if it is missing (portable: no sequences,
    no primary key — an append-only log needs neither)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS site_events "
        "(created INTEGER NOT NULL, event TEXT NOT NULL, "
        "detail TEXT NOT NULL DEFAULT '')")


def record(conn, event, detail='', created=None):
    """Append one event. Never raises: analytics must not break the
    request it is logging."""
    try:
        if event not in EVENTS:
            return
        ensure(conn)
        conn.execute(
            'INSERT INTO site_events (created, event, detail) VALUES (?,?,?)',
            (int(created if created is not None else time.time()),
             event, str(detail)[:240]))
    except Exception as exc:  # noqa: BLE001 - analytics must not fail a request
        print('site_stats record failed:', type(exc).__name__, flush=True)


def summary(conn, days=14):
    """Return (totals, daily, recent).

    totals: {event: all-time count}. daily: [(day_start_epoch,
    {event: count})] for the last `days` days, oldest first. recent:
    [(created, event, detail)] newest first, capped at 50.
    """
    ensure(conn)
    totals = {e: 0 for e in EVENTS}
    for event, n in conn.execute(
            'SELECT event, count(*) FROM site_events GROUP BY event'):
        if event in totals:
            totals[event] = n
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 90:
        raise ValueError('days must be an integer between 1 and 90')
    # UTC calendar days, including today; avoid rolling 24-hour windows.
    today = int(time.time()) // 86400 * 86400
    since = today - (days - 1) * 86400
    by_day = {}
    for event, day, n in conn.execute(
            'SELECT event, created/86400, count(*) FROM site_events '
            'WHERE created>=? GROUP BY event, created/86400 '
            'ORDER BY created/86400',
            (since,)):
        by_day.setdefault(int(day) * 86400, {})[event] = n
    daily = [(since + i * 86400, by_day.get(since + i * 86400, {}))
             for i in range(days)]
    recent = conn.execute(
        'SELECT created, event, detail FROM site_events '
        'ORDER BY created DESC LIMIT 50').fetchall()
    return totals, daily, recent


def _day_label(day_start):
    return datetime.fromtimestamp(day_start, timezone.utc).strftime('%Y-%m-%d')


def stats_html(totals, daily, recent):
    """Founder stats page: funnel, per-day counts, recent events."""
    funnel_rows = ''
    for event in FUNNEL:
        count = max(0, int(totals.get(event, 0)))
        # Anonymous events cannot be joined into unique visitor cohorts.
        # Never present a ratio of unrelated event counts as conversion.
        conv = 'Not measured'
        funnel_rows += ('<tr><td>' + LABELS[event] + '</td><td>' + str(count) +
                        '</td><td>' + conv + '</td></tr>')
    totals_rows = ''.join(
        '<tr><td>' + LABELS[e] + '</td><td>' + str(max(0, int(totals.get(e, 0)))) + '</td></tr>'
        for e in EVENTS)
    day_header = ''.join('<th>' + LABELS[e] + '</th>' for e in FUNNEL)
    day_rows = ''
    for day_start, counts in daily:
        day_rows += '<tr><td>' + _day_label(day_start) + '</td>' + ''.join(
            '<td>' + str(max(0, int(counts.get(e, 0)))) + '</td>' for e in FUNNEL) + '</tr>'
    recent_rows = ''.join(
        '<tr><td>' + datetime.fromtimestamp(
            r[0], timezone.utc).strftime('%Y-%m-%d %H:%M UTC') +
        '</td><td>' + html.escape(LABELS.get(r[1], str(r[1])), quote=True) +
        '</td><td>' + html.escape(str(r[2] or ''), quote=True) + '</td></tr>'
        for r in recent)
    return ('<section class="panel"><h2>Funnel</h2><p>All-time counts; '
            'event counts are not unique-user conversion rates. No visitor tracking is performed.</p><table><thead><tr>'
            '<th>Step</th><th>Count</th><th>Conversion rate</th></tr></thead><tbody>' +
            funnel_rows + '</tbody></table></section>'
            '<section class="panel"><h2>Totals</h2><table><thead><tr>'
            '<th>Event</th><th>All time</th></tr></thead><tbody>' +
            totals_rows + '</tbody></table></section>'
            '<section class="panel"><h2>Last 14 days (UTC)</h2><table><thead><tr>'
            '<th>Day (UTC)</th>' + day_header + '</tr></thead><tbody>' +
            (day_rows or '<tr><td colspan="7">No events yet.</td></tr>') +
            '</tbody></table></section>'
            '<section class="panel"><h2>Recent events</h2><table><thead><tr>'
            '<th>When</th><th>Event</th><th>Detail</th></tr></thead><tbody>' +
            (recent_rows or '<tr><td colspan="3">No events yet.</td></tr>') +
            '</tbody></table><p>Counts include automated traffic (no bot '
            'filtering yet). Event details may contain manually supplied text; avoid entering personal data. No IP '
            'addresses, no user agents, no emails.</p></section>'
            '<p><a href="/">Back to dashboard</a></p>')
