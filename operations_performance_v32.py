"""Read-only workspace recovery performance and recurring bottleneck analytics."""
import html
import urllib.parse
from collections import Counter
from datetime import date
import business_os_v59 as bos
import operations_recovery_v31 as recovery

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid)
    recovery.setup(c)
    rows=c.execute("""SELECT p.task_id,p.diagnosis,p.status,p.created,p.updated,p.due_date
        FROM vx_recovery31 p WHERE p.workspace_id=?""",(wid,)).fetchall()
    total=len(rows)
    resolved=[r for r in rows if r[2]=="resolved"]
    open_rows=[r for r in rows if r[2]=="open"]
    today=date.today().isoformat()
    overdue=sum(r[5]<today for r in open_rows)
    # A recurring bottleneck is a task that has needed multiple recovery plans.
    repeated=Counter(r[0] for r in rows)
    recurring=sum(n>1 for n in repeated.values())
    duration=[max(0,r[4]-r[3]) for r in resolved]
    avg_days=round(sum(duration)/len(duration)/86400,1) if duration else None
    resolved_on_time=sum(date.fromtimestamp(r[4]).isoformat()<=r[5] for r in resolved)
    return {"total":total,"resolved":len(resolved),"open":len(open_rows),
            "overdue_open":overdue,"recurring_tasks":recurring,
            "resolution_rate":round(len(resolved)/total*100,1) if total else None,
            "average_resolution_days":avg_days,
            "resolved_on_time":resolved_on_time,
            "on_time_rate":round(resolved_on_time/len(resolved)*100,1) if resolved else None}

def render(c,uid,wid):
    data=analyze(c,uid,wid)
    e=lambda v:html.escape(str(v),quote=True)
    w=urllib.parse.quote(wid,safe="")
    def tile(label,value):
        return '<article class="panel"><h3>'+e(label)+'</h3><strong>'+e(value)+'</strong></article>'
    pct=lambda value:"N/A" if value is None else str(value)+"%"
    days="N/A" if data["average_resolution_days"] is None else str(data["average_resolution_days"])+" days"
    out=['<section class="panel"><h1>Operations Performance Engine</h1>',
         '<p>Workspace-wide analysis of manually managed recovery plans. '
         'Resolution means a plan was marked resolved; it does not independently '
         'verify task completion, customer outcomes, or revenue. '
         'Recurring means a task has had more than one recorded recovery plan.</p>',
         '<p><a href="/operations-recovery?w='+w+'">Manage recovery plans</a></p></section>',
         '<div class="grid">',
         tile("Recovery plans",data["total"]),tile("Open plans",data["open"]),
         tile("Resolved plans",data["resolved"]),tile("Resolution share",pct(data["resolution_rate"])),
         tile("Overdue open plans",data["overdue_open"]),tile("Recurring task bottlenecks",data["recurring_tasks"]),
         tile("Average resolution time",days),tile("Resolved by deadline",pct(data["on_time_rate"])),
         '</div><section class="panel"><h2>Improvement priorities</h2>']
    recommendations=[]
    if data["recurring_tasks"]:recommendations.append("Review tasks with repeated recovery plans to address recurring blockers.")
    if data["overdue_open"]:recommendations.append("Prioritize overdue open recovery plans and confirm next steps.")
    if data["resolved"] and data["on_time_rate"] is not None and data["on_time_rate"]<70:
        recommendations.append("Review recovery deadlines and workload estimates; fewer than 70% of resolved plans met their deadline.")
    if not recommendations:recommendations.append("No recurring or overdue recovery bottlenecks detected in recorded plans.")
    out.extend('<p>'+e(item)+'</p>' for item in recommendations)
    out.append('<p>These are deterministic suggestions. No changes are made automatically.</p></section>')
    return ''.join(out)
