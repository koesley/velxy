"""V22 Autonomy: deterministic tenant-scoped record-triggered workflow pilot."""
import html,json,secrets,time
import empire_v19,genesis_prime_v20 as prime

def setup(c):
 c.execute("CREATE TABLE IF NOT EXISTS autonomy_rules(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,app_id TEXT NOT NULL,name TEXT NOT NULL,field TEXT NOT NULL,threshold REAL NOT NULL,status TEXT NOT NULL CHECK(status IN ('draft','active','disabled')),created_by INTEGER NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE INDEX IF NOT EXISTS autonomy_rules_tenant ON autonomy_rules(workspace_id,app_id)")
 c.execute("CREATE TABLE IF NOT EXISTS autonomy_tasks(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,app_id TEXT NOT NULL,rule_id TEXT NOT NULL,record_id TEXT NOT NULL,title TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(rule_id,record_id))")
 c.execute("CREATE TABLE IF NOT EXISTS autonomy_events(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,rule_id TEXT NOT NULL,record_id TEXT NOT NULL,outcome TEXT NOT NULL,created INTEGER NOT NULL)")

def create(c,uid,wid,aid,name,field,threshold):
 prime.app(c,uid,wid,aid,True)
 row=prime.app(c,uid,wid,aid)
 if row[3]!='published':raise ValueError('Publish the application first')
 schema=json.loads(row[2]);numeric={f['name'] for f in schema if f['type']=='number'}
 if field not in numeric:raise ValueError('Select a numeric application field')
 name=name.strip()
 if not 2<=len(name)<=90:raise ValueError('Rule name must be 2–90 characters')
 try:threshold=float(threshold)
 except (ValueError,TypeError):raise ValueError('Invalid threshold')
 import math
 if not math.isfinite(threshold) or abs(threshold)>1e9:raise ValueError('Threshold outside permitted range')
 rid=secrets.token_hex(12)
 c.execute('INSERT INTO autonomy_rules VALUES(?,?,?,?,?,?,?,?,?)',(rid,wid,aid,name,field,threshold,'draft',uid,int(time.time())))
 return rid

def rule(c,uid,wid,rid):
 prime.permission(c,uid,wid)
 r=c.execute('SELECT id,workspace_id,app_id,name,field,threshold,status FROM autonomy_rules WHERE id=? AND workspace_id=?',(rid,wid)).fetchone()
 if not r:raise ValueError('Workflow not found in this workspace')
 prime.app(c,uid,wid,r[2])
 return r

def activate(c,uid,wid,rid):
 if empire_v19.role(c,uid,wid)!='owner':raise ValueError('Only workspace owners may activate workflows')
 r=rule(c,uid,wid,rid)
 if r[6]!='draft':raise ValueError('Only draft workflows may be activated')
 c.execute("UPDATE autonomy_rules SET status='active' WHERE id=? AND workspace_id=?",(rid,wid))

def disable(c,uid,wid,rid):
 if empire_v19.role(c,uid,wid)!='owner':raise ValueError('Only owners may disable workflows')
 rule(c,uid,wid,rid)
 c.execute("UPDATE autonomy_rules SET status='disabled' WHERE id=? AND workspace_id=?",(rid,wid))

