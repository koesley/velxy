"""Offline watch-only wallet compatibility check.

Usage on a trusted machine with VELXTRIA_BTC_ACCOUNT_ZPUB set:
    python verify_btc_wallet.py bc1q... --max-index 1000

Never prints or transmits the zpub. Does not prove wallet control or
activate payments; a match only confirms deterministic address derivation.
"""
import argparse
import os
import re
import sys
from bitcoin_addresses import receive_address

def find_address(account_zpub, target, max_index=1000):
    if not isinstance(target, str) or not re.fullmatch(r"bc1q[ac-hj-np-z02-9]{38,58}", target):
        raise ValueError("Expected a mainnet native SegWit receiving address")
    if type(max_index) is not int or not 1 <= max_index <= 10000:
        raise ValueError("Invalid search range")
    for index in range(max_index):
        if receive_address(account_zpub, index) == target:
            return index
    return None

def main():
    parser = argparse.ArgumentParser(description="Verify watch-only BTC receive-address derivation")
    parser.add_argument("address", help="Known BTC receive address")
    parser.add_argument("--max-index", type=int, default=1000)
    args = parser.parse_args()
    key = os.environ.get("VELXTRIA_BTC_ACCOUNT_ZPUB")
    if not key:
        parser.error("VELXTRIA_BTC_ACCOUNT_ZPUB is not configured")
    try:
        index = find_address(key, args.address, args.max_index)
    except ValueError as exc:
        print("Wallet verification failed:", exc, file=sys.stderr)
        return 2
    if index is None:
        print("No match in searched external-chain indices. Checkout remains disabled.")
        return 1
    print("MATCH: wallet receive address at external-chain index", index)
    print("This does not prove wallet ownership or authorize live checkout.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
