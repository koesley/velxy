"""V44: Manual sales execution queue linked to workspace growth plans.

No outbound messages, automatic actions, revenue claims or external API calls.
"""
import html
import secrets
import time
import urllib.parse
from datetime import date, datetime, timezone
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
 c.execute("CREATE INDEX IF NOT EXISTS vx_sales_events44_timeline ON vx_sales_events44(workspace_id,action_id,created DESC,id DESC)")

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
 bos.core.access(c,uid,wid);setup(c)
 today=today or date.today().isoformat()
 rows=c.execute("""SELECT a.id,a.plan_id,a.owner_id,a.contact_label,a.action_kind,
 a.summary,a.due,a.stage,p.title FROM vx_sales_actions44 a
 JOIN vx_growth_strategy42 p ON p.workspace_id=a.workspace_id AND p.id=a.plan_id
 WHERE a.workspace_id=? ORDER BY
 CASE WHEN a.stage IN ('won','lost') THEN 1 ELSE 0 END,
 a.due,a.created DESC LIMIT 200""",(wid,)).fetchall()
 keys=("id","plan_id","owner","contact","kind","summary","due","stage","plan")
 items=[dict(zip(keys,row)) for row in rows]
 open_items=[r for r in items if r["stage"] not in ("won","lost")]
 return {"items":items,"open":len(open_items),
         "overdue":sum(r["due"]<today for r in open_items),
         "due_today":sum(r["due"]==today for r in open_items),
         "won_marked":sum(r["stage"]=="won" for r in items),
         "lost_marked":sum(r["stage"]=="lost" for r in items)}

def evidence_timeline(c,uid,wid,action_ids,limit_per_action=5):
 """Read bounded, workspace-isolated progress evidence for visible actions only."""
 bos.core.access(c,uid,wid);setup(c)
 if not isinstance(limit_per_action,int) or not 1<=limit_per_action<=10:
  raise ValueError("Invalid timeline limit.")
 if len(action_ids)>200:raise ValueError("Too many actions.")
 ids=list(dict.fromkeys(action_ids))
 if not ids:return {}
 if any(not isinstance(i,str) or len(i)>64 or not i for i in ids):
  raise ValueError("Invalid action identifier.")
 placeholders=",".join("?" for _ in ids)
 rows=c.execute("""SELECT e.action_id,e.previous_stage,e.next_stage,e.note,e.created
 FROM vx_sales_events44 e
 JOIN vx_sales_actions44 a ON a.id=e.action_id AND a.workspace_id=e.workspace_id
 WHERE e.workspace_id=? AND e.action_id IN ("""+placeholders+""")
 ORDER BY e.action_id,e.created DESC,e.id DESC""",(wid,*ids)).fetchall()
 result={i:[] for i in ids}
 for action_id,previous,next_stage,note,created in rows:
  if len(result[action_id])<limit_per_action:
   result[action_id].append({"previous":previous,"next":next_stage,"note":note,
    "when":datetime.fromtimestamp(created,timezone.utc).strftime("%Y-%m-%d %H:%M UTC")})
 return result

def render(c,uid,wid,csrf):
 bos.core.access(c,uid,wid);setup(c)
 e=lambda v:html.escape(str(v),quote=True)
 data=snapshot(c,uid,wid)
 plans=strategy.analyze(c,uid,wid)
 active=[p for p in plans if p["status"]!="completed"]
 history=evidence_timeline(c,uid,wid,[item["id"] for item in data["items"]])
 members=c.execute("SELECT user_id FROM empire_members WHERE workspace_id=? ORDER BY user_id",(wid,)).fetchall()
 out=['<section class="panel"><h1>Sales Execution Queue</h1><p>Track manual prospect follow-ups and link each action to a measurable growth strategy. No emails, calls, payments or external actions are sent automatically. Won/lost labels are user-reported, not verified revenue.</p>',
 '<p>Open: '+str(data["open"])+' · Overdue: '+str(data["overdue"])+' · Due today: '+str(data["due_today"])+' · Won-marked: '+str(data["won_marked"])+' · Lost-marked: '+str(data["lost_marked"])+'</p></section>']
 if active:
  out.append('<section class="panel"><h2>Schedule a customer action</h2><form method="post" action="/sales-execution"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="create"><label>Strategy<select name="plan_id">'+''.join('<option value="'+e(p["id"])+'">'+e(p["title"])+'</option>' for p in active)+'</select></label><label>Owner<select name="owner">'+''.join('<option value="'+str(m[0])+'"'+(' selected' if m[0]==uid else '')+'>Member #'+str(m[0])+'</option>' for m in members)+'</select></label><label>Prospect or customer label<input name="contact" maxlength="120" required></label><label>Action type<select name="kind">'+''.join('<option>'+e(k)+'</option>' for k in KINDS)+'</select></label><label>Next step<textarea name="summary" maxlength="500" required></textarea></label><label>Follow-up date<input type="date" name="due" required></label><button>Create follow-up</button></form></section>')
 else:out.append('<section class="panel"><p>Create an active <a href="/growth-strategy?w='+urllib.parse.quote(wid,safe='')+'">growth strategy plan</a> before adding customer follow-ups.</p></section>')
 for item in data["items"]:
  events=history.get(item["id"],[])
  out.append('<section class="panel"><h2>'+e(item["contact"])+'</h2><p>'+e(item["kind"])+' · '+e(item["stage"])+' · due '+e(item["due"])+' · owner #'+str(item["owner"])+'</p><p>Strategy: '+e(item["plan"])+'</p><p>'+e(item["summary"])+'</p><p>Latest evidence: '+e(event[0] if event else "Not recorded")+'</p>')
  if events:
   out.append('<details><summary>Progress history ('+str(len(events))+'+ most recent)</summary><ol>'+''.join('<li><time>'+e(v["when"])+'</time> · '+e(v["previous"])+' → '+e(v["next"])+' — '+e(v["note"])+'</li>' for v in events)+'</ol></details>')
  if item["owner"]==uid and item["stage"] not in ("won","lost"):
   out.append('<form method="post" action="/sales-execution"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="update"><input type="hidden" name="id" value="'+e(item["id"])+'"><label>Progress<select name="stage">'+''.join('<option value="'+e(s)+'"'+(' selected' if s==item["stage"] else '')+'>'+e(s)+'</option>' for s in STAGES)+'</select></label><label>Evidence note<textarea name="note" maxlength="500" required></textarea></label><button>Save progress</button></form>')
  out.append('</section>')
 return ''.join(out)