def evaluate(c,uid,wid,rid,record_id,execute=False):
 r=rule(c,uid,wid,rid)
 if execute:
  prime.permission(c,uid,wid,True)
  if r[6]!='active':raise ValueError('Workflow is not active')
 row=c.execute('SELECT data_json FROM prime_records WHERE id=? AND app_id=? AND workspace_id=?',(record_id,r[2],wid)).fetchone()
 if not row:raise ValueError('Record not found in this workspace/application')
 data=json.loads(row[0]);raw=data.get(r[4],'')
 try:value=float(raw)
 except (ValueError,TypeError):return 'skipped: missing/non-numeric value'
 import math
 if not math.isfinite(value):return 'skipped: non-finite value'
 if value>=r[5]:return 'skipped: threshold not met'
 if not execute:return 'would create task (dry run)'
 title='Review low '+r[4]+' for record '+record_id[:8]
 c.execute('INSERT OR IGNORE INTO autonomy_tasks VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,r[2],rid,record_id,title,int(time.time())))
 outcome='task created' if c.execute('SELECT changes()').fetchone()[0] else 'skipped: task already exists'
 c.execute('INSERT INTO autonomy_events VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wid,rid,record_id,outcome,int(time.time())))
 return outcome

def on_record_created(c,uid,wid,aid,record_id):
 # Called within the original record transaction; never runs unapproved or cross-tenant rules.
 for (rid,) in c.execute("SELECT id FROM autonomy_rules WHERE workspace_id=? AND app_id=? AND status='active' LIMIT 30",(wid,aid)).fetchall():
  evaluate(c,uid,wid,rid,record_id,True)

def render(c,uid,csrf,wid='',message=''):
 esc=lambda x:html.escape(str(x),quote=True)
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not wid and ws:wid=ws[0][0]
 if wid:prime.permission(c,uid,wid)
 h=['<section class="panel"><h1>⚙ AUTONOMY V22</h1><p>Deterministic low-stock workflow pilot. Only approved numeric threshold rules; no arbitrary AI code, external notifications, or scheduled jobs.</p><p>Choose workspace: '+''.join('<a style="margin-right:12px" href="/autonomy?w='+esc(w)+'">'+esc(n)+'</a>' for w,n,_ in ws)+'</p></section>']
 if message:h.append('<section class="panel">'+esc(message)+'</section>')
 if not wid:return ''.join(h)
 role=prime.permission(c,uid,wid)
 apps=c.execute("SELECT id,name,schema_json FROM prime_apps WHERE workspace_id=? AND status='published'",(wid,)).fetchall()
 if role in ('owner','editor'):
  h.append('<section class="panel"><h2>New low-stock workflow</h2><p>Choose a published application and its numeric field. Field options are shown below.</p>')
  for aid,name,schema in apps:
   numeric=[f['name'] for f in json.loads(schema) if f['type']=='number']
   if not numeric:continue
   h.append('<form method="post" action="/autonomy"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="app" value="'+esc(aid)+'"><input type="hidden" name="action" value="create"><h3>'+esc(name)+'</h3><label>Rule name<input name="name" maxlength="90" required></label><label>Numeric field<select name="field">'+''.join('<option value="'+esc(f)+'">'+esc(f)+'</option>' for f in numeric)+'</select></label><label>Create task when value is below<input name="threshold" type="number" step="any" required></label><button>Create draft</button></form>')
  h.append('</section>')
 rules=c.execute('SELECT id,app_id,name,field,threshold,status FROM autonomy_rules WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()
 h.append('<section class="panel"><h2>Workflows</h2>')
 for rid,aid,name,field,threshold,status in rules:
  h.append('<div style="border-top:1px solid #655777;padding:12px"><strong>'+esc(name)+'</strong> — '+esc(status)+'<p>When '+esc(field)+' &lt; '+esc(threshold)+', create a task once per record.</p>')
  if role=='owner' and status=='draft':h.append(_form(csrf,wid,'activate',rid,'Approve and activate'))
  if role=='owner' and status=='active':h.append(_form(csrf,wid,'disable',rid,'Disable'))
  records=c.execute('SELECT id FROM prime_records WHERE workspace_id=? AND app_id=? ORDER BY created DESC LIMIT 10',(wid,aid)).fetchall()
  for (record_id,) in records:
   result=evaluate(c,uid,wid,rid,record_id,False)
   h.append('<p>Record '+esc(record_id[:8])+': '+esc(result)+'</p>')
   if status=='active' and role in ('owner','editor'):h.append(_form(csrf,wid,'run',rid,'Run for '+record_id[:8],record_id))
  h.append('</div>')
 h.append('</section><section class="panel"><h2>Generated tasks</h2>')
 tasks=c.execute('SELECT title,created FROM autonomy_tasks WHERE workspace_id=? ORDER BY created DESC LIMIT 50',(wid,)).fetchall()
 for title,created in tasks:h.append('<p>'+esc(title)+'</p>')
 h.append('</section><section class="panel"><h2>Execution history</h2>')
 for outcome,record_id in c.execute('SELECT outcome,record_id FROM autonomy_events WHERE workspace_id=? ORDER BY created DESC LIMIT 50',(wid,)).fetchall():h.append('<p>'+esc(outcome)+' — '+esc(record_id[:8])+'</p>')
 return ''.join(h)+'</section>'

def _form(csrf,wid,action,rid,label,record=''):
 esc=lambda x:html.escape(str(x),quote=True)
 return '<form method="post" action="/autonomy"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="rule" value="'+esc(rid)+'"><input type="hidden" name="record" value="'+esc(record)+'"><input type="hidden" name="action" value="'+esc(action)+'"><button>'+esc(label)+'</button></form>'
