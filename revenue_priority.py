"""Deterministic, explainable revenue opportunity prioritization.

This module does not claim predicted revenue or execute business actions.
All monetary inputs must be supplied by the business or a trusted integration.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable


@dataclass(frozen=True)
class RevenueOpportunity:
    identifier: str
    title: str
    estimated_value: Decimal
    confidence: float
    urgency: float
    effort_hours: float
    evidence: str


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("estimated_value must be a valid monetary number") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("estimated_value must be finite and nonnegative")
    return result


def rank_opportunities(items: Iterable[RevenueOpportunity]) -> list[dict]:
    """Rank candidates using a bounded, transparent heuristic.

    confidence and urgency are numbers between 0 and 1. The score is a
    *relative priority*, not a probability of conversion or guaranteed ROI.
    """
    ranked = []
    seen = set()
    for item in items:
        if not item.identifier or item.identifier in seen:
            raise ValueError("identifiers must be unique and nonempty")
        seen.add(item.identifier)
        if not item.title.strip() or not item.evidence.strip():
            raise ValueError("title and evidence are required")
        value = _money(item.estimated_value)
        import math
        if not all(math.isfinite(x) for x in (item.confidence, item.urgency, item.effort_hours)):
            raise ValueError("inputs must be finite")
        if not 0 <= item.confidence <= 1 or not 0 <= item.urgency <= 1:
            raise ValueError("confidence and urgency must be between 0 and 1")
        if item.effort_hours < 0:
            raise ValueError("effort_hours must be nonnegative")
        weighted_value = value * Decimal(str(item.confidence))
        # Diminishing returns prevent very large estimates from dominating.
        value_signal = math.log1p(float(min(weighted_value, Decimal("1000000000"))))
        score = round((value_signal * (0.5 + item.urgency)) / (1 + math.sqrt(item.effort_hours)), 4)
        ranked.append({
            "identifier": item.identifier,
            "title": item.title,
            "priority_score": score,
            "estimated_value": str(value),
            "confidence": item.confidence,
            "urgency": item.urgency,
            "effort_hours": item.effort_hours,
            "evidence": item.evidence,
            "explanation": "Score weighs confidence-adjusted value and urgency against estimated effort; not guaranteed revenue.",
            "requires_approval": True,
        })
    return sorted(ranked, key=lambda x: (-x["priority_score"], x["identifier"]))
