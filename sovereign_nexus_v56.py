"""Workflow Nexus: local, workspace-scoped visual planning and operational inbox.
No background scheduler, automatic actions, or external requests.
"""
import html, json, secrets, time, urllib.parse
import sovereign_v56 as core
import sovereign_workflows_v56 as plans
import sovereign_workflow_runtime_v56 as runtime

RULES=('always','on_success','on_blocked','manual_review')
def init(c):
 plans.init(c);runtime.init(c)
 c.execute("CREATE TABLE IF NOT EXISTS sv56_nexus_rules(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,workflow_id TEXT NOT NULL,step_index INTEGER NOT NULL,condition TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,UNIQUE(workspace_id,workflow_id,step_index))")
 c.execute("CREATE TABLE IF NOT EXISTS sv56_nexus_notifications(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,run_id TEXT NOT NULL,kind TEXT NOT NULL,message TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0,created INTEGER NOT NULL)")
 c.execute('CREATE INDEX IF NOT EXISTS sv56_nexus_notifications_scope ON sv56_nexus_notifications(workspace_id,seen,created)')
 c.execute("CREATE TABLE IF NOT EXISTS sv56_nexus_components(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,name TEXT NOT NULL,steps_json TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE TABLE IF NOT EXISTS sv56_nexus_schedules(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,workflow_id TEXT NOT NULL,run_at TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('planned','cancelled')),created_by INTEGER NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE TABLE IF NOT EXISTS sv56_nexus_branch_reviews(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,run_id TEXT NOT NULL,step_index INTEGER NOT NULL,outcome TEXT NOT NULL,decision TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL)")
 c.execute('CREATE INDEX IF NOT EXISTS sv56_nexus_schedules_scope ON sv56_nexus_schedules(workspace_id,run_at)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_nexus_dispatches(schedule_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,run_id TEXT NOT NULL,dispatched_by INTEGER NOT NULL,dispatched_at INTEGER NOT NULL)')

def set_rule(c,uid,wid,wfid,index,condition):
 core.access(c,uid,wid,write=True);init(c)
 row=plans._row(c,wid,wfid)
 if row[2]!='draft':raise ValueError('Only draft workflows can be configured')
 try:index=int(index)
 except (TypeError,ValueError):raise ValueError('Invalid step index')
 steps=json.loads(row[3])
 if not 0<=index<len(steps):raise ValueError('Step index out of range')
 if condition not in RULES:raise ValueError('Unsupported condition')
 if index==0 and condition!='always':raise ValueError('First step must be unconditional')
 with c:
  c.execute('INSERT INTO sv56_nexus_rules VALUES(?,?,?,?,?,?,?) ON CONFLICT(workspace_id,workflow_id,step_index) DO UPDATE SET condition=excluded.condition,created_by=excluded.created_by,created=excluded.created',(secrets.token_hex(12),wid,wfid,index,condition,uid,int(time.time())))
  core.audit(c,uid,wid,'nexus_rule_set',wfid)

