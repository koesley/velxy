"""Authenticated, read-only Revenue Priority Workbench for the VELXTRIA portal."""
import html
from decimal import Decimal
from revenue_priority import RevenueOpportunity, rank_opportunities

def esc(value):
    return html.escape(str(value), quote=True)

def render(params):
    """Score up to five manually entered, non-sensitive opportunity estimates."""
    fields = ("title", "value", "confidence", "urgency", "effort", "evidence")
    submitted = params.get("calculate", [""])[0] == "1"
    errors = []
    opportunities = []
    rows = []
    for i in range(1, 6):
        data = {key: params.get(f"{key}{i}", [""])[0][:300] for key in fields}
        if submitted and any(data.values()):
            try:
                if not all(data.values()):
                    raise ValueError("Complete every field for this opportunity.")
                opportunities.append(RevenueOpportunity(
                    identifier=str(i), title=data["title"],
                    estimated_value=Decimal(data["value"]),
                    confidence=float(data["confidence"]),
                    urgency=float(data["urgency"]),
                    effort_hours=float(data["effort"]),
                    evidence=data["evidence"]))
            except (ValueError, ArithmeticError) as exc:
                errors.append(f"Opportunity {i}: {exc}")
        controls = "".join(
            f'<label>{esc(label)}<input name="{key}{i}" value="{esc(data[key])}" '
            f'{("type=number step=any min=0" if key in ("value", "effort") else "type=number step=any min=0 max=1" if key in ("confidence", "urgency") else "type=text")} '
            f'maxlength=300></label>'
            for key, label in (("title", "Opportunity"), ("value", "Estimated value ($)"),
                               ("confidence", "Confidence (0–1)"), ("urgency", "Urgency (0–1)"),
                               ("effort", "Effort (hours)"), ("evidence", "Evidence / source"))
        )
        rows.append(f'<details {"open" if i == 1 or any(data.values()) else ""}><summary>Opportunity {i}</summary><div class="grid">{controls}</div></details>')
    output = ""
    if submitted and not errors:
        try:
            ranked = rank_opportunities(opportunities)
            if not ranked:
                errors.append("Enter at least one opportunity.")
            else:
                output = '<section class="panel"><h2>Prioritized opportunities</h2><p>Relative ranking only — not a revenue forecast or automatic action.</p>'
                for item in ranked:
                    output += (f'<article class="panel"><h3>{esc(item["title"])} · Score {item["priority_score"]}</h3>'
                               f'<p>Estimated value: ${esc(item["estimated_value"])} · Confidence: {item["confidence"]} · '
                               f'Urgency: {item["urgency"]} · Effort: {item["effort_hours"]} hours</p>'
                               f'<p><strong>Evidence:</strong> {esc(item["evidence"])}</p>'
                               f'<p>{esc(item["explanation"])} No actions are executed.</p></article>')
                output += '</section>'
        except ValueError as exc:
            errors.append(str(exc))
    messages = "".join(f'<p role="alert">{esc(e)}</p>' for e in errors)
    return ('<section class="panel"><h1>Revenue Priority Workbench</h1>'
            '<p>Compare up to five potential business improvements using your own estimates. '
            'No integrations, outreach, or purchases are triggered. Use non-sensitive data only: '
            'form inputs appear in the browser URL and are not saved by this feature.</p>'
            '<p>Confidence and urgency range from 0 to 1. Leave unused opportunities blank.</p>'
            '<form method="get" action="/revenue-priority"><input type="hidden" name="calculate" value="1">'
            + "".join(rows) + '<button type="submit">Rank opportunities</button></form>'
            + messages + output + '</section>')
