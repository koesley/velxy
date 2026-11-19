"""Persistent internal revenue execution board; no external actions."""
import html
import secrets
import time
import urllib.parse
from datetime import date
import business_os_v59 as bos
import revenue_gap_v28 as gap
import revenue_execution_workload as workload

STATES=("todo","in_progress","done","blocked")

# Columns the tasks table must have. setup() adds any that are missing so a
# database created by an older version (or a hand-built table) heals itself
# instead of failing when the index below is created.
_COLUMNS=(("workspace_id","TEXT NOT NULL DEFAULT ''"),("lead_id","TEXT NOT NULL DEFAULT ''"),
 ("title","TEXT NOT NULL DEFAULT ''"),("owner_id","INTEGER NOT NULL DEFAULT 0"),
 ("due_date","TEXT NOT NULL DEFAULT ''"),("status","TEXT NOT NULL DEFAULT 'todo'"),
 ("created","INTEGER NOT NULL DEFAULT 0"),("updated","INTEGER NOT NULL DEFAULT 0"))

def _ensure_columns(c):
    import persistent
    if persistent.REMOTE:
        for name,ddl in _COLUMNS:
            c.execute("ALTER TABLE vx_revenue_tasks29 ADD COLUMN IF NOT EXISTS %s %s"%(name,ddl))
        return
    cols={r[1] for r in c.execute("PRAGMA table_info(vx_revenue_tasks29)")}
    for name,ddl in _COLUMNS:
        if name not in cols:
            c.execute("ALTER TABLE vx_revenue_tasks29 ADD COLUMN %s %s"%(name,ddl))

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_revenue_tasks29 (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
        title TEXT NOT NULL, owner_id INTEGER NOT NULL, due_date TEXT NOT NULL,
        status TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
    _ensure_columns(c)
    c.execute("CREATE INDEX IF NOT EXISTS vx_revenue_tasks29_scope ON vx_revenue_tasks29(workspace_id,status,due_date)")

def create(c,uid,wid,lid,title,due):
    bos.core.access(c,uid,wid,write=True)
    bos.init(c)
    setup(c)
    title=str(title).strip()
    if not title or len(title)>140:raise ValueError("Task title must be 1–140 characters.")
    try:
        if date.fromisoformat(due).isoformat()!=due:raise ValueError()
    except (ValueError,TypeError):
        raise ValueError("Invalid due date.")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND id=? AND status IN ('new','contacted')",(wid,lid)).fetchone():
        raise ValueError("Choose an open lead in this workspace.")
    if c.execute("SELECT 1 FROM vx_revenue_tasks29 WHERE workspace_id=? AND lead_id=? AND status IN ('todo','in_progress') AND title=?",(wid,lid,title)).fetchone():
        raise ValueError("An active task with this title already exists for this lead.")
    now=int(time.time())
    identifier=secrets.token_hex(12)
    c.execute("INSERT INTO vx_revenue_tasks29 VALUES (?,?,?,?,?,?,?,?,?)",
              (identifier,wid,lid,title,uid,due,"todo",now,now))
    return identifier

def change(c,uid,wid,task_id,status):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    if status not in STATES:raise ValueError("Invalid task status.")
    row=c.execute("SELECT owner_id,status FROM vx_revenue_tasks29 WHERE workspace_id=? AND id=?",(wid,task_id)).fetchone()
    if not row:raise ValueError("Task not found.")
    if row[0]!=uid:raise ValueError("Only the assigned owner can update this task.")
    if row[1]=="done":raise ValueError("Completed tasks cannot be reopened.")
    c.execute("UPDATE vx_revenue_tasks29 SET status=?,updated=? WHERE workspace_id=? AND id=?",
              (status,int(time.time()),wid,task_id))

def render(c,uid,wid,csrf,status="all",page=1):
    bos.core.access(c,uid,wid)
    bos.init(c)
    setup(c)
    e=lambda v:html.escape(str(v),quote=True)
    leads=c.execute("SELECT id,name FROM bos59_leads WHERE workspace_id=? AND status IN ('new','contacted') ORDER BY updated DESC LIMIT 300",(wid,)).fetchall()
    counts,due_counts=workload.summary(c,wid)
    total,rows=workload.page(c,wid,status,page)
    page=int(page)
    w=urllib.parse.quote(wid,safe="")
    out=['<section class="panel"><h1>Revenue Execution Board</h1>',
         '<p>Internal tasks assigned to their creator. No automated outreach, payments, '
         'or verified revenue attribution. Showing 25 tasks per page.</p>',
         '<p>'+ ' · '.join(e(s.replace("_"," ").title())+': '+str(counts[s]) for s in STATES)+'</p>',
         '<p>Overdue: '+str(due_counts[0])+' · Due today: '+str(due_counts[1])+' · Future: '+str(due_counts[2])+'</p>',
         '<p><a href="/revenue-gap?w='+w+'">View goal-gap opportunities</a></p></section>',
         '<section class="panel"><h2>Browse tasks</h2><p>Matching tasks: '+str(total)+' · Page '+str(page)+'</p>',
         '<form method="get" action="/revenue-execution"><input type="hidden" name="w" value="'+e(wid)+'">',
         '<label>Status<select name="status">'+''.join('<option value="'+e(x)+'"'+(' selected' if x==status else '')+'>'+e(x.replace("_"," ").title())+'</option>' for x in ("all",)+STATES)+'</select></label><button>Filter</button></form></section>']
    base='/revenue-execution?w='+w+'&status='+urllib.parse.quote(status,safe='')+'&page='
    nav=[]
    if page>1:nav.append('<a href="'+base+str(page-1)+'">Previous</a>')
    if page*25<total:nav.append('<a href="'+base+str(page+1)+'">Next</a>')
    out.append('<section class="panel">'+(' · '.join(nav) if nav else 'No additional pages')+'</section>')

    if leads:
        out.append('<section class="panel"><h2>Create action task</h2><form method="post" action="/revenue-execution">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<input type="hidden" name="action" value="create">'
                   '<label>Lead<select name="lead" required>'+
                   ''.join('<option value="'+e(lid)+'">'+e(name)+'</option>' for lid,name in leads)+'</select></label>'
                   '<label>Task<input name="title" maxlength="140" required></label>'
                   '<label>Due<input type="date" name="due" required></label>'
                   '<button>Create task</button></form></section>')
    for identifier,name,title,due,status,owner in rows:
        out.append('<section class="panel"><h3>'+e(title)+'</h3><p>'+e(name)+
                   ' · Due '+e(due)+' · '+e(status.replace("_"," "))+
                   ' · '+("Assigned to you" if owner==uid else "Assigned to another member")+'</p>')
        if owner==uid and status!="done":
            out.append('<form method="post" action="/revenue-execution">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="status">'
                       '<input type="hidden" name="id" value="'+e(identifier)+'">'
                       '<label>Update status<select name="status">'+
                       ''.join('<option value="'+e(s)+'">'+e(s.replace("_"," ").title())+'</option>' for s in STATES)+
                       '</select></label><button>Save</button></form>')
        out.append('</section>')
    return ''.join(out)
