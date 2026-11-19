"""Referral program: a customer who brings a paying customer earns a free
month of PRO.

How it works:
- Every user has one 8-character referral code (created lazily, on first
  use). Their link is <site>/?ref=<code>.
- A visitor who arrives with ?ref=<code> gets a first-party
  `velxtria_ref` cookie (30 days); registering with that cookie (or with
  ?ref= on the register URL) attributes the signup to the referrer.
- When a referred user pays for PRO and the payment settles, the referrer
  gets one free 30-day PRO period: their current period is extended by 30
  days, or a fresh 30-day period starts if they have none. One reward per
  referred user, ever — the reward claim is idempotent, so duplicate
  reconciles and duplicate webhooks can never credit it twice.
- The reward is account credit, not money out: no payout, no email, no
  SMTP needed. A user who pays $49 to refer themselves saves nothing —
  they paid $49 to earn a $49 month — so there is no arbitrage to guard.
"""
import secrets
import time

CODE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
CODE_LENGTH = 8
REWARD_DAYS = 30
COOKIE_NAME = 'velxtria_ref'
COOKIE_MAX_AGE = 30 * 86400


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS referrals (
      code TEXT PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE, created INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS referral_signups (
      user_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL, created INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(referrer_id) REFERENCES users(id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS referral_rewards (
      referred_user_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL, order_id TEXT NOT NULL,
      credited_at INTEGER NOT NULL,
      FOREIGN KEY(referred_user_id) REFERENCES users(id), FOREIGN KEY(referrer_id) REFERENCES users(id))''')


def valid_code(code):
    return (isinstance(code, str) and len(code) == CODE_LENGTH
            and all(ch in CODE_ALPHABET for ch in code))


def _new_code(conn):
    for _ in range(8):
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not conn.execute('SELECT 1 FROM referrals WHERE code=?', (code,)).fetchone():
            return code
    raise RuntimeError('could not allocate a referral code')


def code_for(conn, user_id):
    """The user's referral code, creating it on first use."""
    row = conn.execute('SELECT code FROM referrals WHERE user_id=?', (user_id,)).fetchone()
    if row:
        return row[0]
    code = _new_code(conn)
    conn.execute('INSERT INTO referrals(code,user_id,created) VALUES (?,?,?)',
                 (code, user_id, int(time.time())))
    return code


def referrer_for_code(conn, code):
    """The user id behind a referral code, or None when it is not a code."""
    if not valid_code(code):
        return None
    row = conn.execute('SELECT user_id FROM referrals WHERE code=?', (code,)).fetchone()
    return row[0] if row else None


def record_signup(conn, new_user_id, code):
    """Attribute a new account to a referrer. Returns the referrer id or None."""
    referrer_id = referrer_for_code(conn, code)
    if not referrer_id or referrer_id == new_user_id:
        return None
    conn.execute('INSERT INTO referral_signups(user_id,referrer_id,created)'
                 ' VALUES (?,?,?) ON CONFLICT(user_id) DO NOTHING',
                 (new_user_id, referrer_id, int(time.time())))
    return referrer_id


def stats(conn, user_id):
    signups = conn.execute('SELECT count(*) FROM referral_signups WHERE referrer_id=?',
                           (user_id,)).fetchone()[0]
    paid = conn.execute('SELECT count(*) FROM referral_rewards WHERE referrer_id=?',
                        (user_id,)).fetchone()[0]
    return {'signups': signups, 'paid': paid, 'months_earned': paid}


def reward_for_payment(conn, user_id, order_id):
    """Credit the referrer one free 30-day PRO period for a settled payment.

    Idempotent: one reward per referred user, ever. Returns True only when
    this call credited the reward.
    """
    setup(conn)
    row = conn.execute('SELECT referrer_id FROM referral_signups WHERE user_id=?',
                       (user_id,)).fetchone()
    if not row:
        return False
    referrer_id = row[0]
    cur = conn.execute('INSERT INTO referral_rewards'
                       '(referred_user_id,referrer_id,order_id,credited_at)'
                       ' VALUES (?,?,?,?) ON CONFLICT(referred_user_id) DO NOTHING',
                       (user_id, referrer_id, order_id, int(time.time())))
    claimed = cur.cursor.rowcount if hasattr(cur, 'cursor') else cur.rowcount
    if claimed != 1:
        return False
    t = int(time.time())
    import subscriptions
    prev = conn.execute('SELECT period_start,period_end FROM subscriptions'
                        ' WHERE user_id=?', (referrer_id,)).fetchone()
    if prev and prev[1] > t:
        start, end = prev[0], prev[1] + REWARD_DAYS * 86400
    else:
        start, end = t, t + REWARD_DAYS * 86400
    conn.execute('''INSERT INTO subscriptions
        (user_id,product_key,pricing_plan,status,source_reference,period_start,period_end,verified_at,verification_source,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
        product_key=excluded.product_key,pricing_plan=excluded.pricing_plan,
        status=excluded.status,source_reference=excluded.source_reference,
        period_start=excluded.period_start,period_end=excluded.period_end,
        verified_at=excluded.verified_at,verification_source=excluded.verification_source,
        updated_at=excluded.updated_at''',
        (referrer_id, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN, 'active',
         'referral:' + order_id, start, end, t, 'referral', t))
    import site_stats
    site_stats.record(conn, 'referral_reward',
                      'referrer=%d referred=%d' % (referrer_id, user_id))
    return True
