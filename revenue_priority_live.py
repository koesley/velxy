"""Read-only opportunity ranking from authenticated Business OS lead records."""
import html
import math
import time
from decimal import Decimal
import business_os_v59
from revenue_priority import RevenueOpportunity, rank_opportunities


def live_rankings(c, uid, workspace_id, limit=20):
    """Scope all records to an authorized workspace; never expose lead contacts."""
    business_os_v59.core.access(c, uid, workspace_id)
    business_os_v59.init(c)
    rows = c.execute(
        "SELECT id,value,status,updated FROM bos59_leads "
        "WHERE workspace_id=? AND status IN ('new','contacted') "
        "ORDER BY updated ASC,id ASC LIMIT 300", (workspace_id,)
    ).fetchall()
    current = int(time.time())
    candidates = []
    for identifier, value, status, updated in rows:
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount <= 0:
                continue
            days = max(0, (current - int(updated)) // 86400)
            # Explicit heuristics, not learned conversion probabilities.
            confidence = 0.35 if status == "new" else 0.5
            urgency = min(1.0, 0.25 + days / 30)
            effort = 1.0 if status == "new" else 0.5
            candidates.append(RevenueOpportunity(
                identifier=str(identifier), title="Review " + status + " lead",
                estimated_value=amount, confidence=confidence,
                urgency=urgency, effort_hours=effort,
                evidence=f"Business OS lead marked {status}; last updated {days} days ago. "
                         "Value is manually entered, not verified revenue."))
        except (ValueError, TypeError, OverflowError):
            continue
    return rank_opportunities(candidates)[:max(1, min(int(limit), 50))]


def render(c, uid, workspace_id):
    results = live_rankings(c, uid, workspace_id)
    esc = lambda value: html.escape(str(value), quote=True)
    out = ['<section class="panel"><h1>Live Pipeline Priorities</h1>',
           '<p>Read-only ranking of up to 300 recent open leads from your authorized Business OS workspace. '
           'No contact information is shown. Values and confidence are heuristic, not verified revenue or '
           'conversion probabilities. No messages are sent and no actions are performed.</p>',
           '<p><a href="/revenue-priority">Manual comparison workbench</a></p></section>']
    if not results:
        out.append('<section class="panel"><p>No eligible open leads with positive values yet.</p></section>')
    for item in results:
        out.append('<section class="panel"><h2>' + esc(item["title"]) +
                   ' · Priority ' + esc(item["priority_score"]) + '</h2><p>Potential value: $' +
                   esc(item["estimated_value"]) + ' · Heuristic confidence: ' +
                   esc(item["confidence"]) + ' · Estimated effort: ' +
                   esc(item["effort_hours"]) + ' hours</p><p>' +
                   esc(item["evidence"]) + '</p><p>' + esc(item["explanation"]) + '</p></section>')
    return ''.join(out)
