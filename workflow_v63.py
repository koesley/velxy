"""V63 workflow operations: internal execution receipts and measurable, manual outcomes.

No outbound delivery, payments, or external integrations. Every operation is
tenant-scoped, auditable, and restricted to approved agent tasks.
"""
import html
import secrets
import time
import urllib.parse
import business_agents_v59 as agents

OUTCOMES=("lead_contacted","appointment_booked","sale_reported","issue_resolved","other")
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS v63_execution_receipts(
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,job_id TEXT NOT NULL,
        performed_by INTEGER NOT NULL,kind TEXT NOT NULL,notes TEXT NOT NULL,
        created INTEGER NOT NULL)""")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS v63_execution_once ON v63_execution_receipts(workspace_id,job_id)")
    c.execute("""CREATE TABLE IF NOT EXISTS v63_outcomes(
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,job_id TEXT NOT NULL,
        recorded_by INTEGER NOT NULL,kind TEXT NOT NULL,amount REAL NOT NULL,
        notes TEXT NOT NULL,created INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS v63_outcome_scope ON v63_outcomes(workspace_id,created)")

def text_field(s,limit):
    if not isinstance(s,str) or not 1<=len(s.strip())<=limit:raise ValueError("Invalid text")
    return s.strip()

def execute_internal(c,uid,wid,jid,notes):
    agents.core.access(c,uid,wid,write=True,owner=True)
    setup(c);notes=text_field(notes,1000)
    row=c.execute("SELECT status FROM bos59_agent_jobs WHERE id=? AND workspace_id=?",(jid,wid)).fetchone()
    if not row or row[0]!="approved":raise ValueError("Only approved jobs may be completed")
    if c.execute("SELECT 1 FROM v63_execution_receipts WHERE workspace_id=? AND job_id=?",(wid,jid)).fetchone():
        raise ValueError("Execution receipt already exists")
    rid=secrets.token_hex(12)
    c.execute("INSERT INTO v63_execution_receipts VALUES(?,?,?,?,?,?,?)",
              (rid,wid,jid,uid,"internal_manual_completion",notes,int(time.time())))
    agents.complete_job(c,uid,wid,jid)
    agents.core.audit(c,uid,wid,"v63_internal_execution_recorded",rid)
    return rid

def record_outcome(c,uid,wid,jid,kind,amount,notes):
    agents.core.access(c,uid,wid,write=True)
    setup(c)
    if kind not in OUTCOMES:raise ValueError("Unknown outcome")
    notes=text_field(notes,1000)
    try:
        value=float(amount)
    except (ValueError,TypeError,OverflowError):
        raise ValueError("Invalid amount")
    import math
    if not math.isfinite(value) or value<0 or value>1000000000:raise ValueError("Invalid amount")
    row=c.execute("SELECT status FROM bos59_agent_jobs WHERE id=? AND workspace_id=?",(jid,wid)).fetchone()
    if not row or row[0]!="completed":raise ValueError("Only completed jobs can have outcomes")
    oid=secrets.token_hex(12)
    c.execute("INSERT INTO v63_outcomes VALUES(?,?,?,?,?,?,?,?)",
              (oid,wid,jid,uid,kind,value,notes,int(time.time())))
    agents.core.audit(c,uid,wid,"v63_outcome_recorded",oid)
    return oid

def overview(c,uid,wid):
    role=agents.core.access(c,uid,wid)
    setup(c);agents.init(c)
    jobs=c.execute("SELECT id,agent,goal,status FROM bos59_agent_jobs WHERE workspace_id=? ORDER BY created DESC LIMIT 200",(wid,)).fetchall()
    receipts=c.execute("SELECT job_id,notes,created FROM v63_execution_receipts WHERE workspace_id=? ORDER BY created DESC LIMIT 200",(wid,)).fetchall()
    outcomes=c.execute("SELECT job_id,kind,amount,notes,created FROM v63_outcomes WHERE workspace_id=? ORDER BY created DESC LIMIT 200",(wid,)).fetchall()
    return {"role":role,"jobs":jobs,"receipts":receipts,"outcomes":outcomes,
            "completed_jobs":sum(j[3]=="completed" for j in jobs),
            "reported_sales":round(sum(o[2] for o in outcomes if o[1]=="sale_reported"),2)}

def render(c,uid,wid,csrf):
    d=overview(c,uid,wid);h=lambda x:html.escape(str(x),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V63 · Workflow & Outcomes</h1><p>Record approved internal work and self-reported outcomes. No external systems are changed.</p><p>Completed jobs: '+h(d["completed_jobs"])+' · Self-reported sales: '+h(d["reported_sales"])+'</p></section>']
    for jid,agent,goal,status in d["jobs"]:
        out.append('<section class="panel"><h3>'+h(agent)+' · '+h(status)+'</h3><p>'+h(goal)+'</p>')
        if status=="approved" and d["role"]=="owner":
            out.append('<form method="post" action="/workflow-v63">'+hidden+'<input type="hidden" name="job" value="'+h(jid)+'"><label>Internal work completed (manual confirmation)<textarea name="notes" required maxlength="1000"></textarea></label><button name="action" value="complete">Record completion</button></form>')
        if status=="completed" and d["role"] in ("owner","editor"):
            out.append('<form method="post" action="/workflow-v63">'+hidden+'<input type="hidden" name="job" value="'+h(jid)+'"><label>Outcome<select name="kind">'+''.join('<option>'+h(k)+'</option>' for k in OUTCOMES)+'</select></label><label>Self-reported amount<input name="amount" type="number" min="0" max="1000000000" step="0.01" value="0" required></label><label>Evidence or notes<textarea name="notes" required maxlength="1000"></textarea></label><button name="action" value="outcome">Record outcome</button></form>')
        out.append('</section>')
    out.append('<section class="panel"><h2>Outcome log</h2>')
    for jid,kind,amount,notes,created in d["outcomes"]:
        out.append('<p>'+h(kind)+' · '+h(amount)+' · '+h(notes)+'</p>')
    out.append('<p><small>All outcome values are manually reported and not verified revenue. No messages are sent or payments processed.</small></p></section>')
    return ''.join(out)
