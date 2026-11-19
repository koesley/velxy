"""VELXTRIA unified, workspace-scoped revenue command center (read-only)."""
import html
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
    hygiene = c.execute("""SELECT
        COUNT(*) AS open_count,
        COALESCE(SUM(CASE WHEN TRIM(contact)='' THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN TRIM(source)='' THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN TRIM(name)='' THEN 1 ELSE 0 END),0)
        FROM bos59_leads WHERE workspace_id=? AND status IN ('new','contacted')""",
        (wid,)).fetchone()
    incomplete = c.execute("""SELECT id,name,
        CASE WHEN TRIM(contact)='' THEN 1 ELSE 0 END AS missing_contact,
        CASE WHEN TRIM(source)='' THEN 1 ELSE 0 END AS missing_source
        FROM bos59_leads WHERE workspace_id=? AND status IN ('new','contacted')
          AND (TRIM(contact)='' OR TRIM(source)='')
        ORDER BY updated ASC,id ASC LIMIT 10""",(wid,)).fetchall()
    return {"contact_readiness": {"open":int(hygiene[0]),"missing_contact":int(hygiene[1]),
            "missing_source":int(hygiene[2]),"missing_name":int(hygiene[3]),
            "examples":incomplete}, "metrics": metrics, "ranked": ranked, "pending_approvals": int(pending),
            "next_followups": due}


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
        '<section class="panel"><h2>Lead data readiness</h2>',
        '<p>Open leads missing contact details: '+e(data["contact_readiness"]["missing_contact"])+
        ' · Missing acquisition source: '+e(data["contact_readiness"]["missing_source"])+
        ' · Missing name: '+e(data["contact_readiness"]["missing_name"])+
        ' · Total open leads: '+e(data["contact_readiness"]["open"])+'.</p>',
        '<p>These are record-completeness checks, not proof that contact is valid or outreach is permitted. '
        'Verify consent and suppression status before any customer communication.</p>',
        '<p>'+link("/business-os-v59","Review and correct lead records")+'</p>',
    ],
        '<section class="panel"><h2>Highest-priority open leads</h2>',
    ]
    if data["contact_readiness"]["examples"]:
        out.append('<p>Oldest incomplete records (up to 10):</p><ul>')
        for _,name,missing_contact,missing_source in data["contact_readiness"]["examples"]:
            reasons = []
            if missing_contact: reasons.append("missing contact")
            if missing_source: reasons.append("missing source")
            out.append('<li>'+e(name or "Unnamed lead")+' — '+e(", ".join(reasons))+'</li>')
        out.append('</ul>')
    out.append('</section>')
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
    return ''.join(out)
