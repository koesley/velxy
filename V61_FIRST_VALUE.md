# VELXTRIA V61 — First Value

Tenant-scoped, pure-Python product activation and observed cohort analytics.

Measures signup-to-first-value activation, observed signup-to-paid conversion, median time to first value, and day-7/30/90 return-event rates with mature-cohort denominators. Does not mistake signup or login for customer value.

## Example
```python
from datetime import datetime, timezone
from first_value_v61 import ProductEvent, analyze_activation
t = datetime.now(timezone.utc)
result = analyze_activation([ProductEvent("workspace", "anonymous-1", "signup", t),
                             ProductEvent("workspace", "anonymous-1", "first_value", t)],
                            "workspace", t)
print(result)
```

## Tests
```bash
python -m unittest -v test_first_value_v61.py
```

## Production integration requirements
1. Authorize workspace access before calling; this pure module is not an authentication boundary.
2. Store minimal, pseudonymous event identifiers with consent, retention limits, and a workspace index.
3. Define 'first_value' as a meaningful completed customer workflow, not a page view.
4. Capture events idempotently and record provenance and schema version.
5. Verify billing provider webhooks before representing 'paid' as actual revenue.
6. Add authenticated dashboard routes and UI, migration, tests, and deploy checks before advertising this as live.

## Limitations
A 'paid' event is only a recorded claim. Day-N retention is a return event within the exact day-N 24-hour window, not continuous usage or subscription retention. The module does not perform database queries, emit external actions, or make causal or revenue predictions.
