"""Weekly money report: what a business made, what to push, who went quiet.

Computed only from the business's own data — their Sales Ledger and
their reports. Nothing is invented: every number comes from a ledger
entry or a report row, and a section with no data is left out instead
of guessed at. This is the proof piece for the autonomous growth
agent: the report shows the money first, and the agent's work
(follow-ups, win-backs) is measured against it. The agent does not
exist yet, so this report never claims agent activity — only the
business's own sales.

Weeks run Monday to Sunday (UTC). "This week" is the current week so
far; "last week" is the seven days before it. A customer is quiet
after 90 days without a paid order.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import time

QUIET_DAYS = 90
WINBACK_MIN = Decimal('100')
TOP_PRODUCTS = 3
TOP_QUIET = 5


def _monday(today):
    return today - timedelta(days=today.weekday())


def week_bounds(now=None):
    """(this_monday, last_monday, today) as dates for a Unix timestamp."""
    today = datetime.fromtimestamp(
        int(now) if now is not None else int(time.time()),
        timezone.utc).date()
    monday = _monday(today)
    return monday, monday - timedelta(days=7), today


def fmt_money(amount):
    return '$%s' % f'{Decimal(amount):,.2f}'


def _week_label(monday):
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return '%s %d–%d, %d' % (
            monday.strftime('%b'), monday.day, sunday.day, monday.year)
    return '%s %d – %s %d, %d' % (
        monday.strftime('%b'), monday.day,
        sunday.strftime('%b'), sunday.day, monday.year)


def quiet_customers(conn, user_id, now=None):
    """Customers with no paid order in QUIET_DAYS, richest first.

    Returns dicts with customer, days_quiet, lifetime (Decimal),
    last_date (ISO) and last_product (the product of their most recent
    paid order). The win-back drafts and the money report both read
    from here, so the quiet rule lives in exactly one place.
    """
    _monday, _last_monday, today = week_bounds(now)
    quiet_before = (today - timedelta(days=QUIET_DAYS)).isoformat()
    rows = conn.execute(
        'SELECT order_date,customer,product,quantity,unit_price'
        ' FROM ledger_entries WHERE user_id=? AND status=?'
        ' ORDER BY order_date ASC',
        (user_id, 'Paid')).fetchall()
    by_customer = {}
    for order_date, customer, product, quantity, unit_price in rows:
        day = str(order_date)[:10]
        amount = Decimal(str(quantity)) * Decimal(str(unit_price))
        cust = by_customer.setdefault(
            customer, {'lifetime': Decimal('0'), 'last': '',
                       'last_product': ''})
        cust['lifetime'] += amount
        if day >= cust['last']:
            cust['last'] = day
            cust['last_product'] = product
    found = []
    for customer, v in by_customer.items():
        if v['last'] and v['last'] < quiet_before:
            found.append({
                'customer': customer,
                'days_quiet': (today - datetime.strptime(
                    v['last'], '%Y-%m-%d').date()).days,
                'lifetime': v['lifetime'],
                'last_date': v['last'],
                'last_product': v['last_product']})
    found.sort(key=lambda item: (-item['lifetime'], item['customer']))
    return found[:TOP_QUIET]


def weekly_report(conn, user_id, now=None):
    """The business's money report for the current week.

    Returns a dict with only real numbers: revenue and orders this
    week vs last week, top products this week, quiet customers with
    lifetime value, the latest report's accepted/flagged counts, one
    top move derived from the numbers, and has_data (False when the
    business has no ledger entries at all — a report alone, such as
    one claimed from the sample demo, is not sales and does not make
    a money report).
    """
    monday, last_monday, today = week_bounds(now)
    monday_s = monday.isoformat()
    last_monday_s = last_monday.isoformat()
    rows = conn.execute(
        'SELECT order_date,customer,product,quantity,unit_price'
        ' FROM ledger_entries WHERE user_id=? AND status=?',
        (user_id, 'Paid')).fetchall()
    total_rows = conn.execute(
        'SELECT COUNT(*) FROM ledger_entries WHERE user_id=?',
        (user_id,)).fetchone()[0]
    latest = conn.execute(
        'SELECT accepted,rejected FROM reports WHERE user_id=?'
        ' ORDER BY created DESC LIMIT 1', (user_id,)).fetchone()
    revenue_this = Decimal('0')
    orders_this = 0
    revenue_last = Decimal('0')
    orders_last = 0
    by_product = {}
    for order_date, customer, product, quantity, unit_price in rows:
        day = str(order_date)[:10]
        amount = Decimal(str(quantity)) * Decimal(str(unit_price))
        if day >= monday_s:
            revenue_this += amount
            orders_this += 1
            prod = by_product.setdefault(
                product, {'orders': 0, 'revenue': Decimal('0')})
            prod['orders'] += 1
            prod['revenue'] += amount
        elif day >= last_monday_s:
            revenue_last += amount
            orders_last += 1
    top_products = sorted(
        ((p, v['orders'], v['revenue']) for p, v in by_product.items()),
        key=lambda item: (-item[2], item[0]))[:TOP_PRODUCTS]
    quiet = [(q['customer'], q['days_quiet'], q['lifetime'], q['last_date'])
             for q in quiet_customers(conn, user_id, now=now)]
    if quiet and quiet[0][2] >= WINBACK_MIN:
        name, days, lifetime, _last = quiet[0]
        top_move = ('Win back %s — no order in %d days, worth %s all time.'
                    % (name, days, fmt_money(lifetime)))
    elif top_products:
        product, _orders, revenue = top_products[0]
        top_move = ('Push %s — it made %s in paid sales this week.'
                    % (product, fmt_money(revenue)))
    elif revenue_this > 0:
        top_move = ('You made %s this week across %d paid orders.'
                    % (fmt_money(revenue_this), orders_this))
    else:
        top_move = ('Nothing in your ledger yet — log a sale and this '
                    'report will show what you made, what to push, and '
                    'who went quiet.')
    return {
        'week_label': _week_label(monday),
        'week_start': monday_s,
        'revenue_this_week': revenue_this,
        'orders_this_week': orders_this,
        'revenue_last_week': revenue_last,
        'orders_last_week': orders_last,
        'top_products': top_products,
        'quiet_customers': quiet,
        'latest_report': (
            (latest[0], latest[1]) if latest else None),
        'top_move': top_move,
        'has_data': bool(total_rows),
    }


def report_email_subject(report):
    """Subject line: the week's revenue when there is any."""
    if report['revenue_this_week'] > 0:
        return ('Your money report: %s this week'
                % fmt_money(report['revenue_this_week']))
    return 'Your VELXTRIA money report'


