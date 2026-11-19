"""Read-only conversion dashboard based on manually entered Business OS records."""
import html
from datetime import date, timedelta
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
    today = date.today()
    due_soon = c.execute(
        "SELECT COUNT(*) FROM vx_followup23 WHERE workspace_id=? "
        "AND status='planned' AND due_date>=? AND due_date<=?",
        (wid, today.isoformat(), (today + timedelta(days=7)).isoformat())
    ).fetchone()[0]
    total_followups = sum(follow.values())
    replied = follow.get("replied", 0)
    total = sum(item["count"] for item in leads.values())
    won = leads.get("won",{}).get("count",0)
    closed = won + leads.get("lost",{}).get("count",0)
    return {
        "leads": leads, "followups": follow, "total_leads": total,
        "open_leads": sum(leads.get(k,{}).get("count",0) for k in ("new","contacted")),
        "won_leads": won, "closed_leads": closed,
        "closed_win_rate": round(100*won/closed,1) if closed else None,
        "potential_open_value": round(sum(leads.get(k,{}).get("value",0) for k in ("new","contacted")),2),
        "won_marked_value": round(leads.get("won",{}).get("value",0),2),
        "overdue_followups": int(overdue),
        "due_next_7_days": int(due_soon),
        "replied_followups": replied,
        "reply_share": round(100 * replied / total_followups, 1) if total_followups else None,
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
         metric("Overdue follow-ups",data["overdue_followups"]),
         metric("Due in next 7 days",data["due_next_7_days"]),
         metric("Follow-ups marked replied",data["replied_followups"]),
         metric("Share marked replied",
                "N/A — no follow-ups" if data["reply_share"] is None
                else str(data["reply_share"])+"%"),'</div>',
         '<section class="panel"><h2>Follow-up outcomes</h2><table><tr><th>Status</th><th>Count</th></tr>']
    for state in followups.STATES:
        out.append('<tr><td>'+esc(state.title())+'</td><td>'+
                   esc(data["followups"].get(state,0))+'</td></tr>')
    out.append('</table><p>Reply share is the proportion of manually recorded follow-ups '
               'marked replied, not an email deliverability rate or verified conversion. '
               'Upcoming due counts include today through seven calendar days ahead. '
               'Overdue counts exclude today.</p><p>Follow-up outcomes and lead stages are separate manual records; '
               'they are not automatically reconciled.</p>'
               '<p><a href="/revenue-followups?w='+esc(wid)+'">Manage follow-ups</a> · '
               '<a href="/revenue-priority/live?w='+esc(wid)+'">View ranked leads</a></p></section>')
    return ''.join(out)
