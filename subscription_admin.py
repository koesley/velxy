"""VELXTRIA V9.2 operator-only subscription reconciliation.

This is NOT automated payment verification. The operator must independently
verify the Stripe/Payhip customer, exact plan, successful payment and dates.
Never expose this command through an HTTP endpoint.
"""
import argparse
from datetime import datetime, timezone
import time
import subscriptions


def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamps must include a timezone (e.g. +00:00)')
    return int(dt.astimezone(timezone.utc).timestamp())


def apply(conn, *, email, action, reference, period_start=None, period_end=None, operator_note=''):
    email = email.strip().lower()
    if not email or '@' not in email:
        raise ValueError('Valid customer email required')
    user = conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
    if not user:
        raise ValueError('No matching VELXTRIA account; do not activate by guesswork')
    uid = user[0]
    subscriptions.setup(conn)
    existing = conn.execute('SELECT status FROM subscriptions WHERE user_id=?', (uid,)).fetchone()
    if action == 'activate':
        if not reference.startswith('sub_') or len(reference) > 128:
            raise ValueError('A verified Stripe subscription ID starting sub_ is required')
        if not operator_note.strip() or len(operator_note) > 500:
            raise ValueError('A short verification note is required')
        if period_start is None or period_end is None or not period_start < period_end:
            raise ValueError('A valid verified billing period is required')
        if period_end <= int(time.time()):
            raise ValueError('Cannot activate an expired billing period')
        status, verified_at, source = 'active', int(time.time()), 'manual_stripe_dashboard'
        start, end = period_start, period_end
    elif action == 'revoke':
        if not existing:
            raise ValueError('No subscription record to revoke')
        if not operator_note.strip():
            raise ValueError('Reason for revocation required')
        status, verified_at, source = 'canceled', 0, ''
        start, end = 0, 0
        reference = reference or 'manual_revocation'
    else:
        raise ValueError('Unsupported action')
    # Do not persist payment credentials, notes containing customer details, or keys.
    # The operator's verification note is mandatory but retained in their external audit log.
    if existing:
        conn.execute('''UPDATE subscriptions SET product_key=?,pricing_plan=?,status=?,source_reference=?,
          period_start=?,period_end=?,verified_at=?,verification_source=?,updated_at=? WHERE user_id=?''',
          (subscriptions.PRODUCT_KEY,subscriptions.PRICING_PLAN,status,reference,start,end,verified_at,source,int(time.time()),uid))
    else:
        conn.execute('''INSERT INTO subscriptions
          (user_id,product_key,pricing_plan,status,source_reference,period_start,period_end,
           verified_at,verification_source,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
          (uid,subscriptions.PRODUCT_KEY,subscriptions.PRICING_PLAN,status,reference,start,end,verified_at,source,int(time.time())))
    conn.commit()
    return uid


def main():
    p=argparse.ArgumentParser(description='Manual verified subscription access; operator only')
    p.add_argument('action',choices=('activate','revoke'))
    p.add_argument('--email',required=True)
    p.add_argument('--reference',default='')
    p.add_argument('--start',help='Verified billing start, ISO 8601 with timezone')
    p.add_argument('--end',help='Verified billing end, ISO 8601 with timezone')
    p.add_argument('--note',required=True,help='Why this was independently verified/revoked; keep an external audit log')
    p.add_argument('--confirm-verified',action='store_true',help='Affirm independently verified billing evidence')
    args=p.parse_args()
    if not args.confirm_verified:
        p.error('Refusing to change access without --confirm-verified')
    if args.action=='activate' and (not args.start or not args.end):
        p.error('Activation requires --start and --end')
    import portal
    with portal.db() as conn:
        uid=apply(conn,email=args.email,action=args.action,reference=args.reference,
                  period_start=timestamp(args.start) if args.start else None,
                  period_end=timestamp(args.end) if args.end else None,operator_note=args.note)
    print(f'{args.action} completed for account ID {uid}; verify dashboard entitlement')

if __name__=='__main__':
    main()
