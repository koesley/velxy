"""VELXTRIA Stripe card checkout (card payments alongside Bitcoin).

This module mirrors btcpay_mainnet.py: same structure, same safety rules,
same public interface, adapted for Stripe's API. It is the card-payment
counterpart to the BTCPay mainnet integration; the two paths are
deliberately separate: different env vars, different order prefixes, and
separate order tables so a card payment can never be mistaken for a
Bitcoin payment (and vice versa).

Configuration (Render environment variables only; never hardcode or commit):
  VELXTRIA_STRIPE_SECRET_KEY             Secret key (sk_live_ or sk_test_)
  VELXTRIA_STRIPE_WEBHOOK_SECRET         Secret configured on the Stripe webhook
  VELXTRIA_ENABLE_STRIPE_CHECKOUT=1      master switch for the checkout route
  VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION=1 opt-in: allow test-mode sessions
                                          to activate PRO (tests only;
                                          default off — test keys must
                                          never grant PRO in production)

Safety rules enforced here:
  * PRO is granted only after a direct Stripe API read confirms session id,
    $49.00 USD amount (4900 cents), USD currency, order ownership, and
    paid payment_status.
  * A browser redirect or a webhook payload is never proof of payment. A
    webhook is only a trigger to re-verify against Stripe, and only a
    signature-verified webhook is accepted at all.
  * Test-mode sessions (livemode False) can never activate PRO unless
    VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION=1 is explicitly set.
  * Settlement is idempotent: a conditional claim (UPDATE ... WHERE
    status='pending') means one settled session can activate PRO exactly
    once, no matter how often reconciliation or the webhook runs.
  * The session's success_url sends the payer back to
    /account?paid=1&method=stripe. That page re-verifies against Stripe
    before showing any confirmation; the redirect itself is never proof
    of payment.
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

STRIPE_API = 'https://api.stripe.com/v1'
PRICE_CENTS = 4900
PRICE = '49.00'
DAYS = 30
ORDER_PREFIX = 'vx-stripe-'
VERIFICATION_SOURCE = 'stripe_verified'

# Stripe webhook events that carry a checkout session. Any event naming a
# known session triggers a re-verification against the Stripe API; the
# payload itself is never treated as payment proof.
WEBHOOK_EVENTS = {
    'checkout.session.completed',
    'checkout.session.async_payment_succeeded',
}


def _env(name):
    return os.getenv(name, '').strip()


def configured():
    """True only when a Stripe secret key is present. Anything else fails closed."""
    return bool(_env('VELXTRIA_STRIPE_SECRET_KEY'))


def checkout_enabled():
    """Master switch for the customer checkout route."""
    return os.getenv('VELXTRIA_ENABLE_STRIPE_CHECKOUT', '0') == '1' and configured()


def site_url():
    """Public site URL sessions redirect payers back to. Override with
    VELXTRIA_SITE_URL; the default is the production preview URL."""
    return os.getenv(
        'VELXTRIA_SITE_URL',
        'https://velxtria-private-preview-tzie.onrender.com').rstrip('/')


def webhook_configured():
    return configured() and bool(_env('VELXTRIA_STRIPE_WEBHOOK_SECRET'))


def log_event(event, **fields):
    """Payment logging without secrets. Only identifiers and statuses."""
    safe = ' '.join('%s=%s' % (k, v) for k, v in sorted(fields.items()))
    print('stripe %s %s' % (event, safe), flush=True)


def request(method, path, payload=None):
    if not configured():
        raise RuntimeError('Stripe checkout not configured')
    headers = {'Authorization': 'Bearer ' + _env('VELXTRIA_STRIPE_SECRET_KEY'), 'Accept': 'application/json'}
    data = None
    if payload is not None:
        # Stripe's API takes form-encoded bodies; nested keys are passed
        # flat, e.g. line_items[0][price_data][currency]=usd.
        data = urllib.parse.urlencode(payload).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(STRIPE_API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)
    except (OSError, ValueError) as exc:
        # OSError covers URLError/HTTPError/SSLError/socket failures: a
        # network or TLS problem must fail closed as a RuntimeError, never
        # crash the request handler.
        raise RuntimeError('Stripe request failed; check configuration and API permissions') from exc


def setup(conn):
    # Serialize PostgreSQL schema initialization across concurrent requests.
    # CREATE TABLE IF NOT EXISTS alone is not safe against simultaneous first creates.
    # Transaction-scoped lock releases automatically on commit or rollback.
    # Guard on the connection itself, not the REMOTE flag: the flag
    # describes the deployment, but setup can be handed a sqlite
    # connection while the flag is set (tests, the Render build), and the
    # Postgres-only lock call crashes on sqlite.
    import persistent
    if isinstance(conn, persistent.PgConnection):
        conn.execute('SELECT pg_advisory_xact_lock(731246, 921036)')
    conn.execute('''CREATE TABLE IF NOT EXISTS stripe_orders (
      order_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
      session_id TEXT UNIQUE, checkout_url TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'creating', created_at INTEGER NOT NULL,
      settled_at INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.execute('CREATE INDEX IF NOT EXISTS stripe_orders_user ON stripe_orders(user_id, created_at)')
    conn.execute('''CREATE TABLE IF NOT EXISTS stripe_webhook_events (
      fingerprint TEXT PRIMARY KEY, session_id TEXT NOT NULL,
      event_type TEXT NOT NULL DEFAULT '', received_at INTEGER NOT NULL)''')


def create_order(conn, user_id):
    """Persist the order before making the external call; failed attempts cannot grant access."""
    if not configured():
        raise RuntimeError('Stripe checkout not configured')
    order_id = ORDER_PREFIX + secrets.token_hex(16)
    conn.execute("INSERT INTO stripe_orders(order_id,user_id,created_at) VALUES (?,?,?)",
                 (order_id, user_id, int(time.time())))
    # Caller commits before network I/O so the session always has a recorded owner.
    log_event('order_created', order_id=order_id, user_id=user_id)
    return order_id


def create_checkout_session(order_id):
    result = request('POST', '/checkout/sessions', {
        'mode': 'payment',
        'line_items[0][price_data][currency]': 'usd',
        'line_items[0][price_data][unit_amount]': PRICE_CENTS,
        'line_items[0][price_data][product_data][name]': 'VELXTRIA PRO - 30 Days - 50 Reports',
        'line_items[0][quantity]': 1,
        'success_url': site_url() + '/account?paid=1&method=stripe',
        'cancel_url': site_url() + '/account',
        'metadata[order_id]': order_id,
    })
    session_id = result.get('id') if isinstance(result, dict) else None
    checkout_url = result.get('url') if isinstance(result, dict) else None
    if not session_id or not checkout_url:
        raise RuntimeError('Stripe did not return a valid checkout session')
    log_event('checkout_session_created', order_id=order_id, session_id=session_id)
    return session_id, checkout_url


def latest_order(conn, user_id):
    """Newest Stripe order for a user, or None. Used for customer-facing state."""
    row = conn.execute("SELECT order_id,status,checkout_url,created_at,settled_at FROM stripe_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
                       (user_id,)).fetchone()
    if not row:
        return None
    return {'order_id': row[0], 'status': row[1], 'checkout_url': row[2],
            'created_at': row[3], 'settled_at': row[4]}


def pending_order(conn, user_id):
    """Newest unpaid Stripe order for a user, or None."""
    row = conn.execute("SELECT order_id,checkout_url,created_at FROM stripe_orders WHERE user_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
                       (user_id,)).fetchone()
    if not row:
        return None
    return {'order_id': row[0], 'checkout_url': row[1], 'created_at': row[2]}


def verify_session(session, order_id, session_id=None):
    """Pure verification of a Stripe checkout session payload against an order.

    Returns (True, '') when the session proves a $49.00 USD payment for
    this order, otherwise (False, reason). Never raises on bad data.
    """
    if not isinstance(session, dict):
        return False, 'session payload is not an object'
    if session.get('id') is None:
        return False, 'session has no id'
    if session_id is not None and session.get('id') != session_id:
        return False, 'session id does not match'
    meta = session.get('metadata') or {}
    if not isinstance(meta, dict):
        return False, 'session metadata is not an object'
    if meta.get('order_id') != order_id:
        return False, 'session order does not match'
    if session.get('payment_status') != 'paid':
        return False, 'session not paid'
    if session.get('amount_total') != PRICE_CENTS:
        return False, 'session amount does not match'
    if session.get('currency') != 'usd':
        return False, 'session currency is not usd'
    # A test-mode session must never grant PRO in production; only an
    # explicit opt-in (tests) allows it.
    if session.get('livemode') is False and os.getenv('VELXTRIA_STRIPE_ALLOW_TEST_ACTIVATION', '0') != '1':
        return False, 'test mode session cannot activate PRO'
    return True, ''


def _claim_and_activate(conn, user_id, order_id, session_id):
    """Atomically claim a settled session and grant one 30-day PRO period.

    Returns True only when this call won the claim. The conditional UPDATE
    means duplicate checks, duplicate webhooks, and concurrent reconciles
    can never extend a subscription twice for the same session.
    """
    result = conn.execute("UPDATE stripe_orders SET status='settled',settled_at=? WHERE order_id=? AND user_id=? AND session_id=? AND status='pending'",
                          (int(time.time()), order_id, user_id, session_id))
    claimed = result.cursor.rowcount if hasattr(result, 'cursor') else result.rowcount
    if claimed != 1:
        return False
    t = int(time.time())
    # Each settled session grants one 30-day period. A renewal extends the
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
        (user_id, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN, 'active', session_id,
         start, end, t, VERIFICATION_SOURCE, t))
    log_event('pro_activated', order_id=order_id, session_id=session_id, user_id=user_id)
    import site_stats
    site_stats.record(conn, 'pro_activated', order_id)
    import referrals
    referrals.reward_for_payment(conn, user_id, order_id)
    import notifications
    row = conn.execute('SELECT email FROM users WHERE id=?', (user_id,)).fetchone()
    if row:
        notifications.queue_pro_confirmation(conn, user_id, row[0], end, order_id, method='card')
    return True


def reconcile(conn, user_id, req=None):
    """Re-verify every pending Stripe order for a user against Stripe.

    Only the authenticated order owner can cause a verified payment to
    activate PRO. Returns True when this call activated PRO.
    """
    fetch = req or request
    orders = conn.execute("SELECT order_id,session_id FROM stripe_orders WHERE user_id=? AND status='pending' AND session_id IS NOT NULL ORDER BY created_at DESC LIMIT 30", (user_id,)).fetchall()
    activated = False
    for order_id, session_id in orders:
        try:
            session = fetch('GET', '/checkout/sessions/' + urllib.parse.quote(session_id, safe=''))
        except (RuntimeError, OSError):
            log_event('reconcile_unavailable', order_id=order_id, session_id=session_id, user_id=user_id)
            continue
        ok, reason = verify_session(session, order_id, session_id)
        status = session.get('status') if isinstance(session, dict) else None
        if not ok and status == 'expired':
            conn.execute("UPDATE stripe_orders SET status='expired' WHERE order_id=? AND user_id=? AND session_id=? AND status='pending'",
                         (order_id, user_id, session_id))
            log_event('session_terminal', order_id=order_id, session_id=session_id, status='expired')
            continue
        if not ok:
            log_event('session_not_verified', order_id=order_id, session_id=session_id, reason=reason)
            continue
        if _claim_and_activate(conn, user_id, order_id, session_id):
            activated = True
    return activated


def verify_webhook_signature(raw_body, signature_header):
    """Verify a Stripe webhook signature. Stripe signs "<timestamp>.<raw
    body>" with HMAC-SHA256 using the webhook secret; the header is
    `Stripe-Signature: t=<unix timestamp>,v1=<hex>`.

    Fails closed: no secret configured, no header, a missing or
    non-integer timestamp, a missing v1, a mismatch, or a timestamp older
    than 300 seconds (replay window) all return False. The secret itself
    is never logged.
    """
    secret = _env('VELXTRIA_STRIPE_WEBHOOK_SECRET')
    if not secret or not signature_header:
        return False
    parts = {}
    for item in signature_header.strip().split(','):
        if '=' not in item:
            continue
        key, value = item.split('=', 1)
        parts.setdefault(key.strip(), []).append(value.strip())
    timestamps = parts.get('t') or []
    signatures = parts.get('v1') or []
    if not timestamps or not signatures:
        return False
    try:
        timestamp = int(timestamps[0])
    except (TypeError, ValueError):
        return False
    if int(time.time()) - timestamp > 300:
        return False
    signed_payload = ('%d.' % timestamp).encode('utf-8') + raw_body
    expected = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def handle_webhook(conn, raw_body, signature_header):
    """Process one Stripe webhook delivery.

    The signature is verified first; an unverified delivery is rejected and
    changes nothing. A verified delivery is only a trigger: the session is
    re-read from Stripe and verified before any access changes. Duplicate
    deliveries (same body) are recorded by fingerprint and ignored.
    Returns (http_status, message).
    """
    if not verify_webhook_signature(raw_body, signature_header):
        log_event('webhook_rejected', reason='bad_signature')
        return 401, 'Invalid webhook signature'
    if not webhook_configured():
        return 503, 'Stripe webhook not configured'
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (ValueError, UnicodeError):
        return 400, 'Invalid webhook payload'
    if not isinstance(payload, dict):
        return 400, 'Invalid webhook payload'
    event_type = payload.get('type', '')
    data = payload.get('data') or {}
    session = data.get('object') if isinstance(data, dict) else None
    if not isinstance(session, dict):
        session = {}
    session_id = session.get('id')
    if not session_id:
        return 200, 'Ignored: no session'
    fingerprint = hashlib.sha256(raw_body).hexdigest()
    seen = conn.execute('SELECT fingerprint FROM stripe_webhook_events WHERE fingerprint=?', (fingerprint,)).fetchone()
    if seen:
        log_event('webhook_duplicate', session_id=session_id, event_type=event_type)
        return 200, 'Duplicate delivery ignored'
    row = conn.execute("SELECT order_id,user_id FROM stripe_orders WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        log_event('webhook_unknown_session', session_id=session_id, event_type=event_type)
        return 200, 'Ignored: unknown session'
    if event_type not in WEBHOOK_EVENTS:
        return 200, 'Ignored: event type'
    order_id, user_id = row
    try:
        reconcile(conn, user_id)
    except (RuntimeError, OSError):
        # Do not record the fingerprint: a later redelivery must retry.
        log_event('webhook_reconcile_unavailable', order_id=order_id, session_id=session_id)
        return 503, 'Stripe verification unavailable; retry later'
    try:
        conn.execute('INSERT INTO stripe_webhook_events(fingerprint,session_id,event_type,received_at) VALUES (?,?,?,?)',
                     (fingerprint, session_id, event_type, int(time.time())))
    except Exception:
        pass  # Concurrent duplicate delivery; reconciliation already ran.
    log_event('webhook_processed', session_id=session_id, event_type=event_type, order_id=order_id)
    return 200, 'Webhook processed'
