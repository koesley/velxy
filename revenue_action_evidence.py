"""Evidence-based revenue action ranking, with no external side effects.

This module is intentionally pure: callers supply workspace-scoped records after
authorization and must never treat estimates as collected revenue.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

MAX_ITEMS = 500
_ALLOWED = {"lead_followup", "invoice_review", "retention", "upsell"}

@dataclass(frozen=True)
class RevenueAction:
    source_id: str
    kind: str
    amount_cents: int
    confidence: Decimal
    days_overdue: int = 0

def rank_actions(actions: Iterable[RevenueAction], limit: int = 20):
    """Return deterministic ranked *proposals*, never executed actions.

    amount_cents is a supplied potential value, not a forecast or receipt.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    candidates = list(actions)
    if len(candidates) > MAX_ITEMS:
        raise ValueError("too many actions")
    seen = set()
    ranked = []
    for item in candidates:
        if not isinstance(item, RevenueAction):
            raise ValueError("invalid action")
        if not isinstance(item.source_id, str) or not 1 <= len(item.source_id) <= 128:
            raise ValueError("invalid source ID")
        if item.kind not in _ALLOWED:
            raise ValueError("unsupported action kind")
        if type(item.amount_cents) is not int or not 0 <= item.amount_cents <= 10**12:
            raise ValueError("invalid potential value")
        if type(item.days_overdue) is not int or not 0 <= item.days_overdue <= 3650:
            raise ValueError("invalid overdue days")
        try:
            confidence = Decimal(str(item.confidence))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("invalid confidence") from None
        if not confidence.is_finite() or not Decimal("0") <= confidence <= Decimal("1"):
            raise ValueError("confidence must be between zero and one")
        key = (item.kind, item.source_id)
        if key in seen:
            raise ValueError("duplicate source")
        seen.add(key)
        score = (Decimal(item.amount_cents) * confidence
                 + Decimal(min(item.days_overdue, 90)) * Decimal("100"))
        ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].kind, pair[1].source_id))
    return [{"source_id": item.source_id, "kind": item.kind,
             "potential_cents": item.amount_cents,
             "confidence": str(Decimal(str(item.confidence))),
             "days_overdue": item.days_overdue,
             "priority_score": str(score),
             "status": "proposal", "verified_revenue_cents": None}
            for score, item in ranked[:limit]]
