"""The Automatic Revenue Engine: follow-up sequences that turn interest
into PRO, on their own.

The funnel leaks at conversion, not at the demo: hundreds of people try
the demo, a few sign up, nobody pays. Two groups show real interest and
then hear nothing:
- Demo leads: a visitor runs a demo and leaves an email. They get ONE
  report email, then silence. They never come back.
- Free-limit users: a user burns their free report, hits the paywall,
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
- Welcome (per user, once ever, at signup): day 0, day 1, day 3. The
  third leg the engine was missing: a new signup heard nothing after
  the account was created, so the seeded ledger Demo-to-Workspace
  leaves behind sat unused and the free report never got touched.
  Day 0 welcomes them (naming the seeded ledger when the signup came
  from an own-CSV demo), day 1 nudges the ledger, day 3 points at PRO.
- Weekly money report (per user, once per week): the proof piece for
  the growth agent — what the business made this week, what to push,
  who went quiet. Computed from their own ledger and reports only;
  never queued when there is no data to report, and never claims
  agent activity, because the agent does not exist yet.

All three sequences record a 'followup_queued' site event so the funnel on
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
    (0, 'You have used your free report — go PRO',
     'You have used your free report. PRO is $49 for 30 days, 50 '
     'reports, Bitcoin or card, and it unlocks the moment payment settles.\n\n'
     'Upgrade here: {site_url}/account\n\n— VELXTRIA'),
    (3, 'Still thinking about PRO?',
     'You hit your free-report limit a few days ago. PRO is $49 for 30 '
     'days, 50 reports, Bitcoin or card — and your reports are waiting.\n\n'
     'Upgrade here: {site_url}/account\n\n— VELXTRIA'),
)

# Welcome + activation (per user, once ever, at signup). Day 0 has two
# versions: one for a signup that arrived with a seeded ledger (an
# own-CSV demo claimed into the account), one for a plain register.
# {site_url} is filled in.
WELCOME_SEEDED_DAY0 = (
    0, 'Welcome to VELXTRIA — your workspace is ready',
    'Your demo report is saved to your free account, and your sales are '
    'already in your Sales Ledger — your dashboard opens on your real '
    'numbers. Log a sale as it happens, or turn your ledger into a full '
    'cleaned report.\n\n'
    'You have 1 free report.\n\n'
    'Open your dashboard: {site_url}/\n\n— VELXTRIA')
WELCOME_PLAIN_DAY0 = (
    0, 'Welcome to VELXTRIA — your free account is ready',
    'Your free account is ready. Upload a sales CSV to get a cleaned '
    'report with the problems flagged, or log sales as they happen in '
    'your Sales Ledger.\n\n'
    'You have 1 free report.\n\n'
    'Open your dashboard: {site_url}/\n\n— VELXTRIA')
WELCOME_STEPS = (
    (1, 'Your Sales Ledger is waiting',
     'Your Sales Ledger keeps your sales in one place. Log a sale as it '
     'happens and watch your monthly totals grow — or turn your ledger '
     'into a full cleaned report (uses your free report).\n\n'
     'Open your dashboard: {site_url}/\n\n— VELXTRIA'),
    (3, 'You have free reports waiting',
     'You have 1 free report. When you need more, PRO is $49 '
     'for 30 days, 50 reports, Bitcoin or card — and it unlocks the moment '
     'payment settles.\n\n'
     'See PRO on your account page: {site_url}/account\n\n— VELXTRIA'),
)


def queue_demo_sequence(conn, email, share_token, share_link, site_url,
                        now=None):
    """Queue the demo-lead follow-up sequence for one demo. Returns how
    many steps were newly queued (0 when this demo already has them)."""
    import notifications
    import email_unsubscribe
    import site_stats
    now = int(time.time()) if now is None else now
    queued = 0
    for days, subject, template in DEMO_STEPS:
        body = template.format(share_link=share_link, site_url=site_url)
        token = email_unsubscribe.get_or_create_token(conn, email)
        body = email_unsubscribe.append_footer(body, email, site_url, token)
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
    import email_unsubscribe
    import site_stats
    import subscriptions
    ent, _count, _remaining = subscriptions.usage(conn, user_id)
    if ent['plan'] == 'pro':
        return 0
    now = int(time.time()) if now is None else now
    queued = 0
    for days, subject, template in PRO_STEPS:
        body = template.format(site_url=site_url)
        token = email_unsubscribe.get_or_create_token(conn, email)
        body = email_unsubscribe.append_footer(body, email, site_url, token)
        if notifications.queue(
                conn, email, subject, body, 'pro_upsell',
                dedupe_key='pro-upsell:%d:%d' % (days, user_id),
                send_at=now + days * DAY):
            queued += 1
    if queued:
        site_stats.record(conn, 'followup_queued', 'pro:%d' % user_id)
    return queued


def queue_weekly_money_report(conn, user_id, email, site_url, now=None):
    """Queue this week's money report for one user, once per week.

    Returns 1 when newly queued, 0 when already queued this week or
    when the user has no ledger entries and no reports — an empty
    report is not emailed; the dashboard shows the empty state
    instead. The body is computed from the user's own ledger and
    reports at queue time, so the numbers are a snapshot of this week.
    """
    import money_report
    import winback
    import notifications
    import email_unsubscribe
    import site_stats
    now = int(time.time()) if now is None else now
    report = money_report.weekly_report(conn, user_id, now=now)
    if not report['has_data']:
        return 0
    draft_list = winback.drafts(conn, user_id, now=now)
    stats = winback.recovery(conn, user_id, now=now)
    body = money_report.report_email_body(
        report, site_url, winback_draft=draft_list[0] if draft_list else None,
        winback_stats=stats)
    token = email_unsubscribe.get_or_create_token(conn, email)
    body = email_unsubscribe.append_footer(body, email, site_url, token)
    if notifications.queue(
            conn, email, money_report.report_email_subject(report), body,
            'money_report',
            dedupe_key='money-report:%s:%d'
            % (report['week_start'], user_id),
            send_at=now):
        site_stats.record(conn, 'followup_queued',
                          'money-report:%d' % user_id)
        return 1
    return 0


def queue_welcome(conn, user_id, email, site_url, seeded=False, now=None):
    """Queue the welcome + activation sequence for a new signup, once
    ever. Day 0 welcomes them (naming the seeded ledger when the signup
    came from an own-CSV demo), day 1 nudges the ledger, day 3 points
    at PRO. Returns how many steps were newly queued (0 when already
    queued for this user)."""
    import notifications
    import email_unsubscribe
    import site_stats
    now = int(time.time()) if now is None else now
    steps = [WELCOME_SEEDED_DAY0 if seeded else WELCOME_PLAIN_DAY0]
    steps.extend(WELCOME_STEPS)
    queued = 0
    for days, subject, template in steps:
        body = template.format(site_url=site_url)
        token = email_unsubscribe.get_or_create_token(conn, email)
        body = email_unsubscribe.append_footer(body, email, site_url, token)
        if notifications.queue(
                conn, email, subject, body, 'welcome',
                dedupe_key='welcome:%d:%d:%s' % (days, user_id, email),
                send_at=now + days * DAY):
            queued += 1
    if queued:
        site_stats.record(conn, 'followup_queued', 'welcome:%d' % user_id)
    return queued
