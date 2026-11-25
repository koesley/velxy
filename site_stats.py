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
import urllib.parse
from datetime import datetime, timezone

EVENTS = ('landing_view', 'about_view', 'demo_run', 'demo_email_sent',
          'signup', 'report_generated', 'checkout_started', 'paywall_shown',
          'pro_activated', 'checkout_unavailable', 'checkout_failed')

# The funnel, in order: each step's conversion is measured against the
# one before it on the stats page (event ratios, not cohort conversion).
FUNNEL = ('landing_view', 'demo_run', 'demo_email_sent', 'signup',
          'report_generated', 'checkout_started', 'pro_activated')

LABELS = {
    'landing_view': 'Landing page views',
    'about_view': 'About page views',
    'demo_run': 'Demo reports generated',
    'demo_email_sent': 'Demo reports emailed',
    'signup': 'Accounts created',
    'report_generated': 'Reports generated (signed in)',
    'checkout_started': 'Payment checkouts started',
    'checkout_unavailable': 'Checkout unavailable',
    'checkout_failed': 'Checkout creation failed',
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
    """Best-effort analytics without poisoning the caller's transaction.

    PostgreSQL marks a transaction aborted after a SQL error. A SAVEPOINT
    allows optional analytics writes to fail without rolling back the
    caller's business operation. Never commit here: the caller owns the
    transaction.
    """
    savepoint = False
    try:
        conn.execute('SAVEPOINT vx_site_stats_record')
        savepoint = True
        ensure(conn)
        conn.execute(
            'INSERT INTO site_events (created, event, detail) VALUES (?,?,?)',
            (int(created if created is not None else time.time()),
             event, str(detail)[:240]))
        conn.execute('RELEASE SAVEPOINT vx_site_stats_record')
        savepoint = False
    except Exception as exc:  # optional telemetry must not break business writes
        if savepoint:
            try:
                conn.execute('ROLLBACK TO SAVEPOINT vx_site_stats_record')
                conn.execute('RELEASE SAVEPOINT vx_site_stats_record')
            except Exception:
                pass
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
    since = int(time.time()) - days * 86400
    by_day = {}
    for event, day, n in conn.execute(
            'SELECT event, CAST(created / 86400 AS INTEGER), count(*) FROM site_events '
            'WHERE created>=? GROUP BY event, CAST(created / 86400 AS INTEGER) '
            'ORDER BY CAST(created / 86400 AS INTEGER)',
            (since,)):
        by_day.setdefault(int(day) * 86400, {})[event] = n
    daily = [(day, by_day[day]) for day in sorted(by_day)]
    recent = conn.execute(
        'SELECT created, event, detail FROM site_events '
        'ORDER BY created DESC LIMIT 50').fetchall()
    return totals, daily, recent


def _day_label(day_start):
    return datetime.fromtimestamp(day_start, timezone.utc).strftime('%Y-%m-%d')


def checkout_health(daily):
    """Aggregate recent checkout events, not individual customer journeys."""
    keys = ('checkout_started', 'checkout_unavailable', 'checkout_failed', 'pro_activated')
    counts = {key: sum(row.get(key, 0) for _, row in daily) for key in keys}
    if counts['checkout_unavailable']:
        action = 'Verify enabled payment providers and checkout configuration.'
    elif counts['checkout_failed']:
        action = 'Inspect checkout creation errors and provider connectivity.'
    elif not counts['checkout_started']:
        action = 'Test the paid offer and checkout entry points.'
    elif not counts['pro_activated']:
        action = 'Reconcile provider settlements and access activation.'
    else:
        action = 'Review verified settlements and customer feedback.'
    return counts, action


def checkout_health_html(daily):
    counts, action = checkout_health(daily)
    rows = ''.join('<li>' + LABELS[key] + ': ' + str(value) + '</li>'
                   for key, value in counts.items())
    return ('<section class="panel"><h2>Checkout health — last 14 days</h2><ul>'
            + rows + '</ul><p><strong>Next action:</strong> ' + action
            + '</p><p>Event counts are not unique buyers, abandonment rates or verified revenue.</p></section>')


def stats_html(totals, daily, recent):
    """Founder stats page: funnel, per-day counts, recent events."""
    funnel_rows = ''
    prev = None
    for event in FUNNEL:
        count = totals.get(event, 0)
        conv = ''
        if prev is not None:
            conv = ('%.1f%%' % (100.0 * count / prev)) if prev else '—'
        funnel_rows += ('<tr><td>' + LABELS[event] + '</td><td>' + str(count) +
                        '</td><td>' + conv + '</td></tr>')
        prev = count
    recent_counts = {event: sum(counts.get(event, 0) for _, counts in daily) for event in FUNNEL}
    recent_summary = ''.join('<li>' + LABELS[event] + ': ' + str(recent_counts[event]) + '</li>' for event in FUNNEL)
    counts = {event: sum(row.get(event, 0) for _, row in daily) for event in FUNNEL}
    if not counts['landing_view']:
        guidance = 'Check public access and acquisition channels; no landing views were recorded.'
    elif not counts['demo_run']:
        guidance = 'Inspect the landing-to-demo experience; no demo runs were recorded.'
    elif not counts['signup']:
        guidance = 'Inspect registration and the demo call to action; no signups were recorded.'
    elif not counts['checkout_started']:
        guidance = 'Inspect the paid offer and checkout availability; no checkout starts were recorded.'
    elif not counts['pro_activated']:
        guidance = 'Inspect payment verification and activation; no PRO activations were recorded.'
    else:
        guidance = 'Review verified payments and customer feedback before changing the offer.'
    actions = (
        ('landing_view', 'Verify public accessibility and test a targeted acquisition channel.'),
        ('demo_run', 'Test the demo from a new browser session.'),
        ('signup', 'Test registration and inspect the demo signup invitation.'),
        ('report_generated', 'Test first-report onboarding with an authorized test account.'),
        ('checkout_started', 'Verify the paid offer and available checkout methods.'),
        ('pro_activated', 'Reconcile verified settlements against granted access.'),
    )
    missing = [(event, action) for event, action in actions if not counts.get(event, 0)]
    action_rows = ''.join('<li>' + action + '</li>' for _, action in missing)
    totals_rows = ''.join(
        '<tr><td>' + LABELS[e] + '</td><td>' + str(totals.get(e, 0)) + '</td></tr>'
        for e in EVENTS)
    day_header = ''.join('<th>' + LABELS[e] + '</th>' for e in FUNNEL)
    day_rows = ''
    for day_start, counts in daily:
        day_rows += '<tr><td>' + _day_label(day_start) + '</td>' + ''.join(
            '<td>' + str(counts.get(e, 0)) + '</td>' for e in FUNNEL) + '</tr>'
    recent_rows = ''.join(
        '<tr><td>' + datetime.fromtimestamp(
            r[0], timezone.utc).strftime('%Y-%m-%d %H:%M UTC') +
        '</td><td>' + html.escape(str(LABELS.get(r[1], r[1])), quote=True) +
        '</td><td>' + html.escape(str(r[2] or ''), quote=True) + '</td></tr>'
        for r in recent)
    return (checkout_health_html(daily)+'<section class="panel"><h2>Funnel</h2><p>All-time counts; '
            'ratios compare event counts with the previous step, not unique customer conversions. Repeat activity and independent journeys can produce ratios above 100%.</p><table><thead><tr>'
            '<th>Step</th><th>Count</th><th>Event count ratio</th></tr></thead><tbody>' +
            funnel_rows + '</tbody></table></section>'
            '<section class="panel"><h2>Recent commercial activity</h2><p>Counts in the displayed recent window; not distinct customers or verified revenue.</p><ul>' + recent_summary + '</ul></section>'
            '<section class="panel"><h2>Commercial diagnostic</h2><p>' + guidance +
            '</p><p>Based on recent aggregate events, not linked customer journeys. Missing telemetry may explain zero counts.</p></section>'
            '<section class="panel"><h2>Commercial verification checklist</h2><p>Suggested checks for stages with no recorded recent activity; not confirmed failures.</p><ul>' +
            (action_rows or '<li>Review verified revenue and customer feedback.</li>') + '</ul></section>'
            '<section class="panel"><h2>Totals</h2><table><thead><tr>'
            '<th>Event</th><th>All time</th></tr></thead><tbody>' +
            totals_rows + '</tbody></table></section>'
            '<section class="panel"><h2>Last 14 days</h2><table><thead><tr>'
            '<th>Day (UTC)</th>' + day_header + '</tr></thead><tbody>' +
            (day_rows or '<tr><td colspan="7">No events yet.</td></tr>') +
            '</tbody></table></section>'
            '<section class="panel"><h2>Recent events</h2><table><thead><tr>'
            '<th>When</th><th>Event</th><th>Detail</th></tr></thead><tbody>' +
            (recent_rows or '<tr><td colspan="3">No events yet.</td></tr>') +
            '</tbody></table><p>Counts include automated traffic (no bot '
            'filtering yet). No personal data is stored here — no IP '
            'addresses, no user agents, no emails.</p></section>'
            '<p><a href="/founder-economics">Revenue scenario console (V60)</a> · '
            '<a href="/">Back to dashboard</a></p>')


CAMPAIGN_CHANNELS = ('email', 'social', 'partner', 'search', 'referral', 'other')

def campaign_channel(path):
    """Only fixed channel labels are retained; never store arbitrary query values."""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query, keep_blank_values=True)
    values = query.get('utm_medium', [])
    if not values:
        return 'untagged'
    if len(values) != 1:
        return 'other'
    return values[0] if values[0] in CAMPAIGN_CHANNELS else 'other'


def acquisition_html(conn):
    since = int(time.time()) - 14 * 86400
    counts = dict(conn.execute(
        "SELECT detail, COUNT(*) FROM site_events WHERE event='landing_view' "
        "AND created>=? GROUP BY detail", (since,)).fetchall())
    rows = ''.join('<tr><th scope="row">' + channel + '</th><td>' +
                   str(counts.get(channel, 0)) + '</td></tr>'
                   for channel in CAMPAIGN_CHANNELS + ('untagged',))
    return ('<section class="panel"><h2>Acquisition channels — last 14 days</h2>'
            '<p>Tagged landing requests, not unique visitors or attributed sales. '
            'Includes automated traffic. Older unclassified requests are excluded.</p>'
            '<table><thead><tr><th>Channel</th><th>Landing requests</th></tr></thead><tbody>'
            + rows + '</tbody></table><h3>Campaign links</h3><p>Append '
            '<code>?utm_medium=email</code> to the public homepage for email campaigns. '
            'Other supported values: social, partner, search, referral, other. '
            'Never put customer identifiers in campaign URLs.</p></section>')
