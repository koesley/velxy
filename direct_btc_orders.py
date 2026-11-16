"""Persistent, fail-closed direct-Bitcoin order address allocation.

Requires a compatible BIP84 account zpub supplied securely by the operator.
Only public keys and receive addresses are stored. No live checkout integration.
SQLite transaction serialization and UNIQUE constraints protect allocations;
PostgreSQL requires a transactional adapter with equivalent row locking.
"""
import secrets
import time

from bitcoin_addresses import receive_address


def setup(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_btc_address_counter (
        wallet_id TEXT PRIMARY KEY,
        next_index INTEGER NOT NULL CHECK(next_index >= 0 AND next_index < 2147483648)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_btc_orders (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        wallet_id TEXT NOT NULL,
        address_index INTEGER NOT NULL,
        address TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'awaiting_quote',
        created_at INTEGER NOT NULL,
        UNIQUE(wallet_id,address_index),
        CHECK(status IN ('awaiting_quote','pending','settled','expired','cancelled'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_btc_claims (
        txid TEXT NOT NULL,
        vout INTEGER NOT NULL CHECK(vout >= 0),
        order_id TEXT NOT NULL,
        claimed_at INTEGER NOT NULL,
        PRIMARY KEY(txid,vout),
        FOREIGN KEY(order_id) REFERENCES direct_btc_orders(order_id)
    )""")


def allocate_sqlite(conn, user_id, wallet_id, account_zpub, *, now=None):
    """Allocate once, atomically. Caller must NOT have an active transaction.

    BEGIN IMMEDIATE serializes writers. On any exception the transaction rolls
    back, so a failed request cannot consume or reuse a partial allocation.
    """
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Invalid user")
    if not isinstance(wallet_id, str) or not wallet_id or len(wallet_id) > 100:
        raise ValueError("Invalid wallet identifier")
    if conn.in_transaction:
        raise RuntimeError("Allocation requires its own SQLite transaction")
    now = int(time.time()) if now is None else now
    conn.execute("BEGIN IMMEDIATE")
    try:
        setup(conn)
        row = conn.execute(
            "SELECT next_index FROM direct_btc_address_counter WHERE wallet_id=?",
            (wallet_id,)).fetchone()
        index = row[0] if row else 0
        if index >= 2147483647:
            raise OverflowError("BIP32 address index exhausted")
        address = receive_address(account_zpub, index)
        order_id = "vx-direct-" + secrets.token_hex(16)
        if row:
            conn.execute("UPDATE direct_btc_address_counter SET next_index=? WHERE wallet_id=?",
                         (index + 1, wallet_id))
        else:
            conn.execute("INSERT INTO direct_btc_address_counter VALUES (?,?)",
                         (wallet_id, index + 1))
        conn.execute("""INSERT INTO direct_btc_orders
            (order_id,user_id,wallet_id,address_index,address,status,created_at)
            VALUES (?,?,?,?,?,'awaiting_quote',?)""",
            (order_id, user_id, wallet_id, index, address, now))
        conn.commit()
        return {"order_id": order_id, "address": address, "index": index}
    except BaseException:
        conn.rollback()
        raise


def claim_output(conn, order_id, txid, vout, *, now=None):
    """Claim a verified blockchain output at most once globally.

    Caller MUST independently verify the output, exact order amount, address,
    confirmation count and quote validity BEFORE invoking this method.
    This function intentionally never grants PRO access.
    """
    if not isinstance(order_id, str) or not order_id.startswith("vx-direct-"):
        raise ValueError("Invalid order")
    if not isinstance(txid, str) or len(txid) != 64 or any(c not in "0123456789abcdef" for c in txid):
        raise ValueError("Invalid transaction ID")
    if type(vout) is not int or vout < 0:
        raise ValueError("Invalid output index")
    now = int(time.time()) if now is None else now
    row = conn.execute("SELECT status FROM direct_btc_orders WHERE order_id=?",
                       (order_id,)).fetchone()
    if not row or row[0] != "pending":
        return False
    try:
        conn.execute("INSERT INTO direct_btc_claims VALUES (?,?,?,?)",
                     (txid, vout, order_id, now))
    except Exception as exc:
        # Only duplicate output claims should return False; propagate other DB errors.
        if "unique" in str(exc).lower() or "primary key" in str(exc).lower():
            return False
        raise
    return True