def notify(c,uid,wid,rid,kind,message):
 core.access(c,uid,wid,write=True);init(c)
 if not c.execute('SELECT 1 FROM sv56_workflow_runs WHERE workspace_id=? AND id=?',(wid,rid)).fetchone():raise ValueError('Run not found')
 if kind not in ('checkpoint','blocked','approval','deadline','review'):raise ValueError('Invalid notification kind')
 message=message.strip()
 if not 1<=len(message)<=300:raise ValueError('Notification must be 1–300 characters')
 with c:
  c.execute('INSERT INTO sv56_nexus_notifications VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,rid,kind,message,0,int(time.time())))
  core.audit(c,uid,wid,'nexus_notification_added',rid)

def mark_seen(c,uid,wid,nid):
 core.access(c,uid,wid,write=True);init(c)
 with c:
  result=c.execute('UPDATE sv56_nexus_notifications SET seen=1 WHERE workspace_id=? AND id=?',(wid,nid))
  if not result.rowcount:raise ValueError('Notification not found')
  core.audit(c,uid,wid,'nexus_notification_seen',nid)

def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 wf=plans.overview(c,uid,wid)['workflows'];runs=runtime.overview(c,uid,wid)['runs']
 rules={}
 for wfid,index,condition in c.execute('SELECT workflow_id,step_index,condition FROM sv56_nexus_rules WHERE workspace_id=?',(wid,)):
  rules.setdefault(wfid,{})[index]=condition
 for w in wf:
  w['canvas']=[{'index':i,'key':s['key'],'label':s['label'],'condition':rules.get(w['id'],{}).get(i,'always')} for i,s in enumerate(w['steps'])]
 notices=[{'id':nid,'run_id':rid,'kind':kind,'message':msg,'seen':bool(seen),'created':ts} for nid,rid,kind,msg,seen,ts in c.execute('SELECT id,run_id,kind,message,seen,created FROM sv56_nexus_notifications WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 alerts=[];now=int(time.time())
 for r in runs:
  if r['status'] in ('active','paused'):
   if any(t['status']=='blocked' for t in r['tasks']):alerts.append({'run_id':r['id'],'kind':'blocked','message':r['name']+' has a blocked checkpoint'})
   if r['due_date']:
    import datetime
    try:
     if datetime.date.fromisoformat(r['due_date'])<datetime.date.fromtimestamp(now):alerts.append({'run_id':r['id'],'kind':'deadline','message':r['name']+' is past its recorded due date'})
    except ValueError:pass
   pending=next((t for t in r['tasks'] if t['status']!='done'),None)
   if pending and pending['key']=='approval':alerts.append({'run_id':r['id'],'kind':'approval','message':r['name']+' is waiting for owner approval'})
 return {'workspace_id':wid,'role':role,'workflows':wf,'runs':runs,'notifications':notices,'live_attention':alerts,'stats':{'plans':len(wf),'runs':len(runs),'attention':len(alerts),'unread':sum(not n['seen'] for n in notices)},'limitations':['Conditions are visual planning annotations, not executable branches.','Notifications are local records and computed alerts, not push/email messages.','No scheduler or autonomous external actions.']}

def render(c,uid,wid,csrf):
 data=overview(c,uid,wid);h=lambda v:html.escape(str(v),quote=True)
 editable=data['role'] in ('owner','editor');out=[]
 for w in data['workflows']:
  nodes=[]
  for step in w['canvas']:
   opts=''.join('<option value="'+r+'"'+(' selected' if step['condition']==r else '')+'>'+r.replace('_',' ').title()+'</option>' for r in RULES)
   form=('<form method="post" action="/sovereign-nexus-v56"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="workflow" value="'+h(w['id'])+'"><input type="hidden" name="index" value="'+str(step['index'])+'"><select name="condition" aria-label="Condition for '+h(step['label'])+'">'+opts+'</select><button name="action" value="rule">Save rule</button></form>') if editable and w['status']=='draft' else '<small>'+h(step['condition'])+'</small>'
   nodes.append('<div class="nx-node"><span class="nx-step">'+str(step['index']+1)+'</span><b>'+h(step['label'])+'</b>'+form+'</div>')
  out.append('<article class="nx-card"><div class="nx-head"><h3>'+h(w['name'])+'</h3><span>'+h(w['status'])+'</span></div><div class="nx-canvas">'+''.join(nodes)+'</div><a href="/sovereign-workflows-v56?w='+urllib.parse.quote(wid,safe='')+'">Edit workflow blueprint →</a></article>')
 attention=''.join('<div class="nx-alert"><b>'+h(a['kind']).upper()+'</b> '+h(a['message'])+'</div>' for a in data['live_attention']) or '<p>No current computed attention items.</p>'
 notices=''
 for n in data['notifications'][:30]:
  form=('<form method="post" action="/sovereign-nexus-v56"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="notification" value="'+h(n['id'])+'"><button name="action" value="seen">Mark read</button></form>') if editable and not n['seen'] else ''
  notices+='<div class="nx-notice"><b>'+h(n['kind'])+'</b> '+h(n['message'])+form+'</div>'
 return '<section class="nx-hero"><span class="nx-kicker">VELXTRIA · WORKFLOW NEXUS</span><h1>Design the logic. See the whole operation.</h1><p>Visual planning, rule annotations, operational attention, and a local notification inbox—without unapproved automation.</p><div class="nx-stats">'+''.join('<div><strong>'+str(value)+'</strong><span>'+h(key.title())+'</span></div>' for key,value in data['stats'].items())+'</div></section><section class="nx-grid"><div><h2>Workflow canvas</h2>'+''.join(out)+'</div><aside><div class="nx-card"><h2>Needs attention</h2>'+attention+'</div><div class="nx-card"><h2>Notification inbox</h2>'+(notices or '<p>No saved notifications yet.</p>')+'</div></aside></section><p class="nx-disclaimer">Rule annotations are non-executable. Checkpoints remain manual and owner approvals remain mandatory. No automatic outbound actions or scheduled jobs.</p>'


# Workflow Nexus 2: reusable step recipes, explicit schedule intentions, and
# conditional checkpoint guidance. All operations are local and human-operated.
def save_component(c,uid,wid,name,steps):
 core.access(c,uid,wid,write=True);init(c)
 name=str(name).strip()
 if not 1<=len(name)<=90:raise ValueError('Component name must be 1–90 characters')
 if isinstance(steps,str):steps=[x.strip() for x in steps.split(',') if x.strip()]
 if not isinstance(steps,list) or not 1<=len(steps)<=12 or any(x not in plans.STEPS for x in steps):raise ValueError('Choose 1–12 valid workflow step keys')
 cid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_nexus_components VALUES(?,?,?,?,?,?)',(cid,wid,name,json.dumps(steps),uid,int(time.time())))
  core.audit(c,uid,wid,'nexus_component_created',cid)
 return cid

def plan_schedule(c,uid,wid,wfid,run_at):
 import datetime
 core.access(c,uid,wid,write=True);init(c)
 w=plans._row(c,wid,wfid)
 if w[2]!='approved':raise ValueError('Approve the blueprint before scheduling')
 try:dt=datetime.datetime.strptime(run_at,'%Y-%m-%dT%H:%M')
 except (TypeError,ValueError):raise ValueError('Use YYYY-MM-DDTHH:MM local time')
 if dt<=datetime.datetime.now() or dt>datetime.datetime.now()+datetime.timedelta(days=366):raise ValueError('Schedule must be within the next 366 days')
 sid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_nexus_schedules VALUES(?,?,?,?,?,?,?)',(sid,wid,wfid,run_at,'planned',uid,int(time.time())))
  core.audit(c,uid,wid,'nexus_schedule_planned',sid)
 return sid

def cancel_schedule(c,uid,wid,sid):
 core.access(c,uid,wid,write=True);init(c)
 with c:
  result=c.execute("UPDATE sv56_nexus_schedules SET status='cancelled' WHERE id=? AND workspace_id=? AND status='planned' AND NOT EXISTS(SELECT 1 FROM sv56_nexus_dispatches WHERE schedule_id=?)",(sid,wid,sid))
  if not result.rowcount:raise ValueError('Active schedule not found')
  core.audit(c,uid,wid,'nexus_schedule_cancelled',sid)

def dispatch_due(c,uid,wid,sid):
 """Explicitly start a due approved plan once; never background dispatch."""
 import datetime
 core.access(c,uid,wid,write=True);init(c)
 with c:
  row=c.execute('SELECT workflow_id,run_at,status FROM sv56_nexus_schedules WHERE id=? AND workspace_id=?',(sid,wid)).fetchone()
  if not row:raise ValueError('Schedule not found')
  prior=c.execute('SELECT run_id FROM sv56_nexus_dispatches WHERE schedule_id=? AND workspace_id=?',(sid,wid)).fetchone()
  if prior:return prior[0]
  if row[2]!='planned':raise ValueError('Schedule is not planned')
  due=datetime.datetime.strptime(row[1],'%Y-%m-%dT%H:%M')
  if due>datetime.datetime.now():raise ValueError('Scheduled time has not arrived')
  # runtime.start checks that the blueprint is still approved and has an approval gate.
  rid=runtime.start(c,uid,wid,row[0])
  c.execute('INSERT INTO sv56_nexus_dispatches VALUES(?,?,?,?,?)',(sid,wid,rid,uid,int(time.time())))
  c.execute('INSERT INTO sv56_nexus_notifications VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,rid,'checkpoint','Scheduled workflow is ready for human checkpoints',0,int(time.time())))
  core.audit(c,uid,wid,'nexus_schedule_dispatched',sid)
  return rid

def due_queue(c,uid,wid):
 import datetime
 core.access(c,uid,wid);init(c)
 now=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M')
 return [{'id':sid,'workflow_id':wfid,'run_at':at} for sid,wfid,at in c.execute("SELECT s.id,s.workflow_id,s.run_at FROM sv56_nexus_schedules s LEFT JOIN sv56_nexus_dispatches d ON d.schedule_id=s.id WHERE s.workspace_id=? AND s.status='planned' AND s.run_at<=? AND d.schedule_id IS NULL ORDER BY s.run_at,s.id LIMIT 50",(wid,now))]

def review_branch(c,uid,wid,rid,step_index,outcome):
 core.access(c,uid,wid,write=True);init(c)
 if outcome not in ('success','blocked','manual_review'):raise ValueError('Invalid observed outcome')
 run=runtime._run(c,wid,rid)
 if run[2]!='active':raise ValueError('Run must be active')
 try:step_index=int(step_index)
 except (TypeError,ValueError):raise ValueError('Invalid step index')
 tasks=c.execute('SELECT ordinal,status FROM sv56_workflow_tasks WHERE workspace_id=? AND run_id=? ORDER BY ordinal',(wid,rid)).fetchall()
 if not 0<=step_index<len(tasks):raise ValueError('Step index out of range')
 if step_index and any(status!='done' for _,status in tasks[:step_index]):raise ValueError('Previous checkpoints must be complete')
 condition=c.execute('SELECT condition FROM sv56_nexus_rules WHERE workspace_id=? AND workflow_id=? AND step_index=?',(wid,run[1],step_index)).fetchone()
 condition=condition[0] if condition else 'always'
 mapping={'always':'eligible','on_success':'eligible' if outcome=='success' else 'hold','on_blocked':'eligible' if outcome=='blocked' else 'hold','manual_review':'requires owner review'}
 decision=mapping[condition]
 if condition=='manual_review':core.access(c,uid,wid,owner=True)
 with c:
  c.execute('INSERT INTO sv56_nexus_branch_reviews VALUES(?,?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,rid,step_index,outcome,decision,uid,int(time.time())))
  core.audit(c,uid,wid,'nexus_branch_reviewed',rid)
 return decision

def advanced_overview(c,uid,wid):
 data=overview(c,uid,wid)
 data['components']=[{'id':cid,'name':name,'steps':json.loads(steps)} for cid,name,steps in c.execute('SELECT id,name,steps_json FROM sv56_nexus_components WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 50',(wid,))]
 data['schedules']=[{'id':sid,'workflow_id':wf,'run_at':at,'status':('dispatched' if c.execute('SELECT 1 FROM sv56_nexus_dispatches WHERE schedule_id=? AND workspace_id=?',(sid,wid)).fetchone() else status)} for sid,wf,at,status in c.execute('SELECT id,workflow_id,run_at,status FROM sv56_nexus_schedules WHERE workspace_id=? ORDER BY run_at,id LIMIT 100',(wid,))]
 data['branch_reviews']=[{'run_id':rid,'step_index':idx,'outcome':outcome,'decision':decision,'created':ts} for rid,idx,outcome,decision,ts in c.execute('SELECT run_id,step_index,outcome,decision,created FROM sv56_nexus_branch_reviews WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 50',(wid,))]
 data['due_queue']=due_queue(c,uid,wid)
 data['dispatches']=[{'schedule_id':sid,'run_id':rid,'dispatched_at':ts} for sid,rid,ts in c.execute('SELECT schedule_id,run_id,dispatched_at FROM sv56_nexus_dispatches WHERE workspace_id=? ORDER BY dispatched_at DESC LIMIT 50',(wid,))]
 data['limitations']+=['Schedules can be dispatched only by an authorized user after their due time; no background runner or automatic external action.','Branch decisions provide human-reviewed guidance, not autonomous checkpoint changes.','Reusable components are stored recipes, not automatically injected into approved workflows.']
 return data

def render_advanced(c,uid,wid,csrf):
 data=advanced_overview(c,uid,wid);h=lambda x:html.escape(str(x),quote=True)
 base='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
 editable=data['role'] in ('owner','editor')
 components=''.join('<li><b>'+h(x['name'])+'</b> · '+h(' → '.join(x['steps']))+'</li>' for x in data['components']) or '<li>No reusable components yet</li>'
 schedules=''.join('<li>'+h(x['run_at'])+' · '+h(x['status'])+' · '+h(x['workflow_id'])+('<form method="post" action="/sovereign-nexus-v56">'+base+'<input type="hidden" name="schedule" value="'+h(x['id'])+'"><button name="action" value="cancel_schedule">Cancel</button></form>' if editable and x['status']=='planned' else '')+'</li>' for x in data['schedules']) or '<li>No planned reminders</li>'
 due_items=''.join('<li>'+h(x['run_at'])+' · '+h(x['workflow_id'])+('<form method="post" action="/sovereign-nexus-v56">'+base+'<input type="hidden" name="schedule" value="'+h(x['id'])+'"><button name="action" value="dispatch">Start due run</button></form>' if editable else '')+'</li>' for x in data['due_queue']) or '<li>No workflows due for manual dispatch</li>'
 reviews=''.join('<li>'+h(x['run_id'])+' · step '+str(x['step_index']+1)+' · '+h(x['outcome'])+' → '+h(x['decision'])+'</li>' for x in data['branch_reviews'][:15]) or '<li>No branch reviews yet</li>'
 forms=''
 if editable:
  forms='<div class="nx-card"><h3>Save reusable step recipe</h3><form method="post" action="/sovereign-nexus-v56">'+base+'<input name="name" maxlength="90" required placeholder="Recipe name"><input name="steps" required placeholder="genesis,approval,memory"><button name="action" value="component">Save recipe</button></form><p>Valid keys: '+h(', '.join(plans.STEPS))+'</p></div>'
  options=''.join('<option value="'+h(x['id'])+'">'+h(x['name'])+'</option>' for x in data['workflows'] if x['status']=='approved')
  forms+='<div class="nx-card"><h3>Plan a future run</h3><form method="post" action="/sovereign-nexus-v56">'+base+'<select name="workflow" required>'+options+'</select><input type="datetime-local" name="run_at" required><button name="action" value="schedule">Save reminder</button></form><p>Due schedules can be started by a person from the due queue; no background worker.</p></div>'
  runs=''.join('<option value="'+h(x['id'])+'">'+h(x['name'])+'</option>' for x in data['runs'] if x['status']=='active')
  forms+='<div class="nx-card"><h3>Review conditional transition</h3><form method="post" action="/sovereign-nexus-v56">'+base+'<select name="run" required>'+runs+'</select><input type="number" min="0" max="11" name="index" value="0" required aria-label="Zero-based step index"><select name="outcome"><option value="success">Success</option><option value="blocked">Blocked</option><option value="manual_review">Manual review</option></select><button name="action" value="branch">Record branch review</button></form><p>Records a guidance decision; does not complete checkpoints.</p></div>'
 return render(c,uid,wid,csrf)+'<section class="nx-advanced"><h2>Nexus 2 · Workflow intelligence</h2><p>Reusable recipes, planned reminders, and human-reviewed conditional transitions.</p><div class="nx-grid"><div>'+forms+'</div><aside><div class="nx-card"><h3>Component library</h3><ul>'+components+'</ul></div><div class="nx-card"><h3>Schedule board</h3><ul>'+schedules+'</ul></div><div class="nx-card"><h3>Due now · manual dispatch</h3><p>Authorized users can instantiate a due approved workflow exactly once. Checkpoints still require human action.</p><ul>'+due_items+'</ul></div><div class="nx-card"><h3>Branch decision history</h3><ul>'+reviews+'</ul></div></aside></div></section>'
