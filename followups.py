"""The Automatic Revenue Engine: follow-up sequences that turn interest
into PRO, on their own.

The funnel leaks at conversion, not at the demo: hundreds of people try
the demo, a few sign up, nobody pays. Two groups show real interest and
then hear nothing:
- Demo leads: a visitor runs a demo and leaves an email. They get ONE
  report email, then silence. They never come back.
- Free-limit users: a user burns all 3 free reports, hits the paywall,
  and gets NO follow-up email. They never upgrade.

This module queues scheduled follow-up sequences for both groups. Each
step is a row in email_outbox with a future next_attempt, so the existing
delivery worker sends it when it comes due — nothing here sends mail
directly, and nothing needs a manual step. Every step has its own
dedupe_key, so a sequence is queued at most once per demo (or per user),
and the worker's retry/backoff still applies if a send fails.

Sequences:
- Demo lead (per demo, keyed by email + share token): day 1, day 3,
  day 7. Each reminds the runner of their report, links the share page
  and the free signup, and points at the unlock.
- PRO upsell (per user, once ever): day 0 (the moment they hit the
  paywall) and day 3. Each points at the account page, where the BTCPay
  checkout lives. Only queued for non-PRO users.

Both sequences record a 'followup_queued' site event so the funnel on
/founder-stats shows the engine working.
"""
import time

DAY = 86400

# (delay in days, subject, body template). {share_link} and {site_url}
# are filled in for demo follow-ups; {site_url} for PRO upsells.
DEMO_STEPS = (
    (1, 'Your VELXTRIA report is waiting',
     'You ran a demo on VELXTRIA and we emailed you the report. The full '
     'list of what is wrong with your data and the cleaned file unlock '
     'with a free account — no card, no purchase.\n\n'
     'View your report: {share_link}\n'
     'Save it to a free account: {site_url}/register\n\n— VELXTRIA'),
    (3, 'Your demo results are still waiting',
     'Your VELXTRIA demo report is still waiting. The share link works '
     'for 30 days, and a free account keeps the full list of what is '
     'wrong with your data forever.\n\n'
     'View your report: {share_link}\n'
     'Save it to a free account: {site_url}/register\n\n— VELXTRIA'),
    (7, 'Last chance to keep your VELXTRIA report',
     'This is the last nudge about your VELXTRIA demo report. If you '
     'want the full list of what is wrong with your data and the cleaned '
     'file, save it to a free account — it takes one email and password, '
     'no card.\n\n'
     'View your report: {share_link}\n'
     'Save it to a free account: {site_url}/register\n\n— VELXTRIA'),
)

PRO_STEPS = (
    (0, 'You have used your 3 free reports — go PRO',
     'You have used all 3 free reports. PRO is $49 for 30 days, 50 '
     'reports, Bitcoin only, and it unlocks the moment payment settles.\n\n'
     'Upgrade here: {site_url}/account\n\n— VELXTRIA'),
    (3, 'Still thinking about PRO?',
     'You hit your free-report limit a few days ago. PRO is $49 for 30 '
     'days, 50 reports, Bitcoin only — and your reports are waiting.\n\n'
     'Upgrade here: {site_url}/account\n\n— VELXTRIA'),
)


def queue_demo_sequence(conn, email, share_token, share_link, site_url,
                        now=None):
    """Queue the demo-lead follow-up sequence for one demo. Returns how
    many steps were newly queued (0 when this demo already has them)."""
    import notifications
    import site_stats
    now = int(time.time()) if now is None else now
    queued = 0
    for days, subject, template in DEMO_STEPS:
        body = template.format(share_link=share_link, site_url=site_url)
        if notifications.queue(
                conn, email, subject, body, 'demo_followup',
                dedupe_key='demo-followup:%d:%s:%s' % (days, email, share_token),
                send_at=now + days * DAY):
            queued += 1
    if queued:
        site_stats.record(conn, 'followup_queued',
                          'demo:%s' % share_token)
    return queued


def queue_pro_upsell(conn, user_id, email, site_url, now=None):
    """Queue the PRO upsell sequence for a free-limit user, once ever.
    Returns how many steps were newly queued (0 when already queued, or
    when the user is already PRO)."""
    import notifications
    import site_stats
    import subscriptions
    ent, _count, _remaining = subscriptions.usage(conn, user_id)
    if ent['plan'] == 'pro':
        return 0
    now = int(time.time()) if now is None else now
    queued = 0
    for days, subject, template in PRO_STEPS:
        body = template.format(site_url=site_url)
        if notifications.queue(
                conn, email, subject, body, 'pro_upsell',
                dedupe_key='pro-upsell:%d:%d' % (days, user_id),
                send_at=now + days * DAY):
            queued += 1
    if queued:
        site_stats.record(conn, 'followup_queued', 'pro:%d' % user_id)
    return queued
