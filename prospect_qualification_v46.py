"""Workspace-scoped prospect qualification and manual conversion handoff."""
import html,secrets,time,urllib.parse
from datetime import date
import business_os_v59 as bos
import sales_execution_v44 as sales
STAGES=("new","qualifying","qualified","disqualified","converted")
SOURCES=("referral","website","phone","event","other")
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS vx_prospects46(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,owner_id INTEGER NOT NULL,
 label TEXT NOT NULL,source TEXT NOT NULL,need TEXT NOT NULL,budget TEXT NOT NULL,
 urgency TEXT NOT NULL,stage TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
 c.execute("CREATE INDEX IF NOT EXISTS vx_prospects46_scope ON vx_prospects46(workspace_id,stage,updated)")
 c.execute("""CREATE TABLE IF NOT EXISTS vx_prospect_events46(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,prospect_id TEXT NOT NULL,
 actor_id INTEGER NOT NULL,previous TEXT NOT NULL,next TEXT NOT NULL,
 note TEXT NOT NULL,created INTEGER NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS vx_prospect_handoffs46(
 prospect_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,action_id TEXT NOT NULL,
 created INTEGER NOT NULL)""")
def required(value,limit,label):
 if not isinstance(value,str) or not 1<=len(value.strip())<=limit:raise ValueError(label+" must be 1-"+str(limit)+" characters.")
 return value.strip()
def member(c,wid,uid):
 if not c.execute("SELECT 1 FROM empire_members WHERE workspace_id=? AND user_id=?",(wid,uid)).fetchone():raise ValueError("Assigned owner is not a workspace member.")
def create(c,uid,wid,owner,label,source,need,budget,urgency):
 bos.core.access(c,uid,wid,write=True);setup(c)
 try:owner=int(owner)
 except (ValueError,TypeError):raise ValueError("Invalid owner.")
 member(c,wid,owner)
 if source not in SOURCES:raise ValueError("Invalid source.")
 if urgency not in ("low","medium","high"):raise ValueError("Invalid urgency.")
 label=required(label,120,"Prospect label");need=required(need,500,"Customer need")
 budget=required(budget,120,"Budget indication")
 identifier=secrets.token_hex(12);now=int(time.time())
 c.execute("INSERT INTO vx_prospects46 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
           (identifier,wid,owner,label,source,need,budget,urgency,"new",now,now))
 return identifier
def change(c,uid,wid,identifier,stage,note):
 bos.core.access(c,uid,wid,write=True);setup(c)
 row=c.execute("SELECT owner_id,stage FROM vx_prospects46 WHERE workspace_id=? AND id=?",(wid,identifier)).fetchone()
 if not row or row[0]!=uid:raise ValueError("Only the assigned owner can update this prospect.")
 if stage not in STAGES or stage==row[1] or row[1] in ("converted","disqualified"):raise ValueError("Invalid stage transition.")
 if stage=="converted":raise ValueError("Use a strategy-linked handoff to mark a prospect converted.")
 note=required(note,500,"Progress evidence");now=int(time.time())
 result=c.execute("UPDATE vx_prospects46 SET stage=?,updated=? WHERE workspace_id=? AND id=? AND stage=?",
                  (stage,now,wid,identifier,row[1]))
 count=result.cursor.rowcount if hasattr(result,"cursor") else result.rowcount
 if count!=1:raise ValueError("Prospect changed; refresh before updating.")
 c.execute("INSERT INTO vx_prospect_events46 VALUES (?,?,?,?,?,?,?,?)",
           (secrets.token_hex(12),wid,identifier,uid,row[1],stage,note,now))
def handoff(c,uid,wid,identifier,plan_id,kind,summary,due):
 bos.core.access(c,uid,wid,write=True);setup(c)
 row=c.execute("SELECT owner_id,label,stage FROM vx_prospects46 WHERE workspace_id=? AND id=?",(wid,identifier)).fetchone()
 if not row or row[0]!=uid:raise ValueError("Only the prospect owner can create a handoff.")
 if row[2]!="qualified":raise ValueError("Only qualified prospects can be handed off.")
 if c.execute("SELECT 1 FROM vx_prospect_handoffs46 WHERE workspace_id=? AND prospect_id=?",(wid,identifier)).fetchone():raise ValueError("Already handed off.")
 action_id=sales.create(c,uid,wid,plan_id,uid,row[1],kind,summary,due)
 now=int(time.time())
 result=c.execute("UPDATE vx_prospects46 SET stage='converted',updated=? WHERE workspace_id=? AND id=? AND stage='qualified'",
                  (now,wid,identifier))
 count=result.cursor.rowcount if hasattr(result,"cursor") else result.rowcount
 if count!=1:raise ValueError("Prospect changed; retry.")
 c.execute("INSERT INTO vx_prospect_handoffs46 VALUES (?,?,?,?)",(identifier,wid,action_id,now))
 c.execute("INSERT INTO vx_prospect_events46 VALUES (?,?,?,?,?,?,?,?)",
           (secrets.token_hex(12),wid,identifier,uid,"qualified","converted","Created manual sales follow-up "+action_id,now))
 return action_id
def snapshot(c,uid,wid):
 bos.core.access(c,uid,wid);setup(c)
 rows=c.execute("""SELECT id,owner_id,label,source,need,budget,urgency,stage,created
 FROM vx_prospects46 WHERE workspace_id=? ORDER BY updated DESC,id LIMIT 200""",(wid,)).fetchall()
 keys=("id","owner","label","source","need","budget","urgency","stage","created")
 items=[dict(zip(keys,r)) for r in rows]
 counts=dict(c.execute("SELECT stage,count(*) FROM vx_prospects46 WHERE workspace_id=? GROUP BY stage",(wid,)).fetchall())
 return {"items":items,"counts":counts,"total":sum(counts.values())}
def render(c,uid,wid,csrf):
 bos.core.access(c,uid,wid);setup(c)
 e=lambda v:html.escape(str(v),quote=True)
 data=snapshot(c,uid,wid)
 members=c.execute("SELECT user_id FROM empire_members WHERE workspace_id=? ORDER BY user_id",(wid,)).fetchall()
 plans=c.execute("SELECT id,title FROM vx_growth_strategy42 WHERE workspace_id=? AND status!='completed' ORDER BY created DESC LIMIT 150",(wid,)).fetchall()
 out=['<section class="panel"><h1>Prospect Qualification</h1><p>Track inbound leads, customer needs, budget indications, urgency, owner assignments, qualification decisions and manual sales handoffs. No messages are sent and a handoff is not a verified sale.</p><p>Total: '+str(data["total"])+' · '+ ' · '.join(e(s)+': '+str(data["counts"].get(s,0)) for s in STAGES)+'</p></section>',
 '<section class="panel"><h2>Add prospect</h2><form method="post" action="/prospect-qualification"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="create"><label>Prospect label<input name="label" maxlength="120" required></label><label>Source<select name="source">'+''.join('<option>'+e(s)+'</option>' for s in SOURCES)+'</select></label><label>Customer need<textarea name="need" maxlength="500" required></textarea></label><label>Budget indication<input name="budget" maxlength="120" required></label><label>Urgency<select name="urgency"><option>low</option><option>medium</option><option>high</option></select></label><label>Owner<select name="owner">'+''.join('<option value="'+str(m[0])+'"'+(' selected' if m[0]==uid else '')+'>Member #'+str(m[0])+'</option>' for m in members)+'</select></label><button>Add prospect</button></form></section>']
 for p in data["items"]:
  out.append('<section class="panel"><h2>'+e(p["label"])+'</h2><p>'+e(p["stage"])+' · '+e(p["source"])+' · '+e(p["urgency"])+' urgency · owner #'+str(p["owner"])+'</p><p>Need: '+e(p["need"])+'</p><p>Budget indication (unverified): '+e(p["budget"])+'</p>')
  if p["owner"]==uid and p["stage"] not in ("converted","disqualified"):
   out.append('<form method="post" action="/prospect-qualification"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="change"><input type="hidden" name="id" value="'+e(p["id"])+'"><label>Stage<select name="stage">'+''.join('<option value="'+e(s)+'"'+(' selected' if s==p["stage"] else '')+'>'+e(s)+'</option>' for s in STAGES if s!="converted")+'</select></label><label>Evidence<textarea name="note" maxlength="500" required></textarea></label><button>Record qualification</button></form>')
   if p["stage"]=="qualified" and plans:
    out.append('<form method="post" action="/prospect-qualification"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="handoff"><input type="hidden" name="id" value="'+e(p["id"])+'"><h3>Hand off to sales queue</h3><label>Growth plan<select name="plan_id">'+''.join('<option value="'+e(x[0])+'">'+e(x[1])+'</option>' for x in plans)+'</select></label><label>Action type<select name="kind">'+''.join('<option>'+e(k)+'</option>' for k in sales.KINDS)+'</select></label><label>Next step<textarea name="summary" maxlength="500" required></textarea></label><label>Follow-up date<input type="date" name="due" required></label><button>Create sales follow-up</button></form>')
  out.append('</section>')
 if data["total"]>len(data["items"]):out.append('<section class="panel"><p>Showing the most recently updated 200 prospects.</p></section>')
 return ''.join(out)
