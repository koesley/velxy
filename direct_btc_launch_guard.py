"""Operational launch guard for VELXTRIA direct Bitcoin checkout.

Fail closed until operator confirms receiving-address ownership, persistent
database support, a running monitor, and an end-to-end small-value test.
This does not accept wallet secrets or enable the public checkout.
"""
import os
import bitcoin_addresses


def readiness(*, account_zpub=None, wallet_first_address=None,
              persistent_database=False, monitoring_enabled=False,
              end_to_end_tested=False):
    checks = {
        "wallet_public_key_configured": False,
        "wallet_receive_address_matches": False,
        "persistent_database": bool(persistent_database),
        "continuous_monitoring": bool(monitoring_enabled),
        "end_to_end_payment_test": bool(end_to_end_tested),
    }
    if account_zpub:
        try:
            expected = bitcoin_addresses.receive_address(account_zpub, 0)
            checks["wallet_public_key_configured"] = True
            checks["wallet_receive_address_matches"] = (
                isinstance(wallet_first_address, str)
                and expected == wallet_first_address)
        except (ValueError, TypeError):
            pass
    return {"ready": all(checks.values()), "checks": checks}


def live_checkout_enabled():
    """Always disabled until separate reviewed integration and deployment."""
    return False
