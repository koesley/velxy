"""Durable, tenant-isolated workflow orchestrator with explicit human gates.

Workflows are internal task plans only. No outbound send or payment actions.
"""
import html
import secrets
import time
import sales_pipeline
import sovereign_ascension

STEPS=("review","draft","execute_manually","record_outcome")
TERMINAL=("completed","cancelled")

def esc(value):return html.escape(str(value),quote=True)

def setup(c):
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    c.execute("""CREATE TABLE IF NOT EXISTS ascension_workflows(
        id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, lead_id TEXT NOT NULL,
        action_id TEXT NOT NULL, status TEXT NOT NULL, current_step INTEGER NOT NULL,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(owner_id,action_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS ascension_workflow_events(
        id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, workflow_id TEXT NOT NULL,
        event TEXT NOT NULL, note TEXT NOT NULL, created_at INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS ascension_workflow_owner ON ascension_workflows(owner_id,status,updated_at)")
    c.execute("CREATE INDEX IF NOT EXISTS ascension_workflow_events_owner ON ascension_workflow_events(owner_id,workflow_id,created_at)")

def log(c,owner,wid,event,note=""):
    c.execute("INSERT INTO ascension_workflow_events VALUES (?,?,?,?,?,?)",
              (secrets.token_hex(12),owner,wid,event,note[:500],int(time.time())))

def create(c,owner,action_id):
    setup(c)
    row=c.execute("""SELECT a.lead_id FROM ascension_actions a
      JOIN sales_pipeline_leads l ON l.id=a.lead_id AND l.owner_id=a.owner_id
      WHERE a.id=? AND a.owner_id=? AND a.status='approved'""",(action_id,owner)).fetchone()
    if not row:raise ValueError("An approved action owned by this account is required")
    if c.execute("SELECT 1 FROM ascension_workflows WHERE owner_id=? AND action_id=?",(owner,action_id)).fetchone():
        raise ValueError("Workflow already exists for this approved action")
    wid=secrets.token_hex(12);now=int(time.time())
    c.execute("INSERT INTO ascension_workflows VALUES (?,?,?,?,?,?,?,?)",
              (wid,owner,row[0],action_id,"active",0,now,now))
    log(c,owner,wid,"created","Approved action linked")
    return wid

def transition(c,owner,wid,decision,note=""):
    setup(c)
    if decision not in ("advance","cancel"):raise ValueError("Invalid workflow decision")
    if len(note)>500:raise ValueError("Note exceeds 500 characters")
    row=c.execute("""SELECT w.current_step,w.status,w.action_id,l.email
        FROM ascension_workflows w JOIN sales_pipeline_leads l
        ON l.id=w.lead_id AND l.owner_id=w.owner_id
        WHERE w.id=? AND w.owner_id=?""",(wid,owner)).fetchone()
    if not row:raise ValueError("Workflow not found")
    step,status,action_id,email=row
    if status!="active":raise ValueError("Workflow is no longer active")
    if decision=="cancel":
        c.execute("UPDATE ascension_workflows SET status='cancelled',updated_at=? WHERE id=? AND owner_id=?",
                  (int(time.time()),wid,owner))
        log(c,owner,wid,"cancelled",note)
        return "cancelled"
    if not note.strip():raise ValueError("Human confirmation note is required")
    if step in (1,2) and not (email and sales_pipeline.outreach_eligibility(c,owner,email)):
        raise ValueError("Contact is suppressed or not verified clear; cannot advance")
    if step==2:
        completed=c.execute("SELECT 1 FROM ascension_actions WHERE id=? AND owner_id=? AND status='completed'",(action_id,owner)).fetchone()
        if not completed:raise ValueError("Complete the approved action in Ascension before proceeding")
    if step==3:
        import ascension_recovery
        ascension_recovery.setup(c)
        outcome=c.execute("SELECT 1 FROM ascension_recovery_outcomes WHERE owner_id=? AND action_id=?",(owner,action_id)).fetchone()
        if not outcome:raise ValueError("Record the outcome in Revenue Recovery before closing")
    next_step=step+1
    state="completed" if next_step==len(STEPS) else "active"
    changed=c.execute("""UPDATE ascension_workflows SET current_step=?,status=?,updated_at=?
        WHERE id=? AND owner_id=? AND status='active' AND current_step=?""",
        (next_step,state,int(time.time()),wid,owner,step))
    updated_rows = changed.cursor.rowcount if hasattr(changed,"cursor") else changed.rowcount
    if updated_rows != 1:
        raise ValueError("Workflow changed concurrently; reload before continuing")
    log(c,owner,wid,"completed" if state=="completed" else "advanced",note)
    return state

def dashboard(c,owner,csrf):
    setup(c)
    rows=c.execute("""SELECT w.id,w.status,w.current_step,l.business,l.email
        FROM ascension_workflows w JOIN sales_pipeline_leads l
        ON l.id=w.lead_id AND l.owner_id=w.owner_id
        WHERE w.owner_id=? ORDER BY w.updated_at DESC LIMIT 100""",(owner,)).fetchall()
    pending=c.execute("""SELECT a.id,l.business FROM ascension_actions a
        JOIN sales_pipeline_leads l ON l.id=a.lead_id AND l.owner_id=a.owner_id
        WHERE a.owner_id=? AND a.status='approved'
        AND NOT EXISTS(SELECT 1 FROM ascension_workflows w WHERE w.owner_id=a.owner_id AND w.action_id=a.id)
        ORDER BY a.updated_at DESC LIMIT 100""",(owner,)).fetchall()
    parts=['<section class="hero"><h1>Workflow Orchestrator</h1><p>Durable internal execution plans with human approvals, activity history and safety gates. VELXTRIA does not send messages or perform external actions here.</p></section>']
    parts.append('<section class="panel"><h2>Approved opportunities</h2>')
    for aid,business in pending:
        parts.append('<article><strong>'+esc(business)+'</strong><form method="post" action="/ascension-workflow-create"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action_id" value="'+esc(aid)+'"><button type="submit">Create execution plan</button></form></article>')
    if not pending:parts.append('<p>No approved opportunities waiting for a plan.</p>')
    parts.append('</section><section class="panel"><h2>Execution plans</h2>')
    for wid,status,step,business,email in rows:
        label=STEPS[min(step,len(STEPS)-1)] if status=="active" else status
        parts.append('<article><h3>'+esc(business)+'</h3><p>Status: '+esc(status)+' · Step: '+esc(label.replace('_',' '))+'</p>')
        if status=="active":
            parts.append('<p>Contact status: '+('verified clear' if email and sales_pipeline.outreach_eligibility(c,owner,email) else 'unverified or restricted')+'</p>')
            parts.append('<form method="post" action="/ascension-workflow-transition"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workflow_id" value="'+esc(wid)+'"><label>Human confirmation / evidence<input name="note" maxlength="500" required></label><button name="decision" value="advance" type="submit">Confirm step complete</button><button name="decision" value="cancel" type="submit">Cancel plan</button></form>')
        events=c.execute("SELECT event,note,created_at FROM ascension_workflow_events WHERE owner_id=? AND workflow_id=? ORDER BY created_at DESC LIMIT 10",(owner,wid)).fetchall()
        parts.append('<details><summary>Audit history</summary>')
        for event,note,at in events:parts.append('<p>'+esc(event)+' · '+esc(note)+' · '+str(at)+'</p>')
        parts.append('</details></article>')
    if not rows:parts.append('<p>No execution plans yet.</p>')
    parts.append('</section>')
    return ''.join(parts)
