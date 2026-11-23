"""Operator-only revenue review from an authorized payment-provider export.

Never exposed as an HTTP endpoint. Does not send messages or alter billing.
"""
import argparse
import json
from datetime import date
from pathlib import Path
from revenue_leakage_v76 import SubscriptionSignal, detect_leakage


def review_export(payload, as_of):
    if not isinstance(payload, dict) or not isinstance(payload.get("subscriptions"), list):
        raise ValueError("Expected a JSON object with subscriptions array")
    if len(payload["subscriptions"]) > 100000:
        raise ValueError("Export exceeds safety limit")
    signals = []
    for entry in payload["subscriptions"]:
        if not isinstance(entry, dict):
            raise ValueError("Subscription entries must be objects")
        allowed = {"subscription_id", "monthly_amount", "status", "failed_payment_count", "renewal_date", "cancellation_requested"}
        if set(entry) - allowed:
            raise ValueError("Unexpected fields in subscription export")
        signals.append(SubscriptionSignal(**entry))
    result = detect_leakage(signals, as_of)
    result["source"] = "operator_supplied_export_unverified"
    return result


def main():
    parser = argparse.ArgumentParser(description="Review a verified, authorized subscription export; no side effects")
    parser.add_argument("export", help="Path to private JSON export; never commit customer data")
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    data = json.loads(Path(args.export).read_text(encoding="utf-8"))
    print(json.dumps(review_export(data, args.as_of), indent=2))


if __name__ == "__main__":
    main()
