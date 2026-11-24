"""Read-only opportunity ranking from authenticated Business OS lead records."""
import html
import math
import time
from decimal import Decimal, InvalidOperation, localcontext
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
            timestamp = int(updated)
            if timestamp > current or timestamp < 0:
                continue
            days = (current - timestamp) // 86400
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
    if row[0] == "new":
        guidance = "Confirm the lead's stated need and contact permission; prepare a short discovery question and a relevant next step."
    else:
        guidance = "Review prior contact and any reply; identify unresolved questions, confirm contact permission, and propose a useful next step without repeating outreach."
    message = "Internal draft: " + guidance + " Submit for approval. Do not send automatically."
    return business_os_v59.propose(c,uid,wid,lid,message)


def render(c, uid, workspace_id, csrf=''):
    results = live_rankings(c, uid, workspace_id)
    esc = lambda value: html.escape(str(value), quote=True)
    out = ['<section class="panel"><h1>Live Pipeline Priorities</h1>',
           '<p>Read-only ranking of up to 300 oldest-updated open leads from your authorized Business OS workspace. Only the top 20 eligible results are displayed; newer leads may not have been evaluated. '
           'No contact information is shown. Values and confidence are heuristic, not verified revenue or '
           'conversion probabilities. No messages are sent and no actions are performed.</p>',
           '<p><a href="/revenue-priority">Manual comparison workbench</a></p></section>']
    if results:
        amounts = [Decimal(item['estimated_value']) for item in results]
        if all(a.is_finite() and 0 <= a <= Decimal('1000000000000') for a in amounts):
            with localcontext() as ctx:
                ctx.prec = 40
                total = format(sum(amounts, Decimal(0)), ',.2f')
            out.append('<section class="panel"><h2>Displayed estimated pipeline value</h2><p>' + chr(36) + esc(total) + ' (unweighted estimates; not collected revenue)</p></section>')
        else:
            out.append('<section class="panel"><p>Estimated total unavailable: a displayed value exceeds the supported range.</p></section>')
        # Count displayed candidates only; never imply full pipeline coverage.
        out.append('<section class="panel"><h2>Opportunity overview</h2><p>' +
                   esc(len(results)) + ' ranked opportunities displayed. '
                   'Start with the highest priority and verify the underlying value before acting.</p>' +
                   '<p>Lead values are estimates, not collected revenue. '
                   'Review drafts require approval before any outreach.</p></section>')
    if not results:
        out.append('<section class="panel"><p>No eligible positive-value leads in the evaluated batch.</p></section>')
    for item in results:
        next_step = ("Review prior replies and resolve outstanding questions."
                     if item["title"] == "Review contacted lead" else
                     "Confirm the customer's need and permission before preparing outreach.")
        out.append('<section class="panel"><p><strong>Suggested next step:</strong> ' +
                   esc(next_step) + '</p></section>')
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
