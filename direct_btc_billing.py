"""Direct BTC fixed-price quotes and atomic confirmed-payment activation.

Not wired to a public checkout. Only invoke settle_verified_output after
independently verifying the blockchain output against the persisted quote.
"""
import json
import time
import urllib.request
from decimal import Decimal, ROUND_CEILING, InvalidOperation

import subscriptions

PRICE_USD = Decimal("49.00")
QUOTE_SECONDS = 900
MIN_SATS = 1000


def btc_usd_rate():
    request = urllib.request.Request("https://api.coinbase.com/v2/prices/BTC-USD/spot",
                                     headers={"Accept": "application/json",
                                              "User-Agent": "VELXTRIA/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    rate = Decimal(str(payload["data"]["amount"]))
    if not rate.is_finite() or rate <= 0:
        raise ValueError("Invalid BTC/USD rate")
    return rate


def sats_for_usd(rate, usd=PRICE_USD):
    rate = Decimal(str(rate))
    if not rate.is_finite() or rate <= 0:
        raise ValueError("Invalid exchange rate")
    if usd != PRICE_USD:
        raise ValueError("Unsupported plan price")
    sats = int((usd * Decimal(100_000_000) / rate).to_integral_value(rounding=ROUND_CEILING))
    if sats < MIN_SATS:
        raise ValueError("BTC amount below checkout minimum")
    return sats


def setup(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_btc_quotes (
        order_id TEXT PRIMARY KEY,
        usd_cents INTEGER NOT NULL CHECK(usd_cents = 4900),
        btc_usd TEXT NOT NULL,
        expected_sats INTEGER NOT NULL CHECK(expected_sats >= 1000),
        issued_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES direct_btc_orders(order_id)
    )""")


def quote_order(conn, order_id, user_id, *, rate=None, now=None):
    """Persist one immutable quote; caller commits transaction before displaying it."""
    if rate is None:
        rate = btc_usd_rate()
    amount = sats_for_usd(rate)
    now = int(time.time()) if now is None else now
    setup(conn)
    order = conn.execute("SELECT user_id,status,address FROM direct_btc_orders WHERE order_id=?",
                         (order_id,)).fetchone()
    if not order or order[0] != user_id or order[1] != "awaiting_quote":
        raise ValueError("Order unavailable for quoting")
    conn.execute("""INSERT INTO direct_btc_quotes
        (order_id,usd_cents,btc_usd,expected_sats,issued_at,expires_at)
        VALUES (?,?,?,?,?,?)""",
        (order_id, 4900, str(rate), amount, now, now + QUOTE_SECONDS))
    changed = conn.execute("""UPDATE direct_btc_orders SET status='pending'
        WHERE order_id=? AND user_id=? AND status='awaiting_quote'""",
        (order_id, user_id))
    if changed.rowcount != 1:
        raise RuntimeError("Quote order state changed")
    return {"order_id": order_id, "address": order[2],
            "expected_sats": amount, "expires_at": now + QUOTE_SECONDS}


def settle_verified_output(conn, order_id, user_id, txid, vout, *,
                           amount_sats, confirmed_block_time, verified_at=None):
    """Atomically grant 30 days after independently confirmed on-chain proof.

    Requires caller-owned transaction and database-level write serialization.
    Transaction/output/address/confirmation verification MUST be done externally.
    Block timestamp must fall within quote validity; do not use the verification
    time to decide whether a payment was sent before expiry.
    """
    import direct_btc_orders
    now = int(time.time()) if verified_at is None else verified_at
    row = conn.execute("""SELECT o.status,q.expected_sats,q.issued_at,q.expires_at
        FROM direct_btc_orders o JOIN direct_btc_quotes q ON q.order_id=o.order_id
        WHERE o.order_id=? AND o.user_id=?""", (order_id, user_id)).fetchone()
    if (not row or row[0] != "pending" or type(amount_sats) is not int
            or amount_sats < row[1] or type(confirmed_block_time) is not int
            or not row[2] <= confirmed_block_time <= row[3]):
        return False
    if not direct_btc_orders.claim_output(conn, order_id, txid, vout, now=now):
        return False
    changed = conn.execute("""UPDATE direct_btc_orders SET status='settled'
        WHERE order_id=? AND user_id=? AND status='pending'""", (order_id, user_id))
    if changed.rowcount != 1:
        raise RuntimeError("Concurrent settlement detected; rollback required")
    previous = conn.execute("SELECT period_end FROM subscriptions WHERE user_id=?",
                            (user_id,)).fetchone()
    start = max(now, previous[0] if previous and previous[0] > now else now)
    subscriptions.setup(conn)
    conn.execute("""INSERT INTO subscriptions
        (user_id,product_key,pricing_plan,status,source_reference,period_start,
         period_end,verified_at,verification_source,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
          product_key=excluded.product_key,pricing_plan=excluded.pricing_plan,
          status=excluded.status,source_reference=excluded.source_reference,
          period_start=excluded.period_start,period_end=excluded.period_end,
          verified_at=excluded.verified_at,verification_source=excluded.verification_source,
          updated_at=excluded.updated_at""",
        (user_id, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN, "active",
         order_id, start, start + 30*86400, now, "direct_btc_confirmed", now))
    return True
