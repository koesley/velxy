"""Win-back drafts: the growth agent's first real work.

For every customer who went quiet (no paid order in 90 days, see
money_report.quiet_customers), the agent writes the exact message the
owner can send them — personalised with their name, their last
service and when it was. Lifetime spending stays internal. The owner copies a
draft, adds their name, and sends it themselves: VELXTRIA holds no
customer email addresses, so nothing here sends anything to a
customer, and no draft ever promises a discount or invents urgency.

Sending is tracked, so the money report can show subsequent purchases:
mark_sent records that the owner sent a draft, and recovery counts
the customers who ordered again afterwards and the revenue that came
back. A send counts for the quiet spell it was sent in — if the
customer orders again and later goes quiet a second time, the old
send does not count as sent for the new spell.
"""
from datetime import date, datetime, timezone
import secrets
import time
from decimal import Decimal, DecimalException


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS winback_sends (
      id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
      customer TEXT NOT NULL, sent_at INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id))''')


def _short_date(iso_date):
    return datetime.strptime(iso_date, '%Y-%m-%d').strftime('%b %-d')


def sent_for_spell(conn, user_id, customer, last_date):
    """Latest sent_at (Unix) for this customer after their last order
    date, or None. A send counts for the current quiet spell only."""
    setup(conn)
    row = conn.execute(
        'SELECT MAX(sent_at) FROM winback_sends'
        ' WHERE user_id=? AND customer=?',
        (user_id, customer)).fetchone()
    if not row or not row[0]:
        return None
    sent_day = datetime.fromtimestamp(
        row[0], timezone.utc).date().isoformat()
    return row[0] if sent_day > last_date else None


def mark_sent(conn, user_id, customer, now=None):
    """Record that the owner sent the win-back draft to this customer.

    Only valid for a customer who is currently quiet; raises
    ValueError otherwise, so arbitrary names can't be marked.
    Idempotent within a spell: marking the same customer twice
    returns the first send's id instead of recording a second send.
    """
    import money_report
    setup(conn)
    name = ' '.join((customer or '').split()).title()
    quiet = {q['customer']: q
             for q in money_report.quiet_customers(conn, user_id, now=now)}
    if name not in quiet:
        raise ValueError('that customer is not waiting for a win-back')
    existing = sent_for_spell(
        conn, user_id, name, quiet[name]['last_date'])
    if existing:
        row = conn.execute(
            'SELECT id FROM winback_sends WHERE user_id=? AND customer=?'
            ' AND sent_at=?', (user_id, name, existing)).fetchone()
        return row[0]
    now = int(time.time()) if now is None else now
    ident = secrets.token_hex(8)
    conn.execute(
        'INSERT INTO winback_sends (id,user_id,customer,sent_at)'
        ' VALUES (?,?,?,?)', (ident, user_id, name, now))
    return ident


def recovery(conn, user_id, now=None):
    """Win-back results as (sent, recovered, recovered_revenue).

    sent is the number of customers the owner has sent a win-back to;
    recovered is how many of them placed a paid order dated after the
    send; recovered_revenue is the paid revenue from those later
    orders through the observation date. This is temporal association,
    not proof that outreach caused a purchase.
    """
    setup(conn)
    observed_at = int(time.time()) if now is None else int(now)
    sends = conn.execute(
        'SELECT customer,MAX(sent_at) FROM winback_sends'
        ' WHERE user_id=? AND sent_at<=? GROUP BY customer', (user_id, observed_at)).fetchall()
    if not sends:
        return (0, 0, Decimal('0'))
    today = datetime.fromtimestamp(observed_at, timezone.utc).date().isoformat()
    sent_day = {
        customer: datetime.fromtimestamp(
            sent_at, timezone.utc).date().isoformat()
        for customer, sent_at in sends if sent_at <= observed_at}
    rows = conn.execute(
        'SELECT order_date,customer,quantity,unit_price'
        ' FROM ledger_entries WHERE user_id=? AND status=?',
        (user_id, 'Paid')).fetchall()
    back = {}
    for order_date, customer, quantity, unit_price in rows:
        day = str(order_date)[:10]
        try:
            day = date.fromisoformat(day).isoformat()
            if customer not in sent_day or not sent_day[customer] < day <= today:
                continue
            amount = Decimal(str(quantity)) * Decimal(str(unit_price))
            if not amount.is_finite() or amount <= 0:
                continue
            back[customer] = back.get(customer, Decimal('0')) + amount
        except (ValueError, TypeError, DecimalException):
            continue
    return (len(sent_day), len(back),
            sum(back.values(), Decimal('0')))


def drafts(conn, user_id, now=None):
    """Ready-to-send win-back drafts, richest quiet customer first.

    Each draft is a dict with customer, days_quiet, lifetime
    (Decimal), last_date, last_product, text, and sent_at (the Unix
    time the owner marked this spell's draft sent, or None).
    """
    import money_report
    setup(conn)
    out = []
    for q in money_report.quiet_customers(conn, user_id, now=now):
        text = (
            "Hi %s — it's been a while since your last %s on %s. "
            "We'd love to welcome you back. Would you be interested in "
            "another visit?" % (q['customer'], q['last_product'],
                       _short_date(q['last_date'])))
        out.append({**q, 'text': text,
                    'sent_at': sent_for_spell(
                        conn, user_id, q['customer'], q['last_date'])})
    return out
