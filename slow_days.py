"""Slow-day filler: spot the business's slowest weekday and fill it.

From the business's own ledger only: which weekday had the fewest
paid orders in the last 28 days, when it next comes around, and which
recent customers to nudge into it — with the exact message to send
each one. The audience is the opposite of win-back: customers who
ordered recently (7–30 days ago), not ones who went quiet.

Nothing is invented: with fewer than 10 paid orders in the window
there is no pattern to call, so no filler is shown at all. The owner
copies a draft and sends it themselves — VELXTRIA holds no customer
email addresses.
"""
from datetime import datetime, timedelta, timezone
from collections import Counter
import time

WINDOW_DAYS = 28
MIN_ORDERS = 10
NUDGE_RECENT_DAYS = 30
NUDGE_MIN_DAYS = 7
TOP_CANDIDATES = 3

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
            'Saturday', 'Sunday']


def _short_date(iso_date):
    return datetime.strptime(iso_date, '%Y-%m-%d').strftime('%a %b %-d')


def _paid_rows(conn, user_id):
    return conn.execute(
        'SELECT order_date,customer,product,quantity,unit_price'
        ' FROM ledger_entries WHERE user_id=? AND status=?'
        ' ORDER BY order_date ASC',
        (user_id, 'Paid')).fetchall()


def filler(conn, user_id, now=None):
    """The slow-day filler, or None when there is no pattern to call.

    Returns a dict with weekday (name), next_date (ISO), next_label
    ('today' or 'Thu Nov 26'), orders (paid orders on that weekday in
    the window), and candidates — up to three recent customers with a
    ready-to-send draft each.
    """
    today = datetime.fromtimestamp(
        int(now) if now is not None else int(time.time()),
        timezone.utc).date()
    window_start = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    rows = _paid_rows(conn, user_id)
    recent = [(str(r[0])[:10], r[1], r[2])
              for r in rows if str(r[0])[:10] >= window_start]
    if len(recent) < MIN_ORDERS:
        return None
    counts = Counter(
        datetime.strptime(day, '%Y-%m-%d').weekday() for day, _, _ in recent)
    slowest = min(range(7), key=lambda w: (counts.get(w, 0), w))
    days_ahead = (slowest - today.weekday()) % 7
    next_day = today + timedelta(days=days_ahead)
    next_label = ('today' if days_ahead == 0
                  else _short_date(next_day.isoformat()))
    # Recent customers to nudge: last order 7–30 days ago, most recent
    # first. Win-back owns the quiet ones; this owns the recent ones.
    # Any last order in the band is inside the window, so `recent`
    # (window rows only) is enough here.
    last_order = {}
    for day, customer, product in recent:
        entry = last_order.setdefault(
            customer, {'last': '', 'product': ''})
        if day >= entry['last']:
            entry['last'] = day
            entry['product'] = product
    nudge_before = (today - timedelta(days=NUDGE_MIN_DAYS)).isoformat()
    nudge_after = (today - timedelta(days=NUDGE_RECENT_DAYS)).isoformat()
    in_band = [(c, v['last'], v['product']) for c, v in last_order.items()
               if nudge_after <= v['last'] <= nudge_before]
    # Most recent first; name ascending breaks ties (stable sort).
    in_band.sort(key=lambda item: item[0])
    in_band.sort(key=lambda item: item[1], reverse=True)
    candidates = in_band[:TOP_CANDIDATES]
    if not candidates:
        return None
    out = []
    for customer, last_date, product in candidates:
        text = (
            "Hi %s — we have an open slot %s. Your last %s was %s — "
            "want me to book you in again?" % (
                customer, next_label, product, _short_date(last_date)))
        out.append({'customer': customer, 'last_date': last_date,
                    'last_product': product, 'text': text})
    return {'weekday': WEEKDAYS[slowest],
            'next_date': next_day.isoformat(),
            'next_label': next_label,
            'orders': counts.get(slowest, 0),
            'candidates': out}
