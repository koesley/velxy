"""Workspace growth strategy tasks, evidence and decision rules."""
import html,secrets,time,urllib.parse
from datetime import date
import business_os_v59 as bos
import growth_intelligence_v41 as growth
STATUSES=("open","in_progress","blocked","completed")
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS vx_growth_strategy42(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,owner_id INTEGER NOT NULL,
 title TEXT NOT NULL,reason TEXT NOT NULL,metric TEXT NOT NULL,target TEXT NOT NULL,
 due TEXT NOT NULL,status TEXT NOT NULL,priority TEXT NOT NULL,created INTEGER NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS vx_growth_events42(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,plan_id TEXT NOT NULL,actor_id INTEGER NOT NULL,
 previous TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL,created INTEGER NOT NULL)""")
 c.execute("CREATE INDEX IF NOT EXISTS vx_growth_strategy42_scope ON vx_growth_strategy42(workspace_id,status,due)")
def suggestions(data):
 result=[]
 if not data["lead_count"]:result.append(("high","Capture and qualify prospects","No leads are recorded.","Qualified leads","10"))
 if data["lead_count"] and not data["acquisition_spend_cents"]:result.append(("high","Reconcile acquisition costs","Leads exist without recorded acquisition costs.","Channels with reconciled costs","All"))
 if data["lead_count"] and not data["won_lead_count"]:result.append(("high","Improve lead follow-up","Leads exist but none is marked won.","Won-marked leads","1"))
 if data["pending_followups"]:result.append(("medium","Complete optimization follow-ups","Implemented changes lack follow-up evidence.","Follow-up records",str(data["pending_followups"])))
 if data["campaigns"] and not data["review_ready_campaigns"]:result.append(("medium","Strengthen campaign measurement","No completed experiment meets descriptive screening thresholds.","Review-ready campaigns","1"))
 if not result:result.append(("medium","Review growth constraints","Validate growth data and identify one measurable constraint.","Completed review","1"))
 return result
def create(c,uid,wid,owner,title,reason,metric,target,due,priority):
 bos.core.access(c,uid,wid,write=True);setup(c)
 vals=[str(v).strip() for v in (title,reason,metric,target)]
 if any(not v for v in vals) or len(vals[0])>120 or any(len(v)>500 for v in vals):raise ValueError("Complete all plan fields; title limit 120 characters, other fields 500.")
 try:
  if date.fromisoformat(due).isoformat()!=due:raise ValueError()
 except (ValueError,TypeError):raise ValueError("Invalid due date.")
 if priority not in ("high","medium","low"):raise ValueError("Invalid priority.")
 try:owner=int(owner)
 except (ValueError,TypeError):raise ValueError("Invalid owner.")
 if not c.execute("SELECT 1 FROM empire_members WHERE workspace_id=? AND user_id=?",(wid,owner)).fetchone():raise ValueError("Owner is not a workspace member.")
 identifier=secrets.token_hex(12)
 c.execute("INSERT INTO vx_growth_strategy42 VALUES (?,?,?,?,?,?,?,?,?,?,?)",(identifier,wid,owner,*vals,due,"open",priority,int(time.time())))
 return identifier
def change(c,uid,wid,identifier,status,note):
 bos.core.access(c,uid,wid,write=True);setup(c)
 row=c.execute("SELECT owner_id,status FROM vx_growth_strategy42 WHERE workspace_id=? AND id=?",(wid,identifier)).fetchone()
 if not row or row[0]!=uid:raise ValueError("Only the assigned workspace owner may update this plan.")
 if row[1]=="completed" or status not in STATUSES:raise ValueError("Invalid plan transition.")
 note=str(note).strip()
 if not 1<=len(note)<=500:raise ValueError("A progress evidence note is required (max 500 characters).")
 c.execute("UPDATE vx_growth_strategy42 SET status=? WHERE workspace_id=? AND id=?",(status,wid,identifier))
 c.execute("INSERT INTO vx_growth_events42 VALUES (?,?,?,?,?,?,?,?)",(secrets.token_hex(12),wid,identifier,uid,row[1],status,note,int(time.time())))
def analyze(c,uid,wid):
 bos.core.access(c,uid,wid);setup(c)
 rows=c.execute("""SELECT id,owner_id,title,reason,metric,target,due,status,priority FROM vx_growth_strategy42
 WHERE workspace_id=? ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,due LIMIT 150""",(wid,)).fetchall()
 return [dict(zip(("id","owner","title","reason","metric","target","due","status","priority"),r)) for r in rows]
def render(c,uid,wid,csrf):
 bos.core.access(c,uid,wid);setup(c)
 e=lambda v:html.escape(str(v),quote=True)
 data=growth.analyze(c,uid,wid);plans=analyze(c,uid,wid)
 members=c.execute("SELECT user_id FROM empire_members WHERE workspace_id=? ORDER BY user_id",(wid,)).fetchall()
 out=['<section class="panel"><h1>Growth Strategy Engine</h1><p>Rule-based growth signals become manually created, owner-assigned action plans with measurable targets and an append-only progress log. No automated execution, forecasts or verified revenue claims.</p></section><section class="panel"><h2>Suggested priorities</h2>']
 for priority,title,why,metric,target in suggestions(data):out.append('<p><strong>'+e(priority.upper()+": "+title)+'</strong> — '+e(why)+' Suggested metric: '+e(metric)+'; target '+e(target)+'</p>')
 out.append('</section><section class="panel"><h2>Create action plan</h2><form method="post" action="/growth-strategy"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="create"><label>Title<input name="title" maxlength="120" required></label><label>Rationale<textarea name="reason" maxlength="500" required></textarea></label><label>Success metric<input name="metric" maxlength="500" required></label><label>Target<input name="target" maxlength="500" required></label><label>Due<input type="date" name="due" required></label><label>Priority<select name="priority"><option>high</option><option>medium</option><option>low</option></select></label><label>Owner<select name="owner">'+''.join('<option value="'+str(x[0])+'">Member #'+str(x[0])+'</option>' for x in members)+'</select></label><button>Create plan</button></form></section>')
 for p in plans:
  event=c.execute("SELECT note FROM vx_growth_events42 WHERE workspace_id=? AND plan_id=? ORDER BY created DESC,rowid DESC LIMIT 1",(wid,p["id"])).fetchone()
  out.append('<section class="panel"><h2>'+e(p["title"])+'</h2><p>'+e(p["priority"])+' · '+e(p["status"])+' · Owner #'+str(p["owner"])+' · Due '+e(p["due"])+'</p><p>'+e(p["reason"])+'</p><p>Target: '+e(p["metric"])+' = '+e(p["target"])+'</p><p>Latest progress: '+e(event[0] if event else "None")+'</p>')
  if p["owner"]==uid and p["status"]!="completed":
   out.append('<form method="post" action="/growth-strategy"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="change"><input type="hidden" name="id" value="'+e(p["id"])+'"><label>Status<select name="status">'+''.join('<option value="'+v+'"'+(' selected' if v==p["status"] else '')+'>'+v+'</option>' for v in STATUSES)+'</select></label><label>Progress evidence<textarea name="note" maxlength="500" required></textarea></label><button>Record progress</button></form>')
  out.append('</section>')
 return ''.join(out)
