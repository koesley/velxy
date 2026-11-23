"""Deterministic recurring-revenue leakage detection.

Pure calculations. Never charges, emails, or modifies customer accounts.
Input records must be authorized and scoped to one tenant by the caller.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date

CENT = Decimal("0.01")


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amount must be finite and nonnegative")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SubscriptionSignal:
    subscription_id: str
    monthly_amount: object
    status: str
    failed_payment_count: int = 0
    renewal_date: str | None = None
    cancellation_requested: bool = False


def detect_leakage(signals, as_of: str):
    """Return review-only recommendations, not a revenue forecast.

    Status is one of active, past_due, canceled, trialing. Missing renewal
    dates are allowed. IDs are opaque; no personal data is returned.
    """
    today = date.fromisoformat(as_of)
    seen = set()
    opportunities = []
    active_mrr = Decimal("0")
    at_risk_mrr = Decimal("0")
    for item in signals:
        if not isinstance(item.subscription_id, str) or not item.subscription_id.strip():
            raise ValueError("Subscription ID required")
        if item.subscription_id in seen:
            raise ValueError("Duplicate subscription ID")
        seen.add(item.subscription_id)
        amount = _amount(item.monthly_amount)
        if item.status not in {"active", "past_due", "canceled", "trialing"}:
            raise ValueError("Unsupported status")
        if isinstance(item.failed_payment_count, bool) or not isinstance(item.failed_payment_count, int) or item.failed_payment_count < 0:
            raise ValueError("Invalid failed payment count")
        renewal = date.fromisoformat(item.renewal_date) if item.renewal_date else None
        if not isinstance(item.cancellation_requested, bool):
            raise ValueError("Invalid cancellation flag")
        if item.status == "active":
            active_mrr += amount
        if item.status in {"active", "past_due"}:
            reasons = []
            if item.status == "past_due":
                reasons.append("payment_past_due")
            if item.failed_payment_count:
                reasons.append("failed_payment")
            if item.cancellation_requested:
                reasons.append("cancellation_requested")
            if renewal is not None and 0 <= (renewal - today).days <= 7:
                reasons.append("renewal_within_7_days")
            if reasons:
                at_risk_mrr += amount
                opportunities.append({
                    "subscription_id": item.subscription_id,
                    "monthly_amount_at_risk": str(amount),
                    "reasons": reasons,
                    "priority": "high" if item.status == "past_due" or item.cancellation_requested else "medium",
                    "recommended_action": "Review billing status and request approval for a compliant customer follow-up",
                    "requires_approval": True,
                })
    opportunities.sort(key=lambda x: (x["priority"] != "high", -Decimal(x["monthly_amount_at_risk"]), x["subscription_id"]))
    return {
        "as_of": today.isoformat(),
        "subscriptions_checked": len(seen),
        "active_mrr": str(active_mrr),
        "monthly_revenue_at_risk": str(at_risk_mrr),
        "opportunities": opportunities,
        "disclaimer": "At-risk amounts are existing subscription amounts, not verified losses or recoverable income. No actions are executed.",
    }
