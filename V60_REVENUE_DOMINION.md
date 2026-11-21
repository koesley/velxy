# VELXTRIA Revenue Dominion V60

An independently usable, deterministic SaaS unit-economics engine. It calculates monthly recurring revenue, contribution after variable costs, acquisition spend, contribution after fixed and acquisition costs, static break-even customer count, and simplified LTV/CAC/payback metrics.

## Run
```bash
python -m unittest -v test_revenue_dominion_v60.py
```

## Example
```python
from revenue_dominion_v60 import SaaSScenario, analyze
result = analyze(SaaSScenario(100, "49", "9", "1000", ".05", "100", 10))
print(result)
```

## Integration status
This is a backend calculation component, **not yet connected to portal routes or the production UI**. No customer data is read and no billing is performed. Integration should require authenticated workspace access, persisted scenario provenance, CSRF protection for writes, and an explicit user-facing assumptions label.

## Financial caveats
These are modeled assumptions, not collected revenue, financial advice, causal attribution, or reliable forecasts. CAC is charged for the assumed new-customer count; break-even excludes acquisition costs. Constant-churn LTV is an oversimplification and is intentionally omitted for zero churn. Never represent these estimates as verified income.
