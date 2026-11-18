"""Workspace-scoped, human-controlled recovery plans for stalled tasks."""
import html
import secrets
import time
import urllib.parse
from datetime import date
import business_os_v59 as bos
import revenue_execution_v29 as execution

STATES=("open","resolved")

def setup(c):
    execution.setup(c)
    c.execute("""CREATE TABLE IF NOT EXISTS vx_recovery31 (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT NOT NULL,
        owner_id INTEGER NOT NULL, diagnosis TEXT NOT NULL, next_step TEXT NOT NULL,
        due_date TEXT NOT NULL, status TEXT NOT NULL, created INTEGER NOT NULL,
        updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_recovery31_scope ON vx_recovery31(workspace_id,task_id,status)")

def create(c,uid,wid,task_id,diagnosis,next_step,due_date):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    diagnosis=str(diagnosis).strip()
    next_step=str(next_step).strip()
    if not diagnosis or len(diagnosis)>500 or not next_step or len(next_step)>500:
        raise ValueError("Diagnosis and next step must each be 1–500 characters.")
    try:
        if date.fromisoformat(due_date).isoformat()!=due_date:raise ValueError()
    except (TypeError,ValueError):
        raise ValueError("Invalid recovery due date.")
    task=c.execute("SELECT owner_id,status FROM vx_revenue_tasks29 WHERE workspace_id=? AND id=?",(wid,task_id)).fetchone()
    if not task or task[0]!=uid or task[1]=="done":
        raise ValueError("Only the owner of an unfinished task can create a recovery plan.")
    existing=c.execute("SELECT 1 FROM vx_recovery31 WHERE workspace_id=? AND task_id=? AND status='open'",(wid,task_id)).fetchone()
    if existing:raise ValueError("An open recovery plan already exists for this task.")
    identifier=secrets.token_hex(12)
    now=int(time.time())
    c.execute("INSERT INTO vx_recovery31 VALUES (?,?,?,?,?,?,?,?,?,?)",
              (identifier,wid,task_id,uid,diagnosis,next_step,due_date,"open",now,now))
    return identifier

def resolve(c,uid,wid,plan_id):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    row=c.execute("SELECT owner_id,status FROM vx_recovery31 WHERE workspace_id=? AND id=?",(wid,plan_id)).fetchone()
    if not row or row[0]!=uid or row[1]!="open":
        raise ValueError("Only the recovery plan owner can resolve an open plan.")
    c.execute("UPDATE vx_recovery31 SET status='resolved',updated=? WHERE workspace_id=? AND id=?",
              (int(time.time()),wid,plan_id))

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid)
    setup(c)
    e=lambda v:html.escape(str(v),quote=True)
    w=urllib.parse.quote(wid,safe="")
    tasks=c.execute("""SELECT id,title,status,owner_id,due_date,updated FROM vx_revenue_tasks29
        WHERE workspace_id=? AND status!='done' ORDER BY due_date LIMIT 100""",(wid,)).fetchall()
    plans=c.execute("""SELECT p.id,t.title,p.diagnosis,p.next_step,p.due_date,p.status,p.owner_id
        FROM vx_recovery31 p JOIN vx_revenue_tasks29 t ON p.task_id=t.id AND p.workspace_id=t.workspace_id
        WHERE p.workspace_id=? ORDER BY CASE WHEN p.status='open' THEN 0 ELSE 1 END,p.due_date LIMIT 100""",(wid,)).fetchall()
    today=date.today().isoformat()
    now=int(time.time())
    candidates=[t for t in tasks if t[3]==uid and (t[2]=="blocked" or t[4]<today or (t[2] in ("todo","in_progress") and now-int(t[5])>=7*86400))]
    out=['<section class="panel"><h1>Operations Recovery Engine</h1>',
         '<p>Create explicit recovery plans for blocked, overdue, or stalled work. '
         'Plans are human-authored and do not change task status, send messages, or '
         'trigger external actions.</p>',
         '<p><a href="/revenue-operations?w='+w+'">Operations intelligence</a> · '
         '<a href="/revenue-execution?w='+w+'">Execution board</a></p></section>']
    if candidates:
        out.append('<section class="panel"><h2>Create recovery plan</h2>'
                   '<form method="post" action="/operations-recovery">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<input type="hidden" name="action" value="create">'
                   '<label>Task<select name="task" required>'+
                   ''.join('<option value="'+e(t[0])+'">'+e(t[1])+'</option>' for t in candidates)+
                   '</select></label>'
                   '<label>What is blocking progress?<textarea name="diagnosis" maxlength="500" required></textarea></label>'
                   '<label>Specific next step<textarea name="next_step" maxlength="500" required></textarea></label>'
                   '<label>Recovery due date<input type="date" name="due" required></label>'
                   '<button>Save recovery plan</button></form></section>')
    else:
        out.append('<section class="panel"><p>No blocked, overdue, or stalled tasks assigned to you '
                   'are currently available for recovery planning.</p></section>')
    for identifier,title,diagnosis,next_step,due,status,owner in plans:
        out.append('<section class="panel"><h3>'+e(title)+'</h3><p>'+e(status)+
                   ' · Due '+e(due)+'</p><p><strong>Obstacle:</strong> '+e(diagnosis)+
                   '</p><p><strong>Next step:</strong> '+e(next_step)+'</p>')
        if owner==uid and status=="open":
            out.append('<form method="post" action="/operations-recovery">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="resolve">'
                       '<input type="hidden" name="id" value="'+e(identifier)+'">'
                       '<button>Mark plan resolved</button></form>')
        out.append('</section>')
    return ''.join(out)
