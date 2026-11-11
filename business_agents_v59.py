"""Approval-first VELXTRIA agent workforce, memory and website FAQ knowledge.

All actions are internal proposals. No network calls, sending, spending or execution.
"""
import html
import secrets
import time
import sovereign_v56 as core

AGENTS=("sales","support","marketing","operations","finance")
STATES=("queued","in_review","approved","rejected","completed")

def init(c):
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_agent_jobs(
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,agent TEXT NOT NULL,
        goal TEXT NOT NULL,proposal TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,
        created_by INTEGER NOT NULL,reviewed_by INTEGER,reason TEXT NOT NULL DEFAULT '',
        created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_knowledge(
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,kind TEXT NOT NULL,
        question TEXT NOT NULL,answer TEXT NOT NULL,created_by INTEGER NOT NULL,
        created INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_jobs_scope ON bos59_agent_jobs(workspace_id,status)")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_knowledge_scope ON bos59_knowledge(workspace_id,kind)")

def clean(s,limit):
    if not isinstance(s,str) or not s.strip() or len(s.strip())>limit:
        raise ValueError("Invalid text")
    return s.strip()

def create_job(c,uid,wid,agent,goal):
    core.access(c,uid,wid,write=True);init(c)
    if agent not in AGENTS:raise ValueError("Unknown agent")
    goal=clean(goal,1000);jid=secrets.token_hex(12);now=int(time.time())
    with c:
        c.execute("INSERT INTO bos59_agent_jobs VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (jid,wid,agent,goal,"","queued",uid,None,"",now,now))
        core.audit(c,uid,wid,"bos_agent_job_created",jid)
    return jid

def propose_job(c,uid,wid,jid,proposal):
    core.access(c,uid,wid,write=True);init(c);proposal=clean(proposal,4000)
    with c:
        row=c.execute("SELECT status FROM bos59_agent_jobs WHERE id=? AND workspace_id=?",(jid,wid)).fetchone()
        if not row or row[0]!="queued":raise ValueError("Job not queued")
        c.execute("UPDATE bos59_agent_jobs SET proposal=?,status='in_review',updated=? WHERE id=? AND workspace_id=?",
                  (proposal,int(time.time()),jid,wid))
        core.audit(c,uid,wid,"bos_agent_proposed",jid)

def review_job(c,uid,wid,jid,decision,reason):
    core.access(c,uid,wid,write=True,owner=True);init(c)
    if decision not in ("approved","rejected"):raise ValueError("Invalid decision")
    reason=clean(reason,500)
    with c:
        row=c.execute("SELECT status FROM bos59_agent_jobs WHERE id=? AND workspace_id=?",(jid,wid)).fetchone()
        if not row or row[0]!="in_review":raise ValueError("Job not awaiting review")
        c.execute("UPDATE bos59_agent_jobs SET status=?,reason=?,reviewed_by=?,updated=? WHERE id=? AND workspace_id=?",
                  (decision,reason,uid,int(time.time()),jid,wid))
        core.audit(c,uid,wid,"bos_agent_"+decision,jid)

def complete_job(c,uid,wid,jid):
    core.access(c,uid,wid,write=True);init(c)
    with c:
        row=c.execute("SELECT status FROM bos59_agent_jobs WHERE id=? AND workspace_id=?",(jid,wid)).fetchone()
        if not row or row[0]!="approved":raise ValueError("Only approved jobs can be recorded complete")
        c.execute("UPDATE bos59_agent_jobs SET status='completed',updated=? WHERE id=? AND workspace_id=?",(int(time.time()),jid,wid))
        core.audit(c,uid,wid,"bos_agent_completed_manually",jid)

def add_knowledge(c,uid,wid,kind,question,answer):
    core.access(c,uid,wid,write=True);init(c)
    if kind not in ("faq","memory"):raise ValueError("Invalid knowledge type")
    question=clean(question,200);answer=clean(answer,3000)
    kid=secrets.token_hex(12)
    with c:
        c.execute("INSERT INTO bos59_knowledge VALUES(?,?,?,?,?,?,?)",
                  (kid,wid,kind,question,answer,uid,int(time.time())))
        core.audit(c,uid,wid,"bos_knowledge_created",kid)
    return kid

def remove_knowledge(c,uid,wid,kid):
    core.access(c,uid,wid,write=True);init(c)
    with c:
        row=c.execute("SELECT 1 FROM bos59_knowledge WHERE id=? AND workspace_id=?",(kid,wid)).fetchone()
        if not row:raise ValueError("Knowledge not found")
        c.execute("DELETE FROM bos59_knowledge WHERE id=? AND workspace_id=?",(kid,wid))
        core.audit(c,uid,wid,"bos_knowledge_deleted",kid)

def overview(c,uid,wid):
    role=core.access(c,uid,wid);init(c)
    jobs=[dict(zip(("id","agent","goal","proposal","status","reason"),row))
          for row in c.execute("SELECT id,agent,goal,proposal,status,reason FROM bos59_agent_jobs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 200",(wid,))]
    knowledge=[dict(zip(("id","kind","question","answer"),row))
               for row in c.execute("SELECT id,kind,question,answer FROM bos59_knowledge WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 200",(wid,))]
    return {"role":role,"jobs":jobs,"knowledge":knowledge,
            "counts":{"jobs":len(jobs),"awaiting_review":sum(j["status"]=="in_review" for j in jobs),
                      "approved_knowledge":len(knowledge)},
            "limitations":["Agent proposals are authored by people; no autonomous model execution is implemented.",
                           "Website knowledge is internal and not exposed as a public chatbot endpoint.",
                           "Completion is manually recorded, not externally verified."]}

def render(c,uid,wid,csrf):
    d=overview(c,uid,wid);h=lambda v:html.escape(str(v),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    url="/business-agents-v59"
    out=['<section class="ov-hero"><span>VELXTRIA · AGENT WORKFORCE</span><h1>One workspace. Five specialist queues.</h1><p>Draft tasks, review proposed work, and curate approved FAQ and business memory. No external actions occur.</p></section>']
    out.append('<section class="ov-metrics">'+''.join('<article class="ov-card"><strong>'+h(k.replace("_"," ").title())+'</strong><span>'+h(v)+'</span></article>' for k,v in d["counts"].items())+'</section>')
    if d["role"] in ("owner","editor"):
        out.append('<section class="ov-panel"><h2>Create agent task</h2><form method="post" action="'+url+'">'+hidden+'<label>Agent<select name="agent">'+''.join('<option>'+a+'</option>' for a in AGENTS)+'</select></label><label>Goal<textarea name="goal" required maxlength="1000"></textarea></label><button name="action" value="create">Create task</button></form></section>')
        out.append('<section class="ov-panel"><h2>Add approved business knowledge</h2><form method="post" action="'+url+'">'+hidden+'<label>Type<select name="kind"><option>faq</option><option>memory</option></select></label><label>Question or topic<input name="question" required maxlength="200"></label><label>Answer or fact<textarea name="answer" required maxlength="3000"></textarea></label><button name="action" value="knowledge">Save knowledge</button></form></section>')
    for j in d["jobs"]:
        out.append('<section class="ov-panel"><h2>'+h(j["agent"].title())+' · '+h(j["status"])+'</h2><p>'+h(j["goal"])+'</p><p>'+h(j["proposal"])+'</p>')
        if j["status"]=="queued" and d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="job" value="'+h(j["id"])+'"><label>Proposed result<textarea name="proposal" required maxlength="4000"></textarea></label><button name="action" value="propose">Submit for review</button></form>')
        if j["status"]=="in_review" and d["role"]=="owner":
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="job" value="'+h(j["id"])+'"><label>Reason<input name="reason" required maxlength="500"></label><button name="decision" value="approved">Approve</button><button name="decision" value="rejected">Reject</button><input type="hidden" name="action" value="review"></form>')
        if j["status"]=="approved" and d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="job" value="'+h(j["id"])+'"><button name="action" value="complete">Record manual completion</button></form>')
        out.append('</section>')
    for k in d["knowledge"]:
        out.append('<section class="ov-panel"><h2>'+h(k["kind"].upper())+' · '+h(k["question"])+'</h2><p>'+h(k["answer"])+'</p>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="knowledge" value="'+h(k["id"])+'"><button name="action" value="delete_knowledge">Delete</button></form>')
        out.append('</section>')
    return ''.join(out)
