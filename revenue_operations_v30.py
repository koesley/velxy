"""Workspace-scoped revenue task bottleneck and execution intelligence."""
import html
import urllib.parse
from datetime import date
import time
import business_os_v59 as bos
import revenue_execution_v29 as execution

def analyze(c,uid,wid,now=None):
    bos.core.access(c,uid,wid)
    execution.setup(c)
    current=int(time.time()) if now is None else int(now)
    today=date.fromtimestamp(current).isoformat()
    rows=c.execute(
        "SELECT status,due_date,updated,created,owner_id FROM vx_revenue_tasks29 "
        "WHERE workspace_id=?", (wid,)
    ).fetchall()
    counts={s:0 for s in execution.STATES}
    overdue=stalled=blocked=completed=0
    owners={}
    for status,due,updated,created,owner in rows:
        if status not in counts:
            continue
        counts[status]+=1
        owners[owner]=owners.get(owner,0)+1
        if status=="done":
            completed+=1
        if status=="blocked":
            blocked+=1
        if status in ("todo","in_progress","blocked") and due<today:
            overdue+=1
        if status in ("todo","in_progress") and current-int(updated)>=7*86400:
            stalled+=1
    total=sum(counts.values())
    active=total-completed
    return {"counts":counts,"total":total,"active":active,"overdue":overdue,
            "stalled":stalled,"blocked":blocked,"completed":completed,
            "completion_pct":round(completed/total*100,1) if total else None,
            "owner_count":len(owners),"today":today}

def render(c,uid,wid):
    data=analyze(c,uid,wid)
    esc=lambda v:html.escape(str(v),quote=True)
    w=urllib.parse.quote(wid,safe="")
    def tile(label,value):
        return '<article class="panel"><h3>'+esc(label)+'</h3><strong>'+esc(value)+'</strong></article>'
    rate="N/A" if data["completion_pct"] is None else str(data["completion_pct"])+"%"
    out=['<section class="panel"><h1>Revenue Operations Intelligence</h1>',
         '<p>Operational task metrics for this workspace as of '+esc(data["today"])+
         '. Stalled means an active task has not been updated for 7 days. '
         'Overdue means an unfinished task is past its due date. '
         'Completion percentage is the share of all recorded tasks marked done, '
         'not a sales conversion rate or verified revenue result.</p>',
         '<p><a href="/revenue-execution?w='+w+'">Manage execution tasks</a></p></section>',
         '<div class="grid">',
         tile("Recorded tasks",data["total"]),tile("Active tasks",data["active"]),
         tile("Completed",data["completed"]),tile("Completion share",rate),
         tile("Overdue",data["overdue"]),tile("Stalled (7+ days)",data["stalled"]),
         tile("Blocked",data["blocked"]),tile("Assigned owners",data["owner_count"]),
         '</div><section class="panel"><h2>Operational recommendations</h2>']
    recommendations=[]
    if data["overdue"]:
        recommendations.append("Review overdue tasks and update due dates or priorities.")
    if data["stalled"]:
        recommendations.append("Check stalled task owners and identify next steps.")
    if data["blocked"]:
        recommendations.append("Identify dependencies preventing blocked work.")
    if not recommendations:
        recommendations.append("No overdue, stalled, or blocked tasks were detected.")
    out.extend('<p>'+esc(item)+'</p>' for item in recommendations)
    out.append('<p>Recommendations are deterministic; no task changes or external '
               'messages are performed automatically.</p></section>')
    return ''.join(out)
