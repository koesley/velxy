"""Payhip webhook staging for VELXTRIA V3; local-only, no paid access grants.

Payhip documents signature=sha256(API_KEY), not a body HMAC. The signature
therefore does not bind individual payload fields. Keep events in review state
until a production-grade reconciliation strategy is available.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import time

EVENTS = {'paid', 'refunded', 'subscription.created', 'subscription.deleted'}
PRODUCT_KEY = 'ajTs4'


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS payhip_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      fingerprint TEXT NOT NULL UNIQUE,
      event_type TEXT NOT NULL,
      reference_id TEXT NOT NULL,
      customer_email TEXT NOT NULL,
      product_key TEXT NOT NULL,
      received_at INTEGER NOT NULL,
      review_status TEXT NOT NULL DEFAULT 'pending_review',
      event_json TEXT NOT NULL
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS payhip_events_customer ON payhip_events(customer_email)')


def accept_event(conn, raw):
    key = os.environ.get('VELXTRIA_PAYHIP_API_KEY', '')
    if not key:
        return 503, 'Payhip webhook not configured'
    if len(raw) > 65536:
        return 413, 'Payload too large'
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError()
    except (ValueError, UnicodeError):
        return 400, 'Invalid JSON'
    signature = data.get('signature', '')
    expected = hashlib.sha256(key.encode('utf-8')).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        return 401, 'Invalid signature'
    kind = data.get('type')
    if kind not in EVENTS:
        return 400, 'Unsupported event'
    if kind.startswith('subscription.'):
        reference = data.get('subscription_id', '')
        email = data.get('customer_email', '')
        product_key = data.get('product_link', '')
    else:
        reference = data.get('id', '')
        email = data.get('email', '')
        items = data.get('items', [])
        if not isinstance(items, list):
            return 400, 'Invalid items'
        matches = [i for i in items if isinstance(i, dict) and i.get('product_key') == PRODUCT_KEY]
        product_key = PRODUCT_KEY if matches else ''
    if not isinstance(reference, str) or not reference or len(reference) > 128:
        return 400, 'Missing reference'
    if not isinstance(email, str) or '@' not in email or len(email) > 254:
        return 400, 'Invalid email'
    if product_key != PRODUCT_KEY:
        # Acknowledge unrelated Payhip products without adding them to VELXTRIA records.
        return 200, 'Ignored unrelated product'
    fingerprint = hashlib.sha256(raw).hexdigest()
    # Avoid storing signature, IP address, or unrelated buyer details.
    safe = {'type': kind, 'reference_id': reference, 'email': email.lower().strip(), 'product_key': PRODUCT_KEY}
    if kind == 'paid':
        safe['currency'] = data.get('currency')
        safe['price'] = data.get('price')
    if kind == 'refunded':
        safe['amount_refunded'] = data.get('amount_refunded')
    setup(conn)
    try:
        conn.execute('''INSERT INTO payhip_events
        (fingerprint,event_type,reference_id,customer_email,product_key,received_at,event_json)
        VALUES (?,?,?,?,?,?,?)''',
        (fingerprint,kind,reference,email.lower().strip(),PRODUCT_KEY,int(time.time()),json.dumps(safe)))
        conn.commit()
    except sqlite3.IntegrityError:
        return 200, 'Duplicate acknowledged'
    return 200, 'Received for review (no access granted)'
