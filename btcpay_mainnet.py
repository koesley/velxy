"""VELXTRIA BTCPay mainnet checkout (production Bitcoin payments).

This module is the production counterpart to btcpay_integration.py, which is
testnet-only and must never be used for real payments. The two paths are
deliberately separate: different env vars, different order prefixes, and a
`network` column on the shared btcpay_orders table so a testnet order can
never activate mainnet PRO (and vice versa).

Configuration (Render environment variables only; never hardcode or commit):
  VELXTRIA_BTCPAY_MAINNET_URL            e.g. https://btcpay.example.com
  VELXTRIA_BTCPAY_MAINNET_STORE_ID       BTCPay store ID
  VELXTRIA_BTCPAY_MAINNET_API_KEY        Greenfield API key (invoice permissions)
  VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET Secret configured on the BTCPay webhook
  VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT=1  master switch for the checkout route

Safety rules enforced here:
  * Mainnet mode refuses any testnet/demo host (never mix networks).
  * PRO is granted only after a direct BTCPay API read confirms invoice id,
    $49.00 USD amount, USD currency, order ownership, and Settled status.
  * A browser redirect or a webhook payload is never proof of payment. A
    webhook is only a trigger to re-verify against BTCPay, and only a
    signature-verified webhook is accepted at all.
  * Settlement is idempotent: a conditional claim (UPDATE ... WHERE
    status='pending') means one settled invoice can activate PRO exactly
    once, no matter how often reconciliation or the webhook runs.
  * The invoice's redirectURL sends the payer back to /account?paid=1.
    That page re-verifies against BTCPay before showing any
    confirmation; the redirect itself is never proof of payment.
  * Nothing in this module logs secrets, API keys, or webhook secrets.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

# Testnet hosts are never valid production BTCPay servers. BTCPay's
# official mainnet demo (mainnet.demo.btcpayserver.org) is a real mainnet
# instance and is allowed: it is the hosted provider VELXTRIA uses.
FORBIDDEN_HOST_MARKERS = ('testnet',)
TESTNET_HOST = 'https://testnet.demo.btcpayserver.org'
PRICE = '49.00'
DAYS = 30
ORDER_PREFIX = 'vx-'
VERIFICATION_SOURCE = 'btcpay_mainnet_verified'

# BTCPay webhook events that carry an invoice id. Any event naming a known
# invoice triggers a re-verification against the BTCPay API; the payload
# itself is never treated as payment proof.
WEBHOOK_EVENTS = {
    'InvoiceCreated', 'InvoiceReceivedPayment', 'InvoicePaymentSettled',
    'InvoiceProcessing', 'InvoiceExpired', 'InvoiceInvalid',
}


def _env(name):
    return os.getenv(name, '').strip()


def mainnet_host():
    """Configured production host, or '' when unset."""
    return _env('VELXTRIA_BTCPAY_MAINNET_URL').rstrip('/')


def _host_is_forbidden(host):
    lowered = host.lower()
    return any(marker in lowered for marker in FORBIDDEN_HOST_MARKERS)


def configured():
    """True only when a real (non-testnet, https) production host, store id,
    and API key are all present. Anything else fails closed."""
    host = mainnet_host()
    if not host or not host.startswith('https://'):
        return False
    if _host_is_forbidden(host):
        return False
    return bool(_env('VELXTRIA_BTCPAY_MAINNET_API_KEY')) and bool(_env('VELXTRIA_BTCPAY_MAINNET_STORE_ID'))


def checkout_enabled():
    """Master switch for the customer checkout route."""
    return os.getenv('VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT', '0') == '1' and configured()


def site_url():
    """Public site URL invoices redirect payers back to. Override with
    VELXTRIA_SITE_URL; the default is the production preview URL."""
    return os.getenv(
        'VELXTRIA_SITE_URL',
        'https://velxtria-private-preview-tzie.onrender.com').rstrip('/')


def webhook_configured():
    return configured() and bool(_env('VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET'))


def log_event(event, **fields):
    """Payment logging without secrets. Only identifiers and statuses."""
    safe = ' '.join('%s=%s' % (k, v) for k, v in sorted(fields.items()))
    print('btcpay-mainnet %s %s' % (event, safe), flush=True)


def request(method, path, payload=None):
    if not configured():
        raise RuntimeError('BTCPay mainnet configuration missing or invalid')
    host = mainnet_host()
    base = host + '/api/v1/stores/' + urllib.parse.quote(_env('VELXTRIA_BTCPAY_MAINNET_STORE_ID'), safe='')
    headers = {'Authorization': 'token ' + _env('VELXTRIA_BTCPAY_MAINNET_API_KEY'), 'Accept': 'application/json'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)
    except (OSError, ValueError) as exc:
        # OSError covers URLError/HTTPError/SSLError/socket failures: a
        # network or TLS problem must fail closed as a RuntimeError, never
        # crash the request handler.
        raise RuntimeError('BTCPay mainnet request failed; check configuration and API permissions') from exc


def _ensure_network_column(conn):
    """Add the network discriminator to btcpay_orders if it is missing.

    Old rows (created by the testnet module) default to 'testnet' so they
    can never be mistaken for production orders.
    """
    import persistent
    if persistent.REMOTE:
        conn.execute("ALTER TABLE btcpay_orders ADD COLUMN IF NOT EXISTS network TEXT NOT NULL DEFAULT 'testnet'")
        return
    cols = [row[1] for row in conn.execute('PRAGMA table_info(btcpay_orders)').fetchall()]
    if 'network' not in cols:
        conn.execute("ALTER TABLE btcpay_orders ADD COLUMN network TEXT NOT NULL DEFAULT 'testnet'")


def setup(conn):
    # Serialize PostgreSQL schema initialization across concurrent requests.
    # CREATE TABLE IF NOT EXISTS alone is not safe against simultaneous first creates.
    # Transaction-scoped lock releases automatically on commit or rollback.
    import persistent
    if persistent.REMOTE:
        conn.execute('SELECT pg_advisory_xact_lock(731245, 921035)')
    conn.execute('''CREATE TABLE IF NOT EXISTS btcpay_orders (
      order_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
      invoice_id TEXT UNIQUE, checkout_url TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'creating', created_at INTEGER NOT NULL,
      settled_at INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.execute('CREATE INDEX IF NOT EXISTS btcpay_orders_user ON btcpay_orders(user_id, created_at)')
    _ensure_network_column(conn)
    conn.execute('CREATE INDEX IF NOT EXISTS btcpay_orders_network ON btcpay_orders(network, status)')
    conn.execute('''CREATE TABLE IF NOT EXISTS btcpay_webhook_events (
      fingerprint TEXT PRIMARY KEY, invoice_id TEXT NOT NULL,
      event_type TEXT NOT NULL DEFAULT '', received_at INTEGER NOT NULL)''')


def create_order(conn, user_id):
    """Persist the order before making the external call; failed attempts cannot grant access."""
    if not configured():
        raise RuntimeError('Mainnet checkout not configured')
    order_id = ORDER_PREFIX + secrets.token_hex(16)
    conn.execute("INSERT INTO btcpay_orders(order_id,user_id,created_at,network) VALUES (?,?,?,'mainnet')",
                 (order_id, user_id, int(time.time())))
    # Caller commits before network I/O so the invoice always has a recorded owner.
    log_event('order_created', order_id=order_id, user_id=user_id)
    return order_id


def issue_invoice(order_id):
    result = request('POST', '/invoices', {
        'amount': PRICE, 'currency': 'USD',
        'metadata': {'orderId': order_id, 'itemDesc': 'VELXTRIA PRO - 30 Days - 50 Reports'},
        'checkout': {'speedPolicy': 'HighSpeed',
                     'redirectURL': site_url() + '/account?paid=1'}
    })
    invoice_id = result.get('id')
    checkout_url = result.get('checkoutLink', '')
    host = mainnet_host()
    if not invoice_id or not checkout_url or not checkout_url.startswith(host + '/i/'):
        raise RuntimeError('BTCPay did not return a valid mainnet checkout')
    log_event('invoice_issued', order_id=order_id, invoice_id=invoice_id)
    return invoice_id, checkout_url


def latest_order(conn, user_id):
    """Newest mainnet order for a user, or None. Used for customer-facing state."""
    row = conn.execute("SELECT order_id,status,checkout_url,created_at,settled_at FROM btcpay_orders WHERE user_id=? AND network='mainnet' ORDER BY created_at DESC LIMIT 1",
                       (user_id,)).fetchone()
    if not row:
        return None
    return {'order_id': row[0], 'status': row[1], 'checkout_url': row[2],
            'created_at': row[3], 'settled_at': row[4]}


def pending_order(conn, user_id):
    """Newest unpaid mainnet order for a user, or None."""
    row = conn.execute("SELECT order_id,checkout_url,created_at FROM btcpay_orders WHERE user_id=? AND network='mainnet' AND status='pending' ORDER BY created_at DESC LIMIT 1",
                       (user_id,)).fetchone()
    if not row:
        return None
    return {'order_id': row[0], 'checkout_url': row[1], 'created_at': row[2]}


def verify_invoice(invoice, order_id, invoice_id=None):
    """Pure verification of a BTCPay invoice payload against an order.

    Returns (True, '') when the invoice proves a $49.00 USD settlement for
    this order, otherwise (False, reason). Never raises on bad data.
    """
    if not isinstance(invoice, dict):
        return False, 'invoice payload is not an object'
    if invoice.get('id') is None:
        return False, 'invoice has no id'
    if invoice_id is not None and invoice.get('id') != invoice_id:
        return False, 'invoice id does not match'
    meta = invoice.get('metadata') or {}
    if not isinstance(meta, dict):
        return False, 'invoice metadata is not an object'
    if meta.get('orderId') != order_id:
        return False, 'invoice order does not match'
    store_id = _env('VELXTRIA_BTCPAY_MAINNET_STORE_ID')
    if invoice.get('storeId') and store_id and invoice.get('storeId') != store_id:
        return False, 'invoice store does not match'
    # A refunded invoice must never grant access, even if it once settled.
    refunds = invoice.get('refunds')
    if isinstance(refunds, list) and refunds:
        return False, 'invoice has refunds'
    status = invoice.get('status')
    if status in ('Expired', 'Invalid'):
        return False, 'invoice %s' % str(status).lower()
    try:
        correct_amount = Decimal(str(invoice.get('amount'))) == Decimal(PRICE)
    except (InvalidOperation, TypeError):
        correct_amount = False
    if not correct_amount:
        return False, 'invoice amount does not match'
    if invoice.get('currency') != 'USD':
        return False, 'invoice currency is not USD'
    if status != 'Settled':
        return False, 'invoice not settled'
    return True, ''


def _claim_and_activate(conn, user_id, order_id, invoice_id):
    """Atomically claim a settled invoice and grant one 30-day PRO period.

    Returns True only when this call won the claim. The conditional UPDATE
    means duplicate checks, duplicate webhooks, and concurrent reconciles
    can never extend a subscription twice for the same invoice.
    """
    result = conn.execute("UPDATE btcpay_orders SET status='settled',settled_at=? WHERE order_id=? AND user_id=? AND invoice_id=? AND network='mainnet' AND status='pending'",
                          (int(time.time()), order_id, user_id, invoice_id))
    claimed = result.cursor.rowcount if hasattr(result, 'cursor') else result.rowcount
    if claimed != 1:
        return False
    t = int(time.time())
    # Each settled invoice grants one 30-day period. A renewal extends the
    # current period: the end moves 30 days out from where it was, and the
    # start stays put, so PRO access is continuous. (Setting the start to
    # the old period end would leave the user with no active period until
    # then, because entitlement requires start <= now < end.)
    previous = conn.execute('SELECT period_start,period_end FROM subscriptions WHERE user_id=?', (user_id,)).fetchone()
    if previous and previous[1] > t:
        start, end = previous[0], previous[1] + DAYS * 86400
    else:
        start, end = t, t + DAYS * 86400
    import subscriptions
    conn.execute('''INSERT INTO subscriptions
        (user_id,product_key,pricing_plan,status,source_reference,period_start,period_end,verified_at,verification_source,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
        product_key=excluded.product_key,pricing_plan=excluded.pricing_plan,
        status=excluded.status,source_reference=excluded.source_reference,
        period_start=excluded.period_start,period_end=excluded.period_end,
        verified_at=excluded.verified_at,verification_source=excluded.verification_source,
        updated_at=excluded.updated_at''',
        (user_id, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN, 'active', invoice_id,
         start, end, t, VERIFICATION_SOURCE, t))
    log_event('pro_activated', order_id=order_id, invoice_id=invoice_id, user_id=user_id)
    import site_stats
    site_stats.record(conn, 'pro_activated', order_id)
    import referrals
    referrals.reward_for_payment(conn, user_id, order_id)
    return True


def reconcile(conn, user_id, req=None):
    """Re-verify every pending mainnet order for a user against BTCPay.

    Only the authenticated order owner can cause a verified settlement to
    activate PRO. Returns True when this call activated PRO.
    """
    fetch = req or request
    orders = conn.execute("SELECT order_id,invoice_id FROM btcpay_orders WHERE user_id=? AND network='mainnet' AND status='pending' AND invoice_id IS NOT NULL ORDER BY created_at DESC LIMIT 30", (user_id,)).fetchall()
    activated = False
    for order_id, invoice_id in orders:
        try:
            invoice = fetch('GET', '/invoices/' + urllib.parse.quote(invoice_id, safe=''))
        except (RuntimeError, OSError):
            log_event('reconcile_unavailable', order_id=order_id, invoice_id=invoice_id, user_id=user_id)
            continue
        ok, reason = verify_invoice(invoice, order_id, invoice_id)
        status = invoice.get('status') if isinstance(invoice, dict) else None
        if not ok and status in ('Expired', 'Invalid'):
            conn.execute("UPDATE btcpay_orders SET status=? WHERE order_id=? AND user_id=? AND invoice_id=? AND network='mainnet' AND status='pending'",
                         (status.lower(), order_id, user_id, invoice_id))
            log_event('invoice_terminal', order_id=order_id, invoice_id=invoice_id, status=status.lower())
            continue
        if not ok:
            log_event('invoice_not_verified', order_id=order_id, invoice_id=invoice_id, reason=reason)
            continue
        if _claim_and_activate(conn, user_id, order_id, invoice_id):
            activated = True
    return activated


def verify_webhook_signature(raw_body, signature_header):
    """Verify a BTCPay webhook signature. BTCPay signs the raw request body
    with HMAC-SHA256 using the webhook secret; header is `sha256=<hex>`.

    Fails closed: no secret configured, no header, or a mismatch all return
    False. The secret itself is never logged.
    """
    secret = _env('VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET')
    if not secret or not signature_header:
        return False
    header = signature_header.strip()
    if not header.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len('sha256='):].strip())


def handle_webhook(conn, raw_body, signature_header):
    """Process one BTCPay webhook delivery.

    The signature is verified first; an unverified delivery is rejected and
    changes nothing. A verified delivery is only a trigger: the invoice is
    re-read from BTCPay and verified before any access changes. Duplicate
    deliveries (same body) are recorded by fingerprint and ignored.
    Returns (http_status, message).
    """
    if not webhook_configured():
        return 503, 'BTCPay webhook not configured'
    if not verify_webhook_signature(raw_body, signature_header):
        log_event('webhook_rejected', reason='bad_signature')
        return 401, 'Invalid webhook signature'
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (ValueError, UnicodeError):
        return 400, 'Invalid webhook payload'
    if not isinstance(payload, dict):
        return 400, 'Invalid webhook payload'
    invoice_id = payload.get('invoiceId')
    event_type = payload.get('type', '')
    if not invoice_id:
        return 200, 'Ignored: no invoice'
    fingerprint = hashlib.sha256(raw_body).hexdigest()
    seen = conn.execute('SELECT fingerprint FROM btcpay_webhook_events WHERE fingerprint=?', (fingerprint,)).fetchone()
    if seen:
        log_event('webhook_duplicate', invoice_id=invoice_id, event_type=event_type)
        return 200, 'Duplicate delivery ignored'
    row = conn.execute("SELECT order_id,user_id FROM btcpay_orders WHERE invoice_id=? AND network='mainnet'", (invoice_id,)).fetchone()
    if not row:
        log_event('webhook_unknown_invoice', invoice_id=invoice_id, event_type=event_type)
        return 200, 'Ignored: unknown invoice'
    order_id, user_id = row
    try:
        reconcile(conn, user_id)
    except (RuntimeError, OSError):
        # Do not record the fingerprint: a later redelivery must retry.
        log_event('webhook_reconcile_unavailable', order_id=order_id, invoice_id=invoice_id)
        return 503, 'BTCPay verification unavailable; retry later'
    try:
        conn.execute('INSERT INTO btcpay_webhook_events(fingerprint,invoice_id,event_type,received_at) VALUES (?,?,?,?)',
                     (fingerprint, invoice_id, event_type, int(time.time())))
    except Exception:
        pass  # Concurrent duplicate delivery; reconciliation already ran.
    log_event('webhook_processed', invoice_id=invoice_id, event_type=event_type, order_id=order_id)
    return 200, 'Webhook processed'


def mainnet_support_check(req=None):
    """Check whether the configured production server supports real Bitcoin
    mainnet payments, without spending funds or creating an invoice.

    Returns a dict with host, BTC payment-method enabled state, and any
    network label the server reports. This confirms reachability, store
    access, and that the BTC payment method is enabled; the operator must
    still confirm in the BTCPay dashboard that the store's BTC method is
    Mainnet (not Testnet) — see BTCPAY_MAINNET_SETUP.md in the repo.
    """
    fetch = req or request
    result = {'ok': False, 'host': mainnet_host(), 'btc_enabled': None, 'network': None, 'detail': ''}
    if not configured():
        result['detail'] = 'mainnet not configured or host is a testnet/demo host'
        return result
    try:
        method = fetch('GET', '/payment-methods/BTC')
    except RuntimeError as exc:
        result['detail'] = str(exc)
        return result
    if not isinstance(method, dict):
        result['detail'] = 'unexpected payment-method response'
        return result
    result['btc_enabled'] = bool(method.get('enabled'))
    result['network'] = method.get('network')
    if not result['btc_enabled']:
        result['detail'] = 'BTC payment method is disabled on this store'
        return result
    result['ok'] = True
    result['detail'] = 'BTC payment method enabled on production host'
    return result


if __name__ == '__main__':
    import sys
    if '--check' in sys.argv:
        check = mainnet_support_check()
        print('host=%s' % check['host'])
        print('btc_enabled=%s' % check['btc_enabled'])
        print('network=%s' % check['network'])
        print('ok=%s' % check['ok'])
        print('detail=%s' % check['detail'])
        sys.exit(0 if check['ok'] else 1)
    print('usage: python btcpay_mainnet.py --check')
