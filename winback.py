"""Win-back drafts: the growth agent's first real work.

For every customer who went quiet (no paid order in 90 days, see
money_report.quiet_customers), the agent writes the exact message the
owner can send them — personalised with their name, their last
service, when it was, and what they are worth. The owner copies a
draft, adds their name, and sends it themselves: VELXTRIA holds no
customer email addresses, so nothing here sends anything to a
customer, and no draft ever promises a discount or invents urgency.
"""
from datetime import datetime


def _short_date(iso_date):
    return datetime.strptime(iso_date, '%Y-%m-%d').strftime('%b %-d')


def drafts(conn, user_id, now=None):
    """Ready-to-send win-back drafts, richest quiet customer first.

    Each draft is a dict with customer, days_quiet, lifetime
    (Decimal), last_date, last_product and text.
    """
    import money_report
    out = []
    for q in money_report.quiet_customers(conn, user_id, now=now):
        text = (
            "Hi %s — it's been a while since your last %s on %s. "
            "You've trusted us with %s so far, and I'd love to get you "
            "back on the schedule. Want me to book your next %s this "
            "week?" % (q['customer'], q['last_product'],
                       _short_date(q['last_date']),
                       money_report.fmt_money(q['lifetime']),
                       q['last_product']))
        out.append({**q, 'text': text})
    return out
