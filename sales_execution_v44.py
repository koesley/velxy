"""V44: Manual sales execution queue linked to workspace growth plans.

No outbound messages, automatic actions, revenue claims or external API calls.
"""
import html
import secrets
import time
import urllib.parse
from datetime import date
import business_os_v59 as bos
import growth_strategy_v42 as strategy

STAGES=("queued","contacted","awaiting_reply","won","lost")
KINDS=("call","email","meeting","proposal","other")

def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS vx_sales_actions44 (
 id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, plan_id TEXT NOT NULL,
 owner_id INTEGER NOT NULL, contact_label TEXT NOT NULL, action_kind TEXT NOT NULL,
 summary TEXT NOT NULL, due TEXT NOT NULL, stage TEXT NOT NULL,
 created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
 c.execute("CREATE INDEX IF NOT EXISTS vx_sales_actions44_queue ON vx_sales_actions44(workspace_id,stage,due)")
 c.execute("""CREATE TABLE IF NOT EXISTS vx_sales_events44 (
 id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, action_id TEXT NOT NULL,
 actor_id INTEGER NOT NULL, previous_stage TEXT NOT NULL,
 next_stage TEXT NOT NULL, note TEXT NOT NULL, created INTEGER NOT NULL)""")

def _text(value,limit,label):
 value=str(value).strip()
 if not value or len(value)>limit:raise ValueError(label+" is required (max "+str(limit)+" characters).")
 return value

def _due(value):
 try:
  if date.fromisoformat(value).isoformat()!=value:raise ValueError()
 except (ValueError,TypeError):raise ValueError("Invalid follow-up date.")
 return value

def create(c,uid,wid,plan_id,owner,contact,kind,summary,due):
 bos.core.access(c,uid,wid,write=True);setup(c)
 if kind not in KINDS:raise ValueError("Invalid action type.")
 contact=_text(contact,120,"Contact label")
 summary=_text(summary,500,"Action summary")
 due=_due(due)
 try:owner=int(owner)
 except (TypeError,ValueError):raise ValueError("Invalid owner.")
 if not c.execute("SELECT 1 FROM empire_members WHERE workspace_id=? AND user_id=?",(wid,owner)).fetchone():
  raise ValueError("Owner is not a member of this workspace.")
 if not c.execute("SELECT 1 FROM vx_growth_strategy42 WHERE workspace_id=? AND id=? AND status!='completed'",(wid,plan_id)).fetchone():
  raise ValueError("Choose an active strategy plan from this workspace.")
 identifier=secrets.token_hex(12);now=int(time.time())
 c.execute("INSERT INTO vx_sales_actions44 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
           (identifier,wid,plan_id,owner,contact,kind,summary,due,"queued",now,now))
 return identifier

def update(c,uid,wid,action_id,stage,note):
 bos.core.access(c,uid,wid,write=True);setup(c)
 if stage not in STAGES:raise ValueError("Invalid stage.")
 note=_text(note,500,"Evidence note")
 row=c.execute("SELECT owner_id,stage FROM vx_sales_actions44 WHERE workspace_id=? AND id=?",(wid,action_id)).fetchone()
 if not row or row[0]!=uid:raise ValueError("Only the assigned action owner may update this item.")
 if row[1] in ("won","lost"):raise ValueError("Closed actions cannot be changed.")
 if stage==row[1]:raise ValueError("Select a different stage.")
 now=int(time.time())
 c.execute("UPDATE vx_sales_actions44 SET stage=?,updated=? WHERE workspace_id=? AND id=? AND stage=?",
           (stage,now,wid,action_id,row[1]))
 c.execute("INSERT INTO vx_sales_events44 VALUES (?,?,?,?,?,?,?,?)",
           (secrets.token_hex(12),wid,action_id,uid,row[1],stage,note,now))

def snapshot(c,uid,wid,today=None):
 """Compute truthful all-record counts and prioritize urgent work in the bounded view."""
 bos.core.access(c,uid,wid);setup(c)
 today=today or date.today().isoformat()
 _due(today)
 counts=c.execute("""SELECT COUNT(*),
 SUM(CASE WHEN stage NOT IN ('won','lost') THEN 1 ELSE 0 END),
 SUM(CASE WHEN stage NOT IN ('won','lost') AND due<? THEN 1 ELSE 0 END),
 SUM(CASE WHEN stage NOT IN ('won','lost') AND due=? THEN 1 ELSE 0 END),
 SUM(CASE WHEN stage='won' THEN 1 ELSE 0 END),
 SUM(CASE WHEN stage='lost' THEN 1 ELSE 0 END)
 FROM vx_sales_actions44 WHERE workspace_id=?""",(today,today,wid)).fetchone()
 rows=c.execute("""SELECT a.id,a.plan_id,a.owner_id,a.contact_label,a.action_kind,
 a.summary,a.due,a.stage,p.title FROM vx_sales_actions44 a
 JOIN vx_growth_strategy42 p ON p.workspace_id=a.workspace_id AND p.id=a.plan_id
 WHERE a.workspace_id=? ORDER BY
 CASE WHEN a.stage IN ('won','lost') THEN 2
      WHEN a.due<=? THEN 0 ELSE 1 END,
 a.due,a.created DESC LIMIT 200""",(wid,today)).fetchall()
 keys=("id","plan_id","owner","contact","kind","summary","due","stage","plan")
 items=[dict(zip(keys,row)) for row in rows]
 for item in items:
  item["priority"]=("closed" if item["stage"] in ("won","lost") else
                    "overdue" if item["due"]<today else
                    "due_today" if item["due"]==today else "upcoming")
 total,opened,overdue,due_today,won,lost=(int(x or 0) for x in counts)
 return {"items":items,"total":total,"shown":len(items),"open":opened,
         "overdue":overdue,"due_today":due_today,
         "won_marked":won,"lost_marked":lost}

def team_triage(c,uid,wid,today=None):
 """Aggregate member workloads without leaking another workspace's actions."""
 bos.core.access(c,uid,wid);setup(c)
 today=today or date.today().isoformat()
 _due(today)
 rows=c.execute("""SELECT a.owner_id,COUNT(*),
 SUM(CASE WHEN a.due<? THEN 1 ELSE 0 END),
 SUM(CASE WHEN a.due=? THEN 1 ELSE 0 END)
 FROM vx_sales_actions44 a
 JOIN empire_members m ON m.workspace_id=a.workspace_id AND m.user_id=a.owner_id
 WHERE a.workspace_id=? AND a.stage NOT IN ('won','lost')
 GROUP BY a.owner_id ORDER BY 3 DESC,2 DESC,a.owner_id""",
 (today,today,wid)).fetchall()
 return [{"owner":int(r[0]),"open":int(r[1]),"overdue":int(r[2] or 0),
          "due_today":int(r[3] or 0)} for r in rows]

def render(c,uid,wid,csrf):
 bos.core.access(c,uid,wid);setup(c)
 e=lambda v:html.escape(str(v),quote=True)
 data=snapshot(c,uid,wid)
 team=team_triage(c,uid,wid)
 plans=strategy.analyze(c,uid,wid)
 active=[p for p in plans if p["status"]!="completed"]
 members=c.execute("SELECT user_id FROM empire_members WHERE workspace_id=? ORDER BY user_id",(wid,)).fetchall()
 out=['<section class="panel"><h1>Sales Execution Queue</h1><p>Track manual prospect follow-ups and link each action to a measurable growth strategy. No emails, calls, payments or external actions are sent automatically. Won/lost labels are user-reported, not verified revenue.</p>',
 '<p>Open: '+str(data["open"])+' · Overdue: '+str(data["overdue"])+' · Due today: '+str(data["due_today"])+' · Won-marked: '+str(data["won_marked"])+' · Lost-marked: '+str(data["lost_marked"])+'</p></section>']
 out.append('<section class="panel"><h2>Team follow-up workload</h2><p>Counts cover all open actions; urgent items appear first below.</p>'+(''.join('<p>Member #'+str(r["owner"])+': '+str(r["open"])+' open · '+str(r["overdue"])+' overdue · '+str(r["due_today"])+' due today</p>' for r in team) or '<p>No open follow-ups.</p>')+'</section>')
 if data["total"]>data["shown"]:
  out.append('<section class="panel"><p>Showing '+str(data["shown"])+' highest-priority actions of '+str(data["total"])+'. Summary and team totals include all actions.</p></section>')
 if active:
  out.append('<section class="panel"><h2>Schedule a customer action</h2><form method="post" action="/sales-execution"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="create"><label>Strategy<select name="plan_id">'+''.join('<option value="'+e(p["id"])+'">'+e(p["title"])+'</option>' for p in active)+'</select></label><label>Owner<select name="owner">'+''.join('<option value="'+str(m[0])+'"'+(' selected' if m[0]==uid else '')+'>Member #'+str(m[0])+'</option>' for m in members)+'</select></label><label>Prospect or customer label<input name="contact" maxlength="120" required></label><label>Action type<select name="kind">'+''.join('<option>'+e(k)+'</option>' for k in KINDS)+'</select></label><label>Next step<textarea name="summary" maxlength="500" required></textarea></label><label>Follow-up date<input type="date" name="due" required></label><button>Create follow-up</button></form></section>')
 else:out.append('<section class="panel"><p>Create an active <a href="/growth-strategy?w='+urllib.parse.quote(wid,safe='')+'">growth strategy plan</a> before adding customer follow-ups.</p></section>')
 for item in data["items"]:
  event=c.execute("SELECT note FROM vx_sales_events44 WHERE workspace_id=? AND action_id=? ORDER BY created DESC LIMIT 1",(wid,item["id"])).fetchone()
  out.append('<section class="panel"><h2>'+e(item["contact"])+'</h2><p>'+e(item["kind"])+' · '+e(item["priority"])+' · '+e(item["stage"])+' · due '+e(item["due"])+' · owner #'+str(item["owner"])+'</p><p>Strategy: '+e(item["plan"])+'</p><p>'+e(item["summary"])+'</p><p>Latest evidence: '+e(event[0] if event else "Not recorded")+'</p>')
  if item["owner"]==uid and item["stage"] not in ("won","lost"):
   out.append('<form method="post" action="/sales-execution"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="update"><input type="hidden" name="id" value="'+e(item["id"])+'"><label>Progress<select name="stage">'+''.join('<option value="'+e(s)+'"'+(' selected' if s==item["stage"] else '')+'>'+e(s)+'</option>' for s in STAGES)+'</select></label><label>Evidence note<textarea name="note" maxlength="500" required></textarea></label><button>Save progress</button></form>')
  out.append('</section>')
 return ''.join(out)
