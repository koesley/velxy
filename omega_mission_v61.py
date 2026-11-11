"""OMEGA Mission Control: human-approved business mission planning.

Deterministic, explainable mission plans; no external API calls, outreach,
spending, publishing, or autonomous execution.
"""
import html
import secrets
import time

ROLES=("Strategy","Marketing","Sales","Finance","Operations","Guardian")
TEMPLATES=(
 ("Strategy","Define the business model","Document target customer, core offer, and measurable success criteria."),
 ("Marketing","Prepare positioning","Draft value proposition, landing-page outline, and marketing experiments."),
 ("Sales","Design lead workflow","Specify qualification criteria, CRM stages, and follow-up templates."),
 ("Finance","Model economics","Estimate prices, costs, break-even, and conservative revenue scenarios."),
 ("Operations","Create execution roadmap","Break the plan into milestones, owners, and dependencies."),
 ("Guardian","Review safety and permissions","Identify data access, budget limits, approval requirements, and rollback plans."),
)
def esc(s):return html.escape(str(s),quote=True)
def check(c,user,workspace):
    if not workspace or not c.execute("SELECT 1 FROM empire_members WHERE workspace_id=? AND user_id=?",(workspace,user)).fetchone():
        raise ValueError("Workspace access denied")
def record(c,w,mid,actor,event,details):
    c.execute("INSERT INTO v61_events(id,workspace,mission,actor,event,details,created) VALUES (?,?,?,?,?,?,?)",
              (secrets.token_hex(16),w,mid,actor,event,details,int(time.time())))
def act(c,user,w,f):
    check(c,user,w)
    action=f.get("action","")
    if action=="create":
        objective=str(f.get("objective","")).strip()
        if not 12<=len(objective)<=1000:raise ValueError("Mission objective must be 12–1000 characters")
        mid=secrets.token_hex(16);now=int(time.time())
        c.execute("INSERT INTO v61_missions(id,workspace,owner,objective,status,created) VALUES (?,?,?,?,?,?)",
                  (mid,w,user,objective,"draft",now))
        for role,title,description in TEMPLATES:
            c.execute("INSERT INTO v61_tasks(id,workspace,mission,role,title,description,status,created) VALUES (?,?,?,?,?,?,?,?)",
                      (secrets.token_hex(16),w,mid,role,title,description,"proposed",now))
        record(c,w,mid,user,"mission_created","Six tasks proposed for human review")
    elif action in ("approve","reject","complete"):
        tid=str(f.get("task",""))
        row=c.execute("SELECT id,mission,status FROM v61_tasks WHERE id=? AND workspace=?",(tid,w)).fetchone()
        if not row:raise ValueError("Task not found")
        current=row[2]
        target={"approve":"approved","reject":"rejected","complete":"completed"}[action]
        if (current,target) not in (("proposed","approved"),("proposed","rejected"),("approved","completed")):
            raise ValueError("Invalid task transition")
        c.execute("UPDATE v61_tasks SET status=? WHERE id=? AND workspace=?",(target,tid,w))
        record(c,w,row[1],user,"task_"+target,tid)
    elif action in ("activate","pause","finish"):
        mid=str(f.get("mission",""))
        row=c.execute("SELECT status FROM v61_missions WHERE id=? AND workspace=?",(mid,w)).fetchone()
        if not row:raise ValueError("Mission not found")
        target={"activate":"active","pause":"paused","finish":"completed"}[action]
        if (row[0],target) not in (("draft","active"),("paused","active"),("active","paused"),("active","completed")):
            raise ValueError("Invalid mission transition")
        if action=="finish":
            remaining=c.execute("SELECT COUNT(*) FROM v61_tasks WHERE workspace=? AND mission=? AND status NOT IN ('completed','rejected')",(w,mid)).fetchone()[0]
            if remaining:raise ValueError("Resolve all tasks before completing the mission")
        c.execute("UPDATE v61_missions SET status=? WHERE id=? AND workspace=?",(target,mid,w))
        record(c,w,mid,user,"mission_"+target,"Manual state transition")
    else:raise ValueError("Unknown action")
def render(c,user,w,csrf):
    check(c,user,w)
    hidden=f'<input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="workspace" value="{esc(w)}">'
    def form(action,extra,label):
        return '<form method="post" action="/omega-v61">'+hidden+f'<input type="hidden" name="action" value="{action}">'+extra+f'<button>{esc(label)}</button></form>'
    out=['<section class="hero"><h1>VELXTRIA OMEGA · Mission Control</h1><p>Plan and supervise company initiatives. Nothing is executed externally; every task requires human approval.</p></section>']
    out.append('<section class="panel"><h2>Create a mission</h2>'+form("create",'<label>Business objective<textarea name="objective" minlength="12" maxlength="1000" required></textarea></label>',"Create mission")+'</section>')
    missions=c.execute("SELECT id,objective,status FROM v61_missions WHERE workspace=? ORDER BY created DESC LIMIT 20",(w,)).fetchall()
    for mid,objective,status in missions:
        out.append(f'<section class="panel"><h2>{esc(objective)}</h2><p>Status: {esc(status)}</p>')
        if status in ("draft","paused"):out.append(form("activate",f'<input type="hidden" name="mission" value="{esc(mid)}">',"Activate"))
        if status=="active":
            out.append(form("pause",f'<input type="hidden" name="mission" value="{esc(mid)}">',"Pause"))
            out.append(form("finish",f'<input type="hidden" name="mission" value="{esc(mid)}">',"Complete mission"))
        tasks=c.execute("SELECT id,role,title,description,status FROM v61_tasks WHERE workspace=? AND mission=? ORDER BY created,id",(w,mid)).fetchall()
        for tid,role,title,description,taskstatus in tasks:
            out.append(f'<article><h3>{esc(role)} · {esc(title)}</h3><p>{esc(description)}</p><p>{esc(taskstatus)}</p>')
            if taskstatus=="proposed":
                for action in ("approve","reject"):out.append(form(action,f'<input type="hidden" name="task" value="{esc(tid)}">',action.title()))
            if taskstatus=="approved":out.append(form("complete",f'<input type="hidden" name="task" value="{esc(tid)}">',"Mark complete"))
            out.append("</article>")
        events=c.execute("SELECT actor,event,details FROM v61_events WHERE workspace=? AND mission=? ORDER BY created DESC LIMIT 20",(w,mid)).fetchall()
        out.append("<h3>Audit history</h3>")
        for actor,event,details in events:out.append(f'<p>{esc(event)} by {esc(actor)} · {esc(details)}</p>')
        out.append("</section>")
    return "".join(out)
