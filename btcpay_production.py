"""Production BTCPay Greenfield client (configuration and verified invoice reads).

This module never accepts browser-submitted settlement claims and never
handles wallet seeds or private keys. The testnet adapter remains separate.
"""
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

PRICE_USD = Decimal("49.00")


def configured():
    try:
        endpoint()
    except ValueError:
        return False
    return bool(os.getenv("VELXTRIA_BTCPAY_PROD_API_KEY", "").strip()
                and os.getenv("VELXTRIA_BTCPAY_PROD_STORE_ID", "").strip())


def endpoint():
    raw = os.getenv("VELXTRIA_BTCPAY_PROD_URL", "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Production BTCPay requires a dedicated HTTPS origin")
    if parsed.hostname == "testnet.demo.btcpayserver.org":
        raise ValueError("Testnet cannot be used as a production BTCPay origin")
    if parsed.hostname.lower() in ("localhost",) or parsed.hostname.endswith(".local"):
        raise ValueError("Localhost is not a production BTCPay origin")
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        if not ip.is_global:
            raise ValueError("Non-public IP is not a production BTCPay origin")
    if parsed.port not in (None, 443):
        raise ValueError("Production BTCPay must use HTTPS default port")
    return raw


def api_request(method, path, payload=None):
    if not configured():
        raise RuntimeError("Production BTCPay is not configured")
    if method not in ("GET", "POST") or not path.startswith("/") or "//" in path:
        raise ValueError("Invalid BTCPay API request")
    base = endpoint() + "/api/v1/stores/" + urllib.parse.quote(os.environ["VELXTRIA_BTCPAY_PROD_STORE_ID"], safe="")
    headers = {"Authorization": "token " + os.environ["VELXTRIA_BTCPAY_PROD_API_KEY"],
               "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        raise RuntimeError("Production BTCPay request failed") from exc


def verified_settlement(invoice_id, order_id):
    """Verify settlement against the authenticated BTCPay server.

    This is a read-only verifier; caller must also enforce persisted order
    ownership, one-time claim, and atomic entitlement updates.
    """
    if not invoice_id or not order_id:
        return False
    info = api_request("GET", "/invoices/" + urllib.parse.quote(invoice_id, safe=""))
    if not isinstance(info, dict) or info.get("id") != invoice_id:
        return False
    meta = info.get("metadata")
    if not isinstance(meta, dict) or meta.get("orderId") != order_id:
        return False
    try:
        amount = Decimal(str(info.get("amount")))
    except (InvalidOperation, TypeError):
        return False
    return (info.get("status") == "Settled" and amount == PRICE_USD
            and info.get("currency") == "USD")


def issue_invoice(order_id):
    """Create a production invoice, returning a validated hosted checkout URL.

    Only call for a previously committed, user-owned order.
    """
    if not order_id or not order_id.startswith("vx-prod-"):
        raise ValueError("Invalid production order identifier")
    result = api_request("POST", "/invoices", {
        "amount": str(PRICE_USD), "currency": "USD",
        "metadata": {"orderId": order_id, "itemDesc": "VELXTRIA PRO - 30 days"},
        "checkout": {"speedPolicy": "HighSpeed"}
    })
    if not isinstance(result, dict):
        raise RuntimeError("Invalid BTCPay invoice response")
    invoice_id, checkout_url = result.get("id"), result.get("checkoutLink")
    if not isinstance(invoice_id, str) or not invoice_id or not isinstance(checkout_url, str):
        raise RuntimeError("Invalid BTCPay invoice response")
    parsed = urllib.parse.urlsplit(checkout_url)
    origin = urllib.parse.urlsplit(endpoint())
    if (parsed.scheme != "https" or parsed.netloc != origin.netloc
            or not parsed.path.startswith("/i/") or not parsed.path[3:]
            or parsed.username or parsed.password or parsed.fragment):
        raise RuntimeError("Untrusted BTCPay checkout URL")
    return invoice_id, checkout_url


def create_order(conn, user_id):
    """Persist a production order before issuing any invoice."""
    import secrets
    import time
    order_id = "vx-prod-" + secrets.token_hex(16)
    conn.execute("INSERT INTO btcpay_orders(order_id,user_id,created_at) VALUES (?,?,?)",
                 (order_id, user_id, int(time.time())))
    return order_id


def attach_invoice(conn, user_id, order_id, invoice_id, checkout_url):
    """Attach invoice only to the creating account's unclaimed order."""
    result = conn.execute(
        "UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,status='pending' "
        "WHERE order_id=? AND user_id=? AND status='creating' AND invoice_id IS NULL",
        (invoice_id, checkout_url, order_id, user_id))
    return (result.cursor.rowcount if hasattr(result, "cursor") else result.rowcount) == 1


def reconcile(conn, user_id):
    """Atomically grant a 30-day period for each independently settled invoice."""
    import time
    import subscriptions
    orders = conn.execute(
        "SELECT order_id,invoice_id FROM btcpay_orders WHERE user_id=? AND "
        "status='pending' AND order_id LIKE 'vx-prod-%' AND invoice_id IS NOT NULL "
        "ORDER BY created_at DESC LIMIT 30", (user_id,)).fetchall()
    activated = False
    for order_id, invoice_id in orders:
        if not verified_settlement(invoice_id, order_id):
            continue
        now = int(time.time())
        claimed = conn.execute(
            "UPDATE btcpay_orders SET status='settled',settled_at=? "
            "WHERE order_id=? AND user_id=? AND invoice_id=? AND status='pending'",
            (now, order_id, user_id, invoice_id))
        count = claimed.cursor.rowcount if hasattr(claimed, "cursor") else claimed.rowcount
        if count != 1:
            continue
        previous = conn.execute(
            "SELECT period_end FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
        start = max(now, previous[0] if previous and previous[0] > now else now)
        conn.execute("""INSERT INTO subscriptions
            (user_id,product_key,pricing_plan,status,source_reference,period_start,period_end,verified_at,verification_source,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
            product_key=excluded.product_key,pricing_plan=excluded.pricing_plan,
            status=excluded.status,source_reference=excluded.source_reference,
            period_start=excluded.period_start,period_end=excluded.period_end,
            verified_at=excluded.verified_at,verification_source=excluded.verification_source,
            updated_at=excluded.updated_at""",
            (user_id, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
             "active", invoice_id, start, start + 30 * 86400, now,
             "btcpay_production_verified", now))
        activated = True
    return activated
