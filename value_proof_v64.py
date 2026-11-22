"""V64 Value Proof: conservative, tenant-scoped evidence-backed outcome receipts.

Pure Python; no database access, external requests, billing claims or side effects.
The caller must authenticate and authorize workspace access.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable

KINDS = frozenset({"recovered_revenue", "cost_avoided", "hours_saved"})
MAX_EVENTS = 10000

@dataclass(frozen=True)
class OutcomeEvidence:
    workspace_id: str
    evidence_id: str
    kind: str
    amount: str
    observed_at: datetime
    source_ref: str
    verified: bool = False

def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)

def build_value_receipt(events: Iterable[OutcomeEvidence], workspace_id: str,
                        as_of: datetime) -> dict:
    """Summarize only verified, unique evidence, without extrapolation.

    Monetary amounts are USD; hours are distinct and never converted to money.
    Evidence identifiers must be unique per workspace, including unverified items.
    """
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace_id required")
    cutoff = _utc(as_of)
    seen = set()
    totals = {kind: Decimal("0") for kind in KINDS}
    accepted = []
    rejected = {"unverified": 0, "future": 0}
    count = 0
    for event in events:
        count += 1
        if count > MAX_EVENTS:
            raise ValueError("Too many events")
        if not isinstance(event, OutcomeEvidence):
            raise ValueError("Expected OutcomeEvidence")
        if event.workspace_id != workspace_id:
            continue
        if not isinstance(event.evidence_id, str) or not event.evidence_id.strip():
            raise ValueError("evidence_id required")
        if event.evidence_id in seen:
            raise ValueError("Duplicate evidence_id")
        seen.add(event.evidence_id)
        if event.kind not in KINDS:
            raise ValueError("Unsupported kind")
        if not isinstance(event.source_ref, str) or not event.source_ref.strip():
            raise ValueError("source_ref required")
        try:
            value = Decimal(event.amount)
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Invalid amount") from None
        if not value.is_finite() or value <= 0:
            raise ValueError("Amount must be positive and finite")
        if _utc(event.observed_at) > cutoff:
            rejected["future"] += 1
        elif event.verified is not True:
            rejected["unverified"] += 1
        else:
            totals[event.kind] += value
            accepted.append({"evidence_id": event.evidence_id, "kind": event.kind,
                             "amount": str(value), "source_ref": event.source_ref})
    return {
        "workspace_id": workspace_id, "as_of": cutoff.isoformat(),
        "verified_evidence_count": len(accepted),
        "verified_totals": {kind: str(totals[kind]) for kind in sorted(KINDS)},
        "units": {"recovered_revenue": "USD", "cost_avoided": "USD",
                  "hours_saved": "hours"},
        "evidence": accepted, "excluded": rejected,
        "limitations": [
            "Verified means caller-attested; independently validate source records.",
            "Recovered revenue and avoided cost are separate; do not present their sum as profit.",
            "No causality, forecasts, billing verification or ROI is inferred.",
            "Authorize workspace access before calling; do not expose raw evidence publicly."
        ]
    }