def report_email_body(report, site_url, winback_draft=None,
                      winback_stats=None):
    """Plain-text body. Every line is a number from the report dict.
    winback_draft, when given, is one draft dict from winback.drafts
    — the top one — included so the owner can act on the report
    straight from their inbox. winback_stats, when given, is
    winback.recovery's (sent, recovered, revenue) tuple, shown only
    once a win-back has actually been sent."""
    lines = ['Your money report — %s' % report['week_label'], '',
             'TOP MOVE', report['top_move'], '',
             'THIS WEEK',
             'Paid revenue: %s (%d orders)'
             % (fmt_money(report['revenue_this_week']),
                report['orders_this_week']),
             'Last week: %s (%d orders)'
             % (fmt_money(report['revenue_last_week']),
                report['orders_last_week'])]
    if report['top_products']:
        lines += ['', 'TOP PRODUCTS THIS WEEK']
        for product, orders, revenue in report['top_products']:
            lines.append('- %s: %s (%d order%s)'
                         % (product, fmt_money(revenue), orders,
                            's' if orders != 1 else ''))
    if report['quiet_customers']:
        lines += ['', 'CUSTOMERS GONE QUIET (90+ days)']
        for name, days, lifetime, last in report['quiet_customers']:
            lines.append('- %s: last order %s (%d days ago), worth %s '
                         'all time' % (name, last, days, fmt_money(lifetime)))
    if report['latest_report']:
        accepted, rejected = report['latest_report']
        lines += ['', 'YOUR DATA',
                  'Latest report: %d accepted, %d flagged.'
                  % (accepted, rejected)]
    if winback_draft:
        lines += ['', 'WIN-BACK DRAFT — send this to %s:'
                  % winback_draft['customer'],
                  winback_draft['text']]
    if winback_stats and winback_stats[0]:
        sent, recovered, revenue = winback_stats
        lines += ['', 'WIN-BACK RESULTS',
                  'Sent: %d · Customers back: %d · Recovered: %s'
                  % (sent, recovered, fmt_money(revenue))]
    lines += ['', 'See the full report on your dashboard: %s/'
              % site_url.rstrip('/'),
              '', '— VELXTRIA']
    return '\n'.join(lines)
