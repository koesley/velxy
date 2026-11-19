"""Deterministic, workspace-scoped daily action brief for business operators."""
import html
import urllib.parse
from datetime import date, timedelta
import business_os_v59 as bos
import revenue_conversion_v24 as conversion
import revenue_followups_v23 as followups


def build(c, uid, wid):
    """Read existing records; never send messages or execute tasks."""
    bos.core.access(c, uid, wid)
    metrics = conversion.summarize(c, uid, wid)
    today = date.today().isoformat()
    overdue = c.execute(
        "SELECT COUNT(*) FROM vx_followup23 WHERE workspace_id=? "
        "AND status='planned' AND due_date<?", (wid, today)
    ).fetchone()[0]
    due_today = c.execute(
        "SELECT COUNT(*) FROM vx_followup23 WHERE workspace_id=? "
        "AND status='planned' AND due_date=?", (wid, today)
    ).fetchone()[0]
    pending = c.execute(
        "SELECT COUNT(*) FROM bos59_actions WHERE workspace_id=? "
        "AND decision='pending'", (wid,)
    ).fetchone()[0]
    untouched = c.execute(
        "SELECT COUNT(*) FROM bos59_leads WHERE workspace_id=? AND status='new'",
        (wid,)
    ).fetchone()[0]
    # A planned next step is distinct from a completed historical activity.
    unplanned = c.execute(
        """SELECT COUNT(*) FROM bos59_leads l
           WHERE l.workspace_id=? AND l.status IN ('new','contacted')
             AND NOT EXISTS (
               SELECT 1 FROM vx_followup23 f
               WHERE f.workspace_id=l.workspace_id AND f.lead_id=l.id
                 AND f.status='planned')""", (wid,)
    ).fetchone()[0]
    upcoming = c.execute(
        "SELECT COUNT(*) FROM vx_followup23 WHERE workspace_id=? "
        "AND status='planned' AND due_date>? AND due_date<=?",
        (wid, today, (date.today()+timedelta(days=7)).isoformat())
    ).fetchone()[0]
    actions = []
    if overdue:
        actions.append({"priority":1,"title":"Review overdue follow-ups",
                        "detail":str(overdue)+" scheduled follow-up(s) are past due.",
                        "path":"/revenue-followups"})
    if due_today:
        actions.append({"priority":2,"title":"Review today's follow-ups",
                        "detail":str(due_today)+" follow-up(s) are scheduled for today.",
                        "path":"/revenue-followups"})
    if unplanned:
        actions.append({"priority":3,"title":"Plan next steps for open leads",
                        "detail":str(unplanned)+" open lead(s) have no planned follow-up. "
                                 "Review contact eligibility before any outreach.",
                        "path":"/revenue-followups"})
    if upcoming:
        actions.append({"priority":4,"title":"Prepare for next week's follow-ups",
                        "detail":str(upcoming)+" follow-up(s) are due in the next seven days.",
                        "path":"/revenue-followups"})
    if pending:
        actions.append({"priority":5,"title":"Review pending outreach drafts",
                        "detail":str(pending)+" internal draft(s) await approval. Approval does not send messages.",
                        "path":"/business-os-v59"})
    if untouched:
        actions.append({"priority":6,"title":"Qualify new leads",
                        "detail":str(untouched)+" lead(s) are marked new.",
                        "path":"/revenue-priority/live"})
    if not actions:
        actions.append({"priority":7,"title":"Review pipeline health",
                        "detail":"No overdue, due-today, upcoming, uncovered-lead, pending-draft, or new-lead actions detected.",
                        "path":"/revenue-conversion"})
    actions.sort(key=lambda item:item['priority'])
    return {"date":today,"actions":actions,"metrics":metrics}


def render(c,uid,wid):
    data=build(c,uid,wid)
    e=lambda x:html.escape(str(x),quote=True)
    w=urllib.parse.quote(wid,safe="")
    out=['<section class="panel"><h1>Daily Revenue Action Brief</h1>',
         '<p>As of '+e(data["date"])+'. Rules-based recommendations using manually entered '
         'business data. No revenue guarantees, automatic outreach, or autonomous execution.</p>',
         '<p><a href="/revenue-command?w='+w+'">Back to Revenue Command Center</a></p></section>']
    for item in data["actions"]:
        out.append('<section class="panel"><h2>'+e(item["title"])+'</h2><p>'+
                   e(item["detail"])+'</p><a href="'+item["path"]+'?w='+w+
                   '">Review in workspace</a></section>')
    return ''.join(out)
