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
