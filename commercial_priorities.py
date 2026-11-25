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
    if not findings:
        findings.append(('Verification', 'Revenue evidence', None,
                         'Reconcile actual settlements, refunds and customer feedback.'))
    return findings

def commercial_priority_html(daily):
    rows = ''.join('<tr><td>' + escape(status) + '</td><td>' + escape(title)
                   + '</td><td>' + ('—' if count is None else str(count))
                   + '</td><td>' + escape(action) + '</td></tr>'
                   for status, title, count, action in commercial_priorities(daily))
    return ('<section class="panel"><h2>Commercial action queue</h2>'
            '<p>Payment error events take priority over missing telemetry. '
            'Zero events do not establish a failure. Counts are not unique buyers, '
            'attributed sales or verified revenue. No actions are executed automatically.</p>'
            '<table><thead><tr><th>Evidence</th><th>Area</th><th>Events</th>'
            '<th>Next verification</th></tr></thead><tbody>' + rows + '</tbody></table></section>')
