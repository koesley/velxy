"""Read-only, founder-only V60 unit-economics scenario console.

The HTTP route enforces admin authorization. Inputs are ephemeral query parameters:
no database writes, no actual billing data, no customer identifiers.
"""
from html import escape
from urllib.parse import urlencode
from revenue_dominion_v60 import SaaSScenario, analyze

FIELDS = (
    ("active_customers", "Assumed active paying customers", "0"),
    ("monthly_price", "Assumed monthly price ($)", "49"),
    ("variable_cost_per_customer", "Assumed monthly cost per customer ($)", "5"),
    ("monthly_fixed_cost", "Assumed fixed monthly costs ($)", "100"),
    ("monthly_churn_rate", "Assumed monthly churn fraction (0–1)", "0.05"),
    ("acquisition_cost_per_customer", "Assumed cost to acquire a customer ($)", "25"),
    ("new_customers_per_month", "Assumed new customers this month", "0"),
)
KEYS = frozenset(name for name, _, _ in FIELDS)


def _integer(value, name):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or len(value) > 8:
        raise ValueError(name + " must be a nonnegative whole number (at most 8 digits)")
    return int(value)


def evaluate(values):
    """Reject missing, repeated, oversized or unknown fields; never guess actual revenue."""
    if not isinstance(values, dict) or set(values) != KEYS:
        raise ValueError("All seven scenario fields are required")
    clean = {}
    for key in KEYS:
        raw = values[key]
        if not isinstance(raw, str) or len(raw) > 40 or not raw.strip():
            raise ValueError("Invalid or oversized input: " + key)
        clean[key] = raw.strip()
    result = analyze(SaaSScenario(
        active_customers=_integer(clean["active_customers"], "active_customers"),
        monthly_price=clean["monthly_price"],
        variable_cost_per_customer=clean["variable_cost_per_customer"],
        monthly_fixed_cost=clean["monthly_fixed_cost"],
        monthly_churn_rate=clean["monthly_churn_rate"],
        acquisition_cost_per_customer=clean["acquisition_cost_per_customer"],
        new_customers_per_month=_integer(clean["new_customers_per_month"], "new_customers_per_month"),
    ))
    return result


def render(params):
    """Render accessible GET form and results. Invalid values never enter HTML unescaped."""
    supplied = bool(params)
    values = {name: default for name, _, default in FIELDS}
    error = ""
    result = None
    if supplied:
        try:
            if set(params) != KEYS or any(len(v) != 1 for v in params.values()):
                raise ValueError("Provide each of the seven fields exactly once")
            values = {name: params[name][0] for name in KEYS}
            result = evaluate(values)
        except (ValueError, ArithmeticError, OverflowError) as exc:
            error = str(exc)
    fields = "".join(
        '<label style="display:block;margin:0.7rem 0">' + escape(label) +
        '<input style="display:block;max-width:24rem" name="' + escape(name) +
        '" value="' + escape(str(values[name])[:40]) + '" required inputmode="decimal"></label>'
        for name, label, _ in FIELDS
    )
    body = ('<section class="panel"><h2>Revenue Dominion — Scenario Console</h2>'
            '<p>Founder-only planning. All values are hypothetical assumptions, '
            'not verified subscriptions, payments, profits, or forecasts. '
            'No values are saved. Avoid entering customer information.</p>'
            '<form method="get" action="/founder-economics">' + fields +
            '<button type="submit">Calculate scenario</button></form>')
    if error:
        body += '<p role="alert">Invalid scenario: ' + escape(error) + '</p>'
    if result:
        labels = (
            ("monthly_recurring_revenue", "Assumed monthly recurring revenue ($)"),
            ("monthly_contribution_before_fixed_and_acquisition", "Contribution before fixed and acquisition ($)"),
            ("monthly_acquisition_spend", "Assumed acquisition spend ($)"),
            ("monthly_operating_contribution", "Operating contribution before taxes ($)"),
            ("contribution_per_customer", "Contribution per customer ($)"),
            ("monthly_contribution_margin_pct", "Contribution margin (%)"),
            ("break_even_active_customers_excluding_acquisition", "Break-even active customers, fixed costs only"),
            ("break_even_active_customers_including_assumed_acquisition", "Break-even active customers including assumed acquisition"),
            ("simplified_contribution_ltv", "Simplified contribution LTV ($)"),
            ("simplified_cac_payback_months", "Simplified CAC payback (months)"),
        )
        rows = "".join('<tr><th scope="row">' + escape(label) + '</th><td>' +
                       escape("Not defined" if result[key] is None else str(result[key])) +
                       '</td></tr>' for key, label in labels)
        body += ('<h3>Calculated scenario</h3><table><tbody>' + rows + '</tbody></table>'
                 '<h3>Assumptions and limitations</h3><ul>' +
                 "".join('<li>' + escape(note) + '</li>' for note in result["assumptions"]) +
                 '</ul>')
    body += ('<p>V61 observed saved-report activation cohorts, early/late drop-off, and 30-day repeat-use by first-save timing and mature signup-week trends '
             'are available on the founder stats page. These are product milestones, '
             'not verified payment, retention, or business value. Anonymous site events '
             'alone cannot establish individual customer journeys.</p>'
             '<p><a href="/founder-stats">Founder event counts</a> · '
             '<a href="/">Dashboard</a></p></section>')
    return body
