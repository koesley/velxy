"""Evidence-based commercial triage; aggregate events are not customer cohorts."""
from html import escape

RULES = (
    ('checkout_unavailable', 'Payment availability', 'Verify enabled payment methods using a sandbox checkout.'),
    ('checkout_failed', 'Payment reliability', 'Inspect provider errors and retry only in a test environment.'),
)
STAGES = (
    ('landing_view', 'Acquisition', 'Verify public access and test one tagged campaign.'),
    ('demo_run', 'Product discovery', 'Run the public demo and inspect its first call to action.'),
    ('signup', 'Registration', 'Test account creation and the demo-to-signup path.'),
    ('report_generated', 'Activation', 'Test first-report generation with an authorized account.'),
    ('checkout_started', 'Purchase intent', 'Test the paid offer and checkout entry point.'),
    ('pro_activated', 'Settlement and access', 'Reconcile provider settlements against granted access.'),
)

def commercial_priorities(daily):
    keys = [r[0] for r in RULES + STAGES]
    counts = {key: sum(row.get(key, 0) for _, row in daily) for key in keys}
    findings = []
    for key, title, action in RULES:
        if counts[key] > 0:
            findings.append(('Observed event', title, counts[key], action))
    for key, title, action in STAGES:
        if counts[key] == 0:
            findings.append(('Evidence gap', title, 0, action))
    if counts['checkout_started'] and not counts['pro_activated']:
        findings.insert(sum(1 for key, _, _ in RULES if counts[key] > 0),
                        ('Verification', 'Checkout follow-through', counts['checkout_started'],
                         'Inspect pending and expired orders; verify settlement and access independently.'))
    if not findings:
        findings.append(('Verification', 'Revenue evidence', None,
                         'Reconcile actual settlements, refunds and customer feedback.'))
    return findings

def commercial_activity_snapshot(daily):
    """Compare observed daily activity without implying cohort conversion."""
    rows = sorted(daily, key=lambda row: row[0])
    if not rows:
        return 'No recent telemetry available.'
    days = {day for day, _ in rows}
    starts = sum(row.get('checkout_started', 0) for _, row in rows)
    activations = sum(row.get('pro_activated', 0) for _, row in rows)
    return (f'{len(days)} UTC dates with recorded activity; {starts} checkout starts; '
            f'{activations} PRO activation events. Not a settlement ledger.')

def commercial_priority_html(daily):
    daily = list(daily)
    rows = ''.join('<tr><td>' + escape(status) + '</td><td>' + escape(title)
                   + '</td><td>' + ('—' if count is None else str(count))
                   + '</td><td>' + escape(action) + '</td></tr>'
                   for status, title, count, action in commercial_priorities(daily))
    return ('<section class="panel"><h2>Commercial action queue</h2>'
            '<p>Payment error events take priority over missing telemetry. '
            'Zero events do not establish a failure. Counts are not unique buyers, '
            'attributed sales or verified revenue. No actions are executed automatically.</p>'
            '<p>' + escape(commercial_activity_snapshot(daily)) + '</p>'
            '<table><thead><tr><th>Evidence</th><th>Area</th><th>Events</th>'
            '<th>Next verification</th></tr></thead><tbody>' + rows + '</tbody></table></section>')
