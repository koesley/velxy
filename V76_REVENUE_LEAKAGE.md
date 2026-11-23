# VELXTRIA Revenue Leakage V76

A pure-Python, review-only detector for recurring subscription revenue at risk.

## What it does
- Accepts tenant-scoped subscription signals supplied by an authorized caller.
- Identifies past-due subscriptions, failed payments, cancellation requests, and renewals within seven days.
- Deduplicates overlapping risk reasons per subscription.
- Returns active MRR, total monthly subscription amounts at risk, and prioritized review recommendations.
- Never charges customers, sends outreach, reads a database, or changes subscription status.

## Run tests
```bash
python -m unittest -v test_revenue_leakage_v76.py
```

## Example
```python
from revenue_leakage_v76 import SubscriptionSignal, detect_leakage

result = detect_leakage(
    [SubscriptionSignal("sub_123", "49.00", "past_due", failed_payment_count=1)],
    as_of="2026-11-22",
)
print(result)
```

## Integration prerequisites
1. Authenticate and authorize workspace access before loading signals.
2. Scope subscription reads to one tenant; never combine customers across tenants.
3. Map real payment-provider status and verified timestamps; avoid fabricated revenue.
4. Require explicit approval and consent-compliant messaging before follow-up.
5. Store idempotency keys and audit records for any future action integration.
6. Distinguish subscription amounts at risk from money recovered or collected.

**Status:** backend utility committed to repository; not connected to live UI, billing, or a scheduler. Automated tests are provided but have not been executed in this session. No revenue increase is claimed.
