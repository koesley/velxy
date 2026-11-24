"""Read-only opportunity ranking from authenticated Business OS lead records."""
import html
import math
import time
from decimal import Decimal, InvalidOperation
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
        except (InvalidOperation, ValueError, TypeError, OverflowError):
            continue
    return rank_opportunities(candidates)[:max(1, min(int(limit), 50))]


def propose_followup(c, uid, wid, lid):
    """Create internal review draft only; never send external messages."""
    business_os_v59.core.access(c,uid,wid,write=True)
    business_os_v59.init(c)
    row=c.execute("SELECT status FROM bos59_leads WHERE workspace_id=? AND id=?",(wid,lid)).fetchone()
    if not row or row[0] not in ("new","contacted"):
        raise ValueError("Lead is not eligible")
    if c.execute("SELECT 1 FROM bos59_actions WHERE workspace_id=? AND lead_id=? AND decision='pending' LIMIT 1",(wid,lid)).fetchone():
        raise ValueError("Pending review already exists")
    message="Internal draft: review this "+row[0]+" lead, verify consent, and prepare a personalized follow-up for approval. Do not send automatically."
    return business_os_v59.propose(c,uid,wid,lid,message)


def render(c, uid, workspace_id, csrf=''):
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
                   esc(item["evidence"]) + '</p><p>' + esc(item["explanation"]) + '</p>' +
                   '<form method="post" action="/revenue-priority/live">' +
                   '<input type="hidden" name="csrf" value="' + esc(csrf) + '">' +
                   '<input type="hidden" name="workspace" value="' + esc(workspace_id) + '">' +
                   '<input type="hidden" name="lead" value="' + esc(item["identifier"]) + '">' +
                   '<button>Create review draft</button></form></section>')
    return ''.join(out)
