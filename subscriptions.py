"""V9 subscription tracking, fail-closed. Payhip notifications are NOT payment proof."""
import os, time
from datetime import datetime, timezone

PRODUCT_KEY = 'iFbye'
PRICING_PLAN = 'MrW6D9VRBN'
PRO_LIMIT = 50

def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
      user_id INTEGER PRIMARY KEY,
      product_key TEXT NOT NULL,
      pricing_plan TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending_review',
      source_reference TEXT NOT NULL DEFAULT '',
      period_start INTEGER NOT NULL DEFAULT 0,
      period_end INTEGER NOT NULL DEFAULT 0,
      verified_at INTEGER NOT NULL DEFAULT 0,
      verification_source TEXT NOT NULL DEFAULT '',
      updated_at INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.execute('CREATE INDEX IF NOT EXISTS subscriptions_status ON subscriptions(status)')

def observe_webhook(conn, email, event_type, reference):
    """Record a claim for review; never activate, extend, or cancel verified access."""
    setup(conn)
    row=conn.execute('SELECT id FROM users WHERE email=?',(email.lower().strip(),)).fetchone()
    if not row: return False
    uid=row[0]
    existing=conn.execute('SELECT status FROM subscriptions WHERE user_id=?',(uid,)).fetchone()
    # A notification cannot change an independently verified subscription.
    if existing and existing[0] in ('active','cancel_at_period_end'): return False
    if event_type=='subscription.deleted': status='cancellation_pending_review'
    elif event_type=='refunded': status='refund_pending_review'
    else: status='pending_review'
    if existing:
        conn.execute('UPDATE subscriptions SET status=?,source_reference=?,updated_at=? WHERE user_id=?',
                     (status,reference,int(time.time()),uid))
    else:
        conn.execute('''INSERT INTO subscriptions
        (user_id,product_key,pricing_plan,status,source_reference,updated_at)
        VALUES (?,?,?,?,?,?)''',(uid,PRODUCT_KEY,PRICING_PLAN,status,reference,int(time.time())))
    return True

def entitlement(conn, user_id, current=None):
    """Only an independently verified, unexpired period grants PRO."""
    current=int(time.time()) if current is None else current
    row=conn.execute('''SELECT status,period_start,period_end,verified_at,verification_source,
      product_key,pricing_plan FROM subscriptions WHERE user_id=?''',(user_id,)).fetchone()
    if row and row[0] in ('active','cancel_at_period_end') and row[1]<=current<row[2] and row[3]>0 and row[4] and row[5]==PRODUCT_KEY and row[6]==PRICING_PLAN:
        return {'plan':'pro','start':row[1],'end':row[2],'status':row[0]}
    d=datetime.fromtimestamp(current,timezone.utc)
    start=int(datetime(d.year,d.month,1,tzinfo=timezone.utc).timestamp())
    return {'plan':'demo','start':start,'end':None,'status':row[0] if row else 'demo'}

def usage(conn, user_id, current=None):
    ent=entitlement(conn,user_id,current)
    if ent['plan']=='pro':
        used=conn.execute('SELECT count(*) FROM reports WHERE user_id=? AND created>=? AND created<?',
                          (user_id,ent['start'],ent['end'])).fetchone()[0]
    else:
        used=conn.execute('SELECT count(*) FROM reports WHERE user_id=? AND created>=?',
                          (user_id,ent['start'])).fetchone()[0]
    return ent,used,max(0,PRO_LIMIT-used)
