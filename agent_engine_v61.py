"""VELXTRIA V61: bounded, approval-first AI drafting and agent orchestration.

Uses OpenAI-compatible Chat Completions only when explicitly configured.
Never executes tools, sends messages, exposes secrets or auto-approves actions.
"""
import html
import json
import os
import secrets
import time
import urllib.request
import urllib.error
import business_agents_v59 as agents
import business_intelligence_v60 as intelligence

ROLES=("sales","support","marketing","operations","finance")
MAX_RESPONSE=12000

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS v61_runs (
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,created_by INTEGER NOT NULL,
      objective TEXT NOT NULL,status TEXT NOT NULL,output TEXT NOT NULL,
      provider TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS v61_runs_workspace ON v61_runs(workspace_id,created)")
    c.execute("""CREATE TABLE IF NOT EXISTS v61_events (
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,run_id TEXT NOT NULL,
      actor INTEGER NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL,created INTEGER NOT NULL)""")

def log(c,uid,wid,rid,event,detail=""):
    c.execute("INSERT INTO v61_events VALUES(?,?,?,?,?,?,?)",
              (secrets.token_hex(12),wid,rid,uid,event,str(detail)[:500],int(time.time())))

def plan(c,uid,wid,objective,model_call=None):
    agents.core.access(c,uid,wid,write=True)
    if not isinstance(objective,str) or not 5<=len(objective.strip())<=800:
        raise ValueError("Objective must be 5-800 characters")
    setup(c)
    objective=objective.strip()
    facts=intelligence.analyze(c,uid,wid)
    safe_context={k:facts[k] for k in ("lead_count","open_potential","status_counts","pending_reviews","suggestions")}
    prompt={"objective":objective,"facts":safe_context,
            "instructions":"Produce a short, concrete proposal for sales, support, marketing, operations and finance. Treat facts as unverified. Do not claim you contacted anyone or executed actions. Avoid personal information."}
    rid=secrets.token_hex(12);now=int(time.time())
    c.execute("INSERT INTO v61_runs VALUES(?,?,?,?,?,?,?,?,?)",
              (rid,wid,uid,objective,"drafting","","pending",now,now))
    log(c,uid,wid,rid,"created")
    try:
        if model_call is not None:
            response=model_call(prompt)
            provider="injected"
        elif os.getenv("VELXTRIA_V61_AI_ENABLED")=="1":
            response=call_model(prompt)
            provider="configured_ai"
        else:
            response=offline_plan(prompt)
            provider="offline_rules"
        if not isinstance(response,str) or not response.strip():
            raise ValueError("Empty model response")
        response=response.strip()[:MAX_RESPONSE]
        c.execute("UPDATE v61_runs SET status='awaiting_review',output=?,provider=?,updated=? WHERE id=? AND workspace_id=?",
                  (response,provider,int(time.time()),rid,wid))
        log(c,uid,wid,rid,"draft_ready",provider)
    except Exception:
        # Fail closed; never leak provider error bodies or credentials.
        c.execute("UPDATE v61_runs SET status='failed',provider='unavailable',updated=? WHERE id=? AND workspace_id=?",
                  (int(time.time()),rid,wid))
        log(c,uid,wid,rid,"draft_failed","Provider unavailable")
    return rid

def offline_plan(prompt):
    facts=prompt["facts"]
    suggestions=facts["suggestions"]
    parts=["Draft business plan (rule-based fallback; no AI model used).",
           "Objective: "+prompt["objective"],
           "Potential pipeline: "+str(facts["open_potential"])+" (unverified, not collected revenue)."]
    parts.extend("- "+s["title"]+": "+s["goal"] for s in suggestions)
    parts.append("Review all recommendations before creating any tasks. No external actions taken.")
    return "\n".join(parts)

def call_model(prompt):
    key=os.getenv("VELXTRIA_V61_AI_API_KEY","")
    model=os.getenv("VELXTRIA_V61_AI_MODEL","")
    endpoint=os.getenv("VELXTRIA_V61_AI_ENDPOINT","https://api.openai.com/v1/chat/completions")
    if not key or not model:raise ValueError("AI provider not configured")
    # Fixed allowlist to avoid SSRF and arbitrary destinations for private business data.
    if endpoint not in ("https://api.openai.com/v1/chat/completions",):
        raise ValueError("Unsupported AI endpoint")
    payload=json.dumps({"model":model,"temperature":0.2,"max_tokens":900,
        "messages":[{"role":"system","content":"You are a cautious business planning assistant. Output proposals only. Never claim execution, certainty, or verified financial outcomes."},
                    {"role":"user","content":json.dumps(prompt)}]}).encode()
    request=urllib.request.Request(endpoint,data=payload,method="POST",headers={
        "Authorization":"Bearer "+key,"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=15) as resp:
        if int(resp.headers.get("Content-Length","0") or 0)>65536:
            raise ValueError("Provider response too large")
        raw=resp.read(65537)
        if len(raw)>65536:raise ValueError("Provider response too large")
    result=json.loads(raw)
    return result["choices"][0]["message"]["content"]

def list_runs(c,uid,wid):
    agents.core.access(c,uid,wid)
    setup(c)
    return [dict(zip(("id","objective","status","output","provider","created"),row))
            for row in c.execute("SELECT id,objective,status,output,provider,created FROM v61_runs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100",(wid,))]

def approve_as_task(c,uid,wid,rid,role):
    agents.core.access(c,uid,wid,write=True,owner=True)
    if role not in ROLES:raise ValueError("Unknown agent role")
    setup(c)
    row=c.execute("SELECT objective,output,status FROM v61_runs WHERE id=? AND workspace_id=?",(rid,wid)).fetchone()
    if not row or row[2]!="awaiting_review":raise ValueError("Plan not ready for review")
    # Owner authorizes a new internal task, not outbound execution.
    jid=agents.create_job(c,uid,wid,role,("Review plan for objective: "+row[0])[:1000])
    agents.propose_job(c,uid,wid,jid,row[1][:4000])
    log(c,uid,wid,rid,"task_created",jid)
    return jid

def render(c,uid,wid,csrf):
    role=agents.core.access(c,uid,wid);runs=list_runs(c,uid,wid)
    h=lambda v:html.escape(str(v),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V61 · Agent Engine</h1><p>Plan business objectives using configured AI or a transparent rule-based fallback. All results are drafts. No external actions are executed.</p></section>']
    if role in ("owner","editor"):
        out.append('<section class="panel"><form method="post" action="/agent-engine-v61">'+hidden+'<label>Business objective<textarea name="objective" maxlength="800" required></textarea></label><button name="action" value="plan">Generate plan</button></form></section>')
    for run in runs:
        out.append('<section class="panel"><h2>'+h(run["objective"])+'</h2><p>Status: '+h(run["status"])+' · Engine: '+h(run["provider"])+'</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+h(run["output"])+'</pre>')
        if run["status"]=="awaiting_review" and role=="owner":
            out.append('<form method="post" action="/agent-engine-v61">'+hidden+'<input type="hidden" name="run" value="'+h(run["id"])+'"><label>Assign agent<select name="role">'+''.join('<option>'+a+'</option>' for a in ROLES)+'</select></label><button name="action" value="task">Submit draft for approval</button></form>')
        out.append('</section>')
    out.append('<section class="panel"><a href="/business-agents-v59?w='+h(wid)+'">Review agent tasks</a></section>')
    return ''.join(out)
