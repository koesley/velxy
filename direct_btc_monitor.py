"""Conservative direct Bitcoin order monitoring.

Record a transaction's first observation DURING an active quote, then confirm
the same output later. If monitoring missed the quote window, fail closed.
An operator must still verify wallet ownership before enabling checkout.
"""
import time
import direct_bitcoin


def setup(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_btc_observations (
        order_id TEXT NOT NULL,
        txid TEXT NOT NULL,
        vout INTEGER NOT NULL,
        observed_at INTEGER NOT NULL,
        PRIMARY KEY(order_id,txid,vout),
        FOREIGN KEY(order_id) REFERENCES direct_btc_orders(order_id)
    )""")


def observe_order(conn, order_id, user_id, *, now=None, fetch=direct_bitcoin.fetch_json):
    """Poll Esplora address transactions, recording only outputs seen in quote window.

    Must be called regularly while a quote is valid. Caller commits transaction.
    The blockchain API is external and can fail; errors must not imply payment.
    """
    now = int(time.time()) if now is None else now
    row = conn.execute("""SELECT o.address,q.expected_sats,q.issued_at,q.expires_at
        FROM direct_btc_orders o JOIN direct_btc_quotes q ON q.order_id=o.order_id
        WHERE o.order_id=? AND o.user_id=? AND o.status='pending'""",
        (order_id, user_id)).fetchone()
    if not row or not row[2] <= now <= row[3]:
        return 0
    address, expected_sats, _, _ = row
    if not direct_bitcoin.ADDRESS_RE.fullmatch(address):
        raise ValueError("Invalid assigned address")
    # First page only. Never claim exhaustive history from this endpoint.
    txs = fetch("/address/" + address + "/txs")
    if not isinstance(txs, list):
        raise ValueError("Unexpected blockchain response")
    setup(conn)
    count = 0
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        txid = tx.get("txid")
        if not isinstance(txid, str) or not direct_bitcoin.TXID_RE.fullmatch(txid):
            continue
        outputs = tx.get("vout")
        if not isinstance(outputs, list):
            continue
        for vout, output in enumerate(outputs):
            if (isinstance(output, dict) and output.get("scriptpubkey_address") == address
                    and type(output.get("value")) is int and output["value"] >= expected_sats):
                cursor = conn.execute("""INSERT OR IGNORE INTO direct_btc_observations
                    (order_id,txid,vout,observed_at) VALUES (?,?,?,?)""",
                    (order_id, txid, vout, now))
                count += cursor.rowcount
    return count


def observed_in_quote(conn, order_id, txid, vout):
    row = conn.execute("""SELECT obs.observed_at,q.issued_at,q.expires_at
        FROM direct_btc_observations obs
        JOIN direct_btc_quotes q ON q.order_id=obs.order_id
        WHERE obs.order_id=? AND obs.txid=? AND obs.vout=?""",
        (order_id, txid, vout)).fetchone()
    return bool(row and row[1] <= row[0] <= row[2])
