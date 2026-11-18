"""VELXTRIA unified, workspace-scoped revenue command center (read-only)."""
import html
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from revenue_action_evidence import RevenueAction, rank_actions
import urllib.parse
import revenue_conversion_v24 as conversion
import revenue_priority_live as priorities
import revenue_followups_v23 as followups
import business_os_v59 as bos


def snapshot(c, uid, wid):
    """One authorized workspace; combine existing lead and follow-up read models."""
    bos.core.access(c, uid, wid)
    metrics = conversion.summarize(c, uid, wid)
    ranked = priorities.live_rankings(c, uid, wid, limit=5)
    evidence_actions = []
    for item in ranked:
        try:
            cents = int((Decimal(item['estimated_value']) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            if cents > 0:
                evidence_actions.append(RevenueAction(str(item['identifier']), 'lead_followup', cents, Decimal(str(item['confidence']))))
        except (ValueError, TypeError, InvalidOperation, KeyError):
            continue
    action_proposals = rank_actions(evidence_actions, limit=5)
    pending = c.execute(
        "SELECT COUNT(*) FROM bos59_actions WHERE workspace_id=? AND decision='pending'",
        (wid,)
    ).fetchone()[0]
    due = c.execute(
        "SELECT f.due_date,l.name,f.status FROM vx_followup23 f "
        "JOIN bos59_leads l ON l.workspace_id=f.workspace_id AND l.id=f.lead_id "
        "WHERE f.workspace_id=? AND f.status='planned' "
        "ORDER BY f.due_date,f.created LIMIT 8", (wid,)
    ).fetchall()
    return {"metrics": metrics, "ranked": ranked, "pending_approvals": int(pending),
            "next_followups": due, "action_proposals": action_proposals}


def render(c, uid, wid):
    data = snapshot(c, uid, wid)
    m = data["metrics"]
    e = lambda value: html.escape(str(value), quote=True)
    w = urllib.parse.quote(wid, safe="")
    def link(path, label):
        return '<a href="' + path + '?w=' + w + '">' + e(label) + '</a>'
    def tile(label, value):
        return '<article class="panel"><h3>' + e(label) + '</h3><strong>' + e(value) + '</strong></article>'
    rate = "N/A" if m["closed_win_rate"] is None else str(m["closed_win_rate"]) + "%"
    out = [
        '<section class="panel"><h1>Revenue Command Center</h1>',
        '<p>One view of your existing business pipeline, follow-up schedule, review queue, '
        'and conversion metrics. Values are manually recorded estimates, not verified '
        'revenue or guaranteed outcomes. No outbound actions occur here.</p>',
        '<p>' + link("/business-os-v59", "Manage leads") + ' · ' +
        link("/revenue-followups", "Follow-up tracker") + ' · ' +
        link("/revenue-conversion", "Conversion dashboard") + '</p></section>',
        '<div class="grid">',
        tile("Open leads", m["open_leads"]),
        tile("Potential open pipeline", "$" + format(m["potential_open_value"], ",.2f")),
        tile("Closed-lead win rate", rate),
        tile("Pending message approvals", data["pending_approvals"]),
        tile("Overdue follow-ups", m["overdue_followups"]),
        '</div>',
        '<section class="panel"><h2>Highest-priority open leads</h2>',
    ]
    if not data["ranked"]:
        out.append('<p>No eligible open leads with positive manually entered values.</p>')
    for item in data["ranked"]:
        out.append('<article><strong>' + e(item["title"]) + '</strong> · Score ' +
                   e(item["priority_score"]) + ' · Potential $' +
                   e(item["estimated_value"]) + '<p>' + e(item["evidence"]) +
                   '</p></article>')
    out.append('<p>' + link("/revenue-priority/live", "Review ranked leads and create approval drafts") +
               '</p></section><section class="panel"><h2>Upcoming internal follow-ups</h2>')
    if not data["next_followups"]:
        out.append('<p>No planned follow-ups.</p>')
    else:
        out.append('<table><tr><th>Due</th><th>Lead</th></tr>')
        for due, name, _ in data["next_followups"]:
            out.append('<tr><td>' + e(due) + '</td><td>' + e(name) + '</td></tr>')
        out.append('</table>')
    out.append('<p>' + link("/revenue-followups", "Schedule or record follow-up outcomes") +
               '</p></section>')
    out.append('<section class="panel"><h2>Evidence-ranked action proposals</h2><p>Heuristic ranking of existing open leads. Values are potential, not collected revenue. Nothing is sent or executed.</p>')
    if not data['action_proposals']:
        out.append('<p>No eligible proposals.</p>')
    for action in data['action_proposals']:
        out.append('<article><strong>Review lead ' + e(action['source_id']) + '</strong> · Priority ' + e(action['priority_score']) + ' · Potential 
 + e(format(Decimal(action['potential_cents']) / 100, ',.2f')) + '</article>')
    out.append('</section>')
    return ''.join(out)
