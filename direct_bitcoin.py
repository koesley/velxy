"""Experimental direct-BTC payment verifier. Disabled for customer checkout.

Never reuse a deposit address between orders. Never accept a customer-supplied
transaction as proof; only independently query confirmed Bitcoin outputs.
"""
import json
import re
import urllib.request

BLOCKSTREAM = "https://blockstream.info/api"
ADDRESS_RE = re.compile(r"^(bc1[ac-hj-np-z02-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
TXID_RE = re.compile(r"^[0-9a-f]{64}$")
MIN_CONFIRMATIONS = 3


def fetch_json(path):
    request = urllib.request.Request(BLOCKSTREAM + path, headers={
        "Accept": "application/json", "User-Agent": "VELXTRIA-payment-verifier/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def verify_transaction(txid, address, expected_sats, issued_at, *, fetch=fetch_json):
    """Fail closed unless a uniquely assigned address received enough BTC.

    The caller must persist the unique address, quote and issuance timestamp
    BEFORE showing it to the customer. The caller must atomically claim the
    (txid,vout) globally, so no transaction can unlock two accounts.
    """
    if not isinstance(txid, str) or not TXID_RE.fullmatch(txid):
        return []
    if not isinstance(address, str) or not ADDRESS_RE.fullmatch(address):
        return []
    if type(expected_sats) is not int or expected_sats <= 0:
        return []
    if type(issued_at) is not int or issued_at <= 0:
        return []
    tx = fetch("/tx/" + txid)
    tip = fetch("/blocks/tip/height")
    if not isinstance(tx, dict) or tx.get("txid") != txid or type(tip) is not int:
        return []
    status = tx.get("status")
    if not isinstance(status, dict) or status.get("confirmed") is not True:
        return []
    height = status.get("block_height")
    block_time = status.get("block_time")
    if (type(height) is not int or height > tip or
            tip - height + 1 < MIN_CONFIRMATIONS or
            type(block_time) is not int or block_time < issued_at):
        return []
    outputs = tx.get("vout")
    if not isinstance(outputs, list):
        return []
    matched = []
    for index, output in enumerate(outputs):
        if (isinstance(output, dict) and output.get("scriptpubkey_address") == address
                and type(output.get("value")) is int and output["value"] >= expected_sats):
            matched.append((txid, index, output["value"]))
    return matched


def ready_for_launch():
    """A deliberate fail-closed gate until address allocation and quoting exist."""
    return False
