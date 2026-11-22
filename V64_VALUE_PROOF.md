# VELXTRIA V64 — Value Proof Ledger

## Purpose
Produce evidence-backed customer value receipts: verified recovered revenue, verified avoided cost, and hours saved. Keep each unit separate, so the platform cannot inflate an ROI or profit claim. This is a **new standalone pure-Python component**, not yet a live dashboard feature.

## Run
`python -m unittest -v test_value_proof_v64.py`

## Example
```python
from datetime import datetime, timezone
from value_proof_v64 import OutcomeEvidence, build_value_receipt
now = datetime.now(timezone.utc)
receipt = build_value_receipt([
    OutcomeEvidence("workspace-1", "invoice-123", "recovered_revenue",
                    "149.00", now, "billing:invoice-123", True)
], "workspace-1", now)
print(receipt)
```

## Production integration requirements
- Authenticate and authorize workspace before passing events; never trust client-supplied verification.
- Validate source evidence server-side against real records and deduplicate persistently.
- Use an immutable audit trail, retention policy and privacy controls.
- Connect to the authenticated dashboard and persist through a migration with tests.
- Never label saved time as cash, or cost avoidance as realized profit.
- Require independently verified payment evidence before reporting recovered revenue.
