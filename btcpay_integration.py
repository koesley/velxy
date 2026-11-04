"""VELXTRIA BTCPay testnet checkout. Never use this module for mainnet checkout."""
import json, os, secrets, time, urllib.error, urllib.parse, urllib.request

HOST = 'https://testnet.demo.btcpayserver.org'
PRICE = '49.00'
DAYS = 30

def configured():
    return (os.getenv('VELXTRIA_BTCPAY_URL', '').rstrip('/') == HOST
            and bool(os.getenv('VELXTRIA_BTCPAY_API_KEY'))
            and bool(os.getenv('VELXTRIA_BTCPAY_STORE_ID')))

def request(method, path, payload=None):
    if not configured():
        raise RuntimeError('BTCPay testnet configuration missing or URL is not testnet')
    base = HOST + '/api/v1/stores/' + urllib.parse.quote(os.environ['VELXTRIA_BTCPAY_STORE_ID'], safe='')
    headers = {'Authorization': 'token ' + os.environ['VELXTRIA_BTCPAY_API_KEY'], 'Accept': 'application/json'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        raise RuntimeError('BTCPay request failed; check testnet configuration and API permissions') from exc

def setup(conn):
    # Serialize PostgreSQL schema initialization across concurrent requests.
    # CREATE TABLE IF NOT EXISTS alone is not safe against simultaneous first creates.
    # Transaction-scoped lock releases automatically on commit or rollback.
    import persistent
    if persistent.REMOTE:
        conn.execute('SELECT pg_advisory_xact_lock(731245, 921034)')
    conn.execute('''CREATE TABLE IF NOT EXISTS btcpay_orders (
      order_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
      invoice_id TEXT UNIQUE, checkout_url TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'creating', created_at INTEGER NOT NULL,
      settled_at INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.execute('CREATE INDEX IF NOT EXISTS btcpay_orders_user ON btcpay_orders(user_id, created_at)')

def create_order(conn, user_id):
    """Persist the order before making the external call; failed attempts cannot grant access."""
    if not configured():
        raise RuntimeError('Test checkout not configured')
    order_id = 'vx-test-' + secrets.token_hex(16)
    conn.execute('INSERT INTO btcpay_orders(order_id,user_id,created_at) VALUES (?,?,?)',
                 (order_id, user_id, int(time.time())))
    # Caller commits before network I/O so the invoice always has a recorded owner.
    return order_id

def issue_invoice(order_id):
    result = request('POST', '/invoices', {
        'amount': PRICE, 'currency': 'USD',
        'metadata': {'orderId': order_id, 'itemDesc': 'VELXTRIA PRO - 30 Days - 50 Reports (TESTNET)'},
        'checkout': {'speedPolicy': 'HighSpeed'}
    })
    invoice_id = result.get('id')
    checkout_url = result.get('checkoutLink', '')
    if not invoice_id or not checkout_url or not checkout_url.startswith(HOST + '/i/'):
        raise RuntimeError('BTCPay did not return a valid testnet checkout')
    return invoice_id, checkout_url

def reconcile(conn, user_id):
    """Only the authenticated order owner can cause a verified settlement to activate PRO.

    A transaction/unique invoice record ensures repeated checks never extend access.
    """
    orders = conn.execute("SELECT order_id,invoice_id FROM btcpay_orders WHERE user_id=? AND status='pending' AND invoice_id IS NOT NULL ORDER BY created_at DESC LIMIT 5", (user_id,)).fetchall()
    activated = False
    for order_id, invoice_id in orders:
        invoice = request('GET', '/invoices/' + urllib.parse.quote(invoice_id, safe=''))
        meta = invoice.get('metadata') or {}
        if (invoice.get('id') != invoice_id or invoice.get('status') != 'Settled'
                or str(invoice.get('amount')) not in ('49', '49.0', '49.00')
                or invoice.get('currency') != 'USD' or meta.get('orderId') != order_id):
            continue
        # SQLite/PostgreSQL both support this conditional claim; only one checker wins.
        result = conn.execute("UPDATE btcpay_orders SET status='settled',settled_at=? WHERE order_id=? AND user_id=? AND invoice_id=? AND status='pending'",
                               (int(time.time()), order_id, user_id, invoice_id))
        claimed = result.cursor.rowcount if hasattr(result, 'cursor') else result.rowcount
        if claimed != 1:
            continue
        t = int(time.time())
        # Each settled invoice grants one 30-day period; a renewal starts when the previous ends.
        previous = conn.execute('SELECT period_end FROM subscriptions WHERE user_id=?', (user_id,)).fetchone()
        start = max(t, previous[0] if previous and previous[0] > t else t)
        end = start + DAYS * 86400
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
            (user_id,subscriptions.PRODUCT_KEY,subscriptions.PRICING_PLAN,'active',invoice_id,
             start,end,t,'btcpay_testnet_verified',t))
        activated = True
    return activated
