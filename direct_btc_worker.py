"""Conservative CLI monitoring for direct Bitcoin orders (not enabled on Render).

Usage: python direct_btc_worker.py /path/to/persistent.sqlite
Only uses orders already quoted and persisted by the app. Never accepts
customer-provided settlement claims or enables checkout.
"""
import argparse
import sqlite3
import time
import direct_btc_monitor
import direct_btc_billing


def scan_once(conn, *, now=None):
    now = int(time.time()) if now is None else now
    rows = conn.execute("""SELECT o.order_id,o.user_id,q.expires_at
        FROM direct_btc_orders o JOIN direct_btc_quotes q ON q.order_id=o.order_id
        WHERE o.status='pending' ORDER BY q.issued_at LIMIT 100""").fetchall()
    observed = activated = 0
    for order_id, user_id, expires_at in rows:
        try:
            if now <= expires_at:
                observed += direct_btc_monitor.observe_order(conn, order_id, user_id, now=now)
                conn.commit()
            txs = conn.execute("""SELECT txid,vout FROM direct_btc_observations
                WHERE order_id=? ORDER BY observed_at LIMIT 100""", (order_id,)).fetchall()
            for txid, vout in txs:
                if direct_btc_billing.settle_verified_output(
                        conn, order_id, user_id, txid, vout, verified_at=now):
                    activated += 1
                    conn.commit()
                    break
                conn.rollback()
        except Exception:
            conn.rollback()
            # A temporary API failure must never grant access.
            continue
    return {"observed": observed, "activated": activated}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", help="Persistent SQLite database path")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    if args.interval < 15:
        parser.error("Minimum poll interval is 15 seconds")
    conn = sqlite3.connect(args.database, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        while True:
            scan_once(conn)
            time.sleep(args.interval)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
