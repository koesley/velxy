"""First Value V61: privacy-conscious, tenant-scoped activation analytics.

This module never sends messages, collects payments, or calls external services.
Callers must authenticate and authorize workspace access before supplying events.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

ALLOWED = frozenset({"signup", "first_value", "paid", "returned"})
WINDOW_DAYS = (7, 30, 90)


@dataclass(frozen=True)
class ProductEvent:
    workspace_id: str
    customer_id: str
    event_type: str
    occurred_at: datetime


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Event timestamps must be timezone-aware datetimes")
    return value.astimezone(timezone.utc)


def analyze_activation(events: Iterable[ProductEvent], workspace_id: str, as_of: datetime) -> dict:
    """Compute observed signup cohorts, first-value activation, and return rates.

    Customers are pseudonymous identifiers. First value is an explicitly
    recorded outcome, never inferred from logins or checklist completion.
    Retention requires a separate 'returned' event after signup, within
    the day-N window and on or after day N (not mere elapsed presence).
    Cohorts without full observation time are excluded from each rate.
    """
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id required")
    cutoff = _utc(as_of)
    by_customer = defaultdict(lambda: defaultdict(list))
    for event in events:
        if not isinstance(event, ProductEvent):
            raise ValueError("Events must be ProductEvent instances")
        if event.workspace_id != workspace_id:
            continue
        if not event.customer_id or not event.customer_id.strip():
            raise ValueError("customer_id required")
        if event.event_type not in ALLOWED:
            raise ValueError("Unsupported event type")
        stamp = _utc(event.occurred_at)
        if stamp <= cutoff:
            by_customer[event.customer_id][event.event_type].append(stamp)

    eligible = []
    anomalies = 0
    for customer, history in by_customer.items():
        signups = history.get("signup", [])
        if not signups:
            anomalies += 1
            continue
        signup = min(signups)
        activated = min((x for x in history.get("first_value", []) if x >= signup), default=None)
        paid = min((x for x in history.get("paid", []) if x >= signup), default=None)
        returns = [x for x in history.get("returned", []) if x > signup]
        eligible.append((signup, activated, paid, returns))
    total = len(eligible)
    activated_count = sum(activated is not None for _, activated, _, _ in eligible)
    paid_count = sum(paid is not None for _, _, paid, _ in eligible)
    durations = sorted((activated - signup).total_seconds() / 3600
                       for signup, activated, _, _ in eligible if activated is not None)
    retention = {}
    from datetime import timedelta
    for days in WINDOW_DAYS:
        mature = [(signup, returns) for signup, _, _, returns in eligible
                  if signup + timedelta(days=days) <= cutoff]
        retained = sum(any(signup + timedelta(days=days) <= t <
                           signup + timedelta(days=days + 1) for t in returns)
                       for signup, returns in mature)
        retention[str(days)] = {
            "eligible": len(mature), "retained": retained,
            "rate_pct": round(100 * retained / len(mature), 2) if mature else None,
        }
    return {
        "workspace_id": workspace_id,
        "signups": total,
        "activated": activated_count,
        "activation_rate_pct": round(100 * activated_count / total, 2) if total else None,
        "paid_customers_observed": paid_count,
        "signup_to_paid_rate_pct": round(100 * paid_count / total, 2) if total else None,
        "median_time_to_first_value_hours": (
            round((durations[(len(durations)-1)//2] + durations[len(durations)//2])/2, 2)
            if durations else None
        ),
        "day_n_retention": retention,
        "customers_with_events_but_no_signup": anomalies,
        "notes": [
            "Only events supplied to this function are counted; no billing verification.",
            "First value must represent an independently defined customer outcome.",
            "Day-N retention means a return event during that specific 24-hour window.",
            "Late-arriving events and incomplete instrumentation can change metrics.",
            "No inference of causal uplift, profit, or future conversion.",
        ],
    }
