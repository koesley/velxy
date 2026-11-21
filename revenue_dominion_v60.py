"""VELXTRIA Revenue Dominion: auditable SaaS unit-economics scenarios.

Pure calculation only. No payment processing, customer outreach, forecasts,
external writes, or claims that estimated revenue has been collected.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid monetary input") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Money must be finite and nonnegative")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def ratio(value, name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(name + " must be numeric") from exc
    if not number.is_finite() or not Decimal("0") <= number <= Decimal("1"):
        raise ValueError(name + " must be between 0 and 1")
    return number


@dataclass(frozen=True)
class SaaSScenario:
    active_customers: int
    monthly_price: object
    variable_cost_per_customer: object
    monthly_fixed_cost: object
    monthly_churn_rate: object
    acquisition_cost_per_customer: object
    new_customers_per_month: int = 0


def analyze(scenario: SaaSScenario) -> dict:
    """Compute static monthly unit economics, not a forward-looking forecast.

    CAC is charged for each assumed new customer in this scenario.
    LTV uses constant churn and constant contribution margin; no discounting.
    """
    for name in ("active_customers", "new_customers_per_month"):
        value = getattr(scenario, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(name + " must be a nonnegative integer")
    price = money(scenario.monthly_price)
    variable = money(scenario.variable_cost_per_customer)
    fixed = money(scenario.monthly_fixed_cost)
    cac = money(scenario.acquisition_cost_per_customer)
    churn = ratio(scenario.monthly_churn_rate, "monthly_churn_rate")
    count = scenario.active_customers
    new = scenario.new_customers_per_month
    margin = price - variable
    mrr = price * count
    gross_contribution = margin * count
    acquisition_spend = cac * new
    operating_contribution = gross_contribution - fixed - acquisition_spend
    break_even = None
    if margin > 0:
        break_even = int((fixed / margin).to_integral_value(rounding="ROUND_CEILING"))
    # With zero churn, lifetime is undefined; do not imply infinite revenue.
    ltv = None if churn == 0 or margin <= 0 else (margin / churn).quantize(CENT)
    payback = None if margin <= 0 else (cac / margin).quantize(CENT)
    # Acquisition spend belongs in the break-even calculation when the
    # scenario explicitly assumes new customers and their acquisition cost.
    break_even_with_acquisition = None
    if margin > 0:
        break_even_with_acquisition = int(((fixed + acquisition_spend) / margin).to_integral_value(rounding="ROUND_CEILING"))
    return {
        "active_customers": count,
        "new_customers_per_month": new,
        "monthly_recurring_revenue": str(mrr),
        "monthly_contribution_before_fixed_and_acquisition": str(gross_contribution),
        "monthly_acquisition_spend": str(acquisition_spend),
        "monthly_operating_contribution": str(operating_contribution),
        "contribution_per_customer": str(margin),
        "break_even_active_customers_excluding_acquisition": break_even,
        "break_even_active_customers_including_assumed_acquisition": break_even_with_acquisition,
        "monthly_contribution_margin_pct": None if price == 0 else str((margin / price * 100).quantize(CENT)),
        "simplified_contribution_ltv": None if ltv is None else str(ltv),
        "simplified_cac_payback_months": None if payback is None else str(payback),
        "ltv_to_cac": None if ltv is None or cac == 0 else str((ltv / cac).quantize(CENT)),
        "assumptions": [
            "Inputs are user-supplied assumptions, not verified transactions.",
            "No taxes, refunds, payment fees beyond entered costs, expansion, or discounting.",
            "LTV assumes constant monthly churn and contribution; zero churn has no finite LTV.",
            "Two break-even thresholds show fixed costs alone versus fixed plus assumed acquisition spend.",
            "Negative contribution margin percentages mean the assumed variable cost exceeds price.",
            "No guarantee of future revenue, profit, or customer retention.",
        ],
    }


def compare(scenarios):
    """Compare named scenarios; reject duplicate labels and empty comparisons."""
    result = {}
    for name, scenario in scenarios.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Scenario names must be nonempty")
        result[name] = analyze(scenario)
    if not result:
        raise ValueError("At least one scenario is required")
    return result
