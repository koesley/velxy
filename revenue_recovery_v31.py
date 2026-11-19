"""Internal recovery plans for blocked, overdue, and stalled revenue tasks."""
import html
import secrets
import time
import urllib.parse
from datetime import date
import business_os_v59 as bos
import revenue_execution_v29 as execution

STEPS=("identify_blocker","choose_next_action","confirm_resolution")

def setup(c):
    execution.setup(c)
    c.execute("""CREATE TABLE IF NOT EXISTS vx_recovery31 (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL,
        owner_id INTEGER NOT NULL, blocker TEXT NOT NULL, next_action TEXT NOT NULL,
        status TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_recovery31_scope ON vx_recovery31(workspace_id,task_id,status)")

def workload(c, uid, wid, now=None):
    """Workspace-wide recovery workload; no 100-row sampling bias."""
    bos.core.access(c, uid, wid)
    setup(c)
    current = int(time.time()) if now is None else int(now)
    today = date.fromtimestamp(current).isoformat()
    cutoff = current - 7 * 86400
    condition = """t.status IN ('todo','in_progress','blocked')
        AND (t.status='blocked' OR t.due_date < ? OR
             (t.status IN ('todo','in_progress') AND t.updated <= ?))"""
    base = """FROM vx_revenue_tasks29 t JOIN bos59_leads l
        ON l.workspace_id=t.workspace_id AND l.id=t.lead_id
        WHERE t.workspace_id=? AND """ + condition
    params = (wid, today, cutoff)
    total = c.execute("SELECT COUNT(*) " + base, params).fetchone()[0]
    active = c.execute("""SELECT COUNT(*) FROM vx_recovery31 r
        JOIN vx_revenue_tasks29 t ON t.id=r.task_id AND t.workspace_id=r.workspace_id
        WHERE r.workspace_id=? AND r.status='active'
        AND t.status IN ('todo','in_progress','blocked')""", (wid,)).fetchone()[0]
    rows = c.execute("""SELECT t.id,t.title,t.status,t.due_date,t.updated,
        t.owner_id,l.name, EXISTS(
          SELECT 1 FROM vx_recovery31 r
          WHERE r.workspace_id=t.workspace_id AND r.task_id=t.id AND r.status='active'
        ) """ + base + """
        ORDER BY CASE WHEN t.status='blocked' THEN 0
                      WHEN t.due_date < ? THEN 1 ELSE 2 END,
                 t.due_date ASC,t.created ASC,t.id ASC LIMIT 100""",
        params + (today,)).fetchall()
    result = []
    for identifier,title,status,due,updated,owner,lead,has_plan in rows:
        reasons = []
        if status == 'blocked': reasons.append('blocked')
        if due < today: reasons.append('overdue')
        if status in ('todo','in_progress') and int(updated) <= cutoff:
            reasons.append('stalled')
        result.append({'id':identifier,'title':title,'lead':lead,
                       'owner':owner,'reasons':reasons,'has_active_plan':bool(has_plan)})
    return {'total':total,'active_plans':active,'items':result}


def candidates(c,uid,wid,now=None):
    return workload(c,uid,wid,now=now)['items']

def create(c,uid,wid,task_id,blocker,next_action):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    blocker=str(blocker).strip()
    next_action=str(next_action).strip()
    if not blocker or len(blocker)>500 or not next_action or len(next_action)>500:
        raise ValueError("Blocker and next action must each be 1–500 characters.")
    eligible={row["id"]:row for row in candidates(c,uid,wid)}
    if task_id not in eligible:raise ValueError("Task is not eligible for recovery.")
    if eligible[task_id]["has_active_plan"]:raise ValueError("An active recovery plan already exists.")
    if eligible[task_id]["owner"]!=uid:raise ValueError("Only the assigned task owner can create recovery plans.")
    if c.execute("SELECT 1 FROM vx_recovery31 WHERE workspace_id=? AND task_id=? AND status='active'",
                 (wid,task_id)).fetchone():
        raise ValueError("An active recovery plan already exists.")
    identifier=secrets.token_hex(12)
    now=int(time.time())
    c.execute("INSERT INTO vx_recovery31 VALUES (?,?,?,?,?,?,?,?,?)",
              (identifier,wid,task_id,uid,blocker,next_action,"active",now,now))
    return identifier

def resolve(c,uid,wid,identifier):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    row=c.execute("SELECT owner_id,status FROM vx_recovery31 WHERE workspace_id=? AND id=?",
                  (wid,identifier)).fetchone()
    if not row:raise ValueError("Recovery plan not found.")
    if row[0]!=uid:raise ValueError("Only the plan owner can resolve it.")
    if row[1]!="active":raise ValueError("Recovery plan is already resolved.")
    c.execute("UPDATE vx_recovery31 SET status='resolved',updated=? WHERE workspace_id=? AND id=?",
              (int(time.time()),wid,identifier))

def render(c,uid,wid,csrf):
    summary=workload(c,uid,wid)
    rows=summary["items"]
    e=lambda x:html.escape(str(x),quote=True)
    w=urllib.parse.quote(wid,safe="")
    plans=c.execute("""SELECT r.id,t.title,r.blocker,r.next_action,r.status,r.owner_id
        FROM vx_recovery31 r JOIN vx_revenue_tasks29 t
        ON t.workspace_id=r.workspace_id AND t.id=r.task_id
        WHERE r.workspace_id=? ORDER BY r.updated DESC LIMIT 100""",(wid,)).fetchall()
    out=['<section class="panel"><h1>Operations Recovery Engine</h1>',
         '<p>Document blockers and next steps for at-risk tasks. Internal workflow only: '
         'resolving a recovery plan does not mark the task complete, send messages, '
         'or verify revenue.</p><p>Tasks needing attention: '+str(summary['total'])+
         ' · Active recovery plans: '+str(summary['active_plans'])+
         ' · Showing up to 100 priority tasks.</p><p><a href="/revenue-execution?w='+w+
         '">Manage tasks</a></p></section>']
    for task in rows:
        out.append('<section class="panel"><h2>'+e(task["title"])+
                   '</h2><p>'+e(task["lead"])+' · '+e(", ".join(task["reasons"]))+'</p>')
        if task["owner"]==uid and not task["has_active_plan"]:
            out.append('<form method="post" action="/revenue-recovery">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="create">'
                       '<input type="hidden" name="task" value="'+e(task["id"])+'">'
                       '<label>Blocker<input name="blocker" maxlength="500" required></label>'
                       '<label>Next action<input name="next_action" maxlength="500" required></label>'
                       '<button>Create recovery plan</button></form>')
        if task['has_active_plan']:
            out.append('<p>Active recovery plan already recorded.</p>')
        out.append('</section>')
    out.append('<section class="panel"><h2>Recovery plans</h2></section>')
    for identifier,title,blocker,next_action,status,owner in plans:
        out.append('<section class="panel"><h3>'+e(title)+'</h3><p>Status: '+e(status)+
                   '</p><p>Blocker: '+e(blocker)+'</p><p>Next action: '+e(next_action)+'</p>')
        if owner==uid and status=="active":
            out.append('<form method="post" action="/revenue-recovery">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="resolve">'
                       '<input type="hidden" name="id" value="'+e(identifier)+'">'
                       '<button>Mark recovery plan resolved</button></form>')
        out.append('</section>')
    return ''.join(out)
