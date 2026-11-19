"""Read-only conversion dashboard based on manually entered Business OS records."""
import html
from datetime import date
import business_os_v59 as bos
import revenue_followups_v23 as followups

def summarize(c, uid, wid):
    bos.core.access(c, uid, wid)
    bos.init(c)
    followups.setup(c)
    lead_rows = c.execute(
        "SELECT status, COUNT(*), COALESCE(SUM(value),0) FROM bos59_leads "
        "WHERE workspace_id=? GROUP BY status", (wid,)
    ).fetchall()
    leads = {status: {"count": int(count), "value": float(value)}
             for status,count,value in lead_rows}
    follow_rows = c.execute(
        "SELECT status, COUNT(*) FROM vx_followup23 WHERE workspace_id=? GROUP BY status",
        (wid,)
    ).fetchall()
    follow = {status:int(count) for status,count in follow_rows}
    overdue = c.execute(
        "SELECT COUNT(*) FROM vx_followup23 WHERE workspace_id=? AND status='planned' AND due_date<?",
        (wid,date.today().isoformat())
    ).fetchone()[0]
    # Count leads once per cohort, even if a lead has multiple follow-up records.
    # These are associations in manually maintained data, not attribution of sales.
    cohort_rows = c.execute(
        "SELECT l.status, "
        "CASE WHEN EXISTS (SELECT 1 FROM vx_followup23 f "
        "WHERE f.workspace_id=l.workspace_id AND f.lead_id=l.id) "
        "THEN 'with_followup' ELSE 'without_followup' END, COUNT(*) "
        "FROM bos59_leads l WHERE l.workspace_id=? "
        "GROUP BY l.status, CASE WHEN EXISTS (SELECT 1 FROM vx_followup23 f "
        "WHERE f.workspace_id=l.workspace_id AND f.lead_id=l.id) "
        "THEN 'with_followup' ELSE 'without_followup' END", (wid,)
    ).fetchall()
    cohorts = {"with_followup": {"open": 0, "won": 0, "lost": 0},
               "without_followup": {"open": 0, "won": 0, "lost": 0}}
    for stage, cohort, count in cohort_rows:
        category = "open" if stage in ("new", "contacted") else stage
        if category in ("open", "won", "lost"):
            cohorts[cohort][category] += int(count)
    # Only completed follow-ups are included; these are not verified replies.
    outcome_rows = c.execute(
        "SELECT f.status, COUNT(*) FROM vx_followup23 f "
        "JOIN bos59_leads l ON l.workspace_id=f.workspace_id AND l.id=f.lead_id "
        "WHERE f.workspace_id=? AND f.status<>'planned' "
        "GROUP BY f.status", (wid,)
    ).fetchall()
    recorded_outcomes = {state: int(count) for state, count in outcome_rows}
    total = sum(item["count"] for item in leads.values())
    won = leads.get("won",{}).get("count",0)
    closed = won + leads.get("lost",{}).get("count",0)
    return {
        "leads": leads, "followups": follow, "total_leads": total,
        "followup_cohorts": cohorts, "recorded_outcomes": recorded_outcomes,
        "open_leads": sum(leads.get(k,{}).get("count",0) for k in ("new","contacted")),
        "won_leads": won, "closed_leads": closed,
        "closed_win_rate": round(100*won/closed,1) if closed else None,
        "potential_open_value": round(sum(leads.get(k,{}).get("value",0) for k in ("new","contacted")),2),
        "won_marked_value": round(leads.get("won",{}).get("value",0),2),
        "overdue_followups": int(overdue),
    }

def render(c,uid,wid):
    data=summarize(c,uid,wid)
    esc=lambda value:html.escape(str(value),quote=True)
    def metric(label,value):
        return '<article class="panel"><h3>'+esc(label)+'</h3><p><strong>'+esc(value)+'</strong></p></article>'
    rate="N/A — no closed leads" if data["closed_win_rate"] is None else str(data["closed_win_rate"])+"%"
    out=['<section class="panel"><h1>Revenue Conversion Dashboard</h1>',
         '<p>Workspace-wide counts from manually entered leads and follow-up records. '
         'A lead marked won is not proof of payment or realized revenue. '
         'This dashboard does not send messages or make purchases.</p></section>',
         '<div class="grid">',metric("All leads",data["total_leads"]),
         metric("Open leads",data["open_leads"]),metric("Won-marked leads",data["won_leads"]),
         metric("Closed-lead win rate",rate),
         metric("Open pipeline potential","$"+format(data["potential_open_value"],",.2f")),
         metric("Won-marked potential","$"+format(data["won_marked_value"],",.2f")),
         metric("Overdue follow-ups",data["overdue_followups"]),'</div>',
         '<section class="panel"><h2>Follow-up outcomes</h2><table><tr><th>Status</th><th>Count</th></tr>']
    for state in followups.STATES:
        out.append('<tr><td>'+esc(state.title())+'</td><td>'+
                   esc(data["followups"].get(state,0))+'</td></tr>')
    out.append('<section class="panel"><h2>Lead outcomes by follow-up history</h2>'
               '<p>Each lead appears once. Having a follow-up does not establish '
               'that the follow-up caused a win. Stages and follow-ups are '
               'manually entered and may be incomplete.</p>'
               '<table><tr><th>Follow-up history</th><th>Open</th><th>Won-marked</th>'
               '<th>Lost-marked</th><th>Closed win share</th></tr>')
    for key,label in (("with_followup","At least one follow-up"),
                      ("without_followup","No recorded follow-up")):
        cohort=data["followup_cohorts"][key]
        closed=cohort["won"]+cohort["lost"]
        share=(str(round(100*cohort["won"]/closed,1))+"%") if closed else "N/A"
        out.append('<tr><td>'+esc(label)+'</td><td>'+esc(cohort["open"])+
                   '</td><td>'+esc(cohort["won"])+ '</td><td>'+esc(cohort["lost"])+
                   '</td><td>'+esc(share)+'</td></tr>')
    out.append('</table><p>Closed win share excludes open leads. '
               'Records with other stages are excluded from this breakdown.</p></section>')
    out.append('</table><p>Follow-up outcomes and lead stages are separate manual records; '
               'they are not automatically reconciled.</p>'
               '<p><a href="/revenue-followups?w='+esc(wid)+'">Manage follow-ups</a> · '
               '<a href="/revenue-priority/live?w='+esc(wid)+'">View ranked leads</a></p></section>')
    return ''.join(out)
