"""Local-only, human-approved visual workflow planner. No external actions."""
import html, json, secrets, time, urllib.parse
import sovereign_v56 as core

STEPS={'connectors':('Connectors','/sovereign-connectors-v56'),'guardian':('Guardian','/sovereign-guardian-v56'),'genesis':('Project Genesis','/sovereign-genesis-v56'),'strategy':('Strategies','/sovereign-strategies-v56'),'future':('Future Simulator','/sovereign-future-v56'),'approval':('Human Approval','/sovereign-execution-v56'),'memory':('Organizational Memory','/sovereign-memory-v56')}
TEMPLATES={'discover':['connectors','guardian','genesis','approval','memory'],'plan':['connectors','strategy','future','approval','memory'],'monitor':['connectors','guardian','approval','memory'],'launch':['connectors','genesis','strategy','future','approval','memory'],'resilience':['guardian','future','approval','memory']}
def init(c):
 c.execute('CREATE TABLE IF NOT EXISTS sv56_workflows(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ("draft","approved","archived")),steps_json TEXT NOT NULL,created_by INTEGER NOT NULL,approved_by INTEGER,created INTEGER NOT NULL,updated INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_workflows_scope ON sv56_workflows(workspace_id,created)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_workflow_reviews(id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,snapshot_json TEXT NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_workflow_reviews_scope ON sv56_workflow_reviews(workspace_id,workflow_id)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_workflow_notes(id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,body TEXT NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_workflow_notes_scope ON sv56_workflow_notes(workspace_id,workflow_id,created)')
def _row(c,wid,wfid):
 row=c.execute('SELECT id,name,status,steps_json,created,approved_by FROM sv56_workflows WHERE workspace_id=? AND id=?',(wid,wfid)).fetchone()
 if not row:raise ValueError('Workflow not found')
 return row
def create(c,uid,wid,name,template):
 core.access(c,uid,wid,write=True);init(c)
 name=name.strip()
 if not 3<=len(name)<=100:raise ValueError('Workflow name must be 3–100 characters')
 if template not in TEMPLATES:raise ValueError('Unknown workflow template')
 wid_id=secrets.token_hex(12);now=int(time.time())
 with c:
  c.execute('INSERT INTO sv56_workflows VALUES(?,?,?,?,?,?,?,?,?)',(wid_id,wid,name,'draft',json.dumps(TEMPLATES[template]),uid,None,now,now))
  core.audit(c,uid,wid,'workflow_created',wid_id)
 return wid_id
def update(c,uid,wid,wfid,action,step=''):
 core.access(c,uid,wid,write=True);init(c)
 with c:
  row=_row(c,wid,wfid);steps=json.loads(row[3]);status=row[2]
  if action in ('add','remove','up','down'):
   if status!='draft':raise ValueError('Only draft workflows can be edited')
   if step not in STEPS:raise ValueError('Unknown step')
   if action=='add':
    if len(steps)>=12:raise ValueError('Maximum 12 steps')
    steps.append(step)
   else:
    if step not in steps:raise ValueError('Step is not in workflow')
    idx=steps.index(step)
    if action=='remove':steps.pop(idx)
    elif action=='up' and idx>0:steps[idx-1],steps[idx]=steps[idx],steps[idx-1]
    elif action=='down' and idx<len(steps)-1:steps[idx+1],steps[idx]=steps[idx],steps[idx+1]
   c.execute('UPDATE sv56_workflows SET steps_json=?,updated=? WHERE workspace_id=? AND id=?',(json.dumps(steps),int(time.time()),wid,wfid))
  elif action=='duplicate':
   new_id=secrets.token_hex(12);now=int(time.time())
   c.execute('INSERT INTO sv56_workflows VALUES(?,?,?,?,?,?,?,?,?)',(new_id,wid,row[1]+' (copy)','draft',json.dumps(steps),uid,None,now,now))
   core.audit(c,uid,wid,'workflow_duplicated',new_id)
  elif action=='approve':
   core.access(c,uid,wid,owner=True)
   if status!='draft' or not steps or 'approval' not in steps:raise ValueError('Draft must contain a human approval step')
   c.execute('UPDATE sv56_workflows SET status="approved",approved_by=?,updated=? WHERE workspace_id=? AND id=?',(uid,int(time.time()),wid,wfid))
  elif action=='archive':
   if status=='archived':raise ValueError('Already archived')
   c.execute('UPDATE sv56_workflows SET status="archived",updated=? WHERE workspace_id=? AND id=?',(int(time.time()),wid,wfid))
  elif action=='review':
   snapshot={'workflow_id':wfid,'steps':steps,'status':status,'type':'manual_navigation_preview','execution_performed':False,'limitations':['Steps are navigation links, not automated operations.','No external actions or financial outcomes are triggered.']}
   c.execute('INSERT INTO sv56_workflow_reviews VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wfid,wid,uid,int(time.time()),json.dumps(snapshot)))
  else:raise ValueError('Unknown workflow action')
  core.audit(c,uid,wid,'workflow_'+action,wfid)
def add_note(c,uid,wid,wfid,body):
 core.access(c,uid,wid,write=True);init(c)
 body=body.strip()
 if not 1<=len(body)<=1000:raise ValueError('Note must contain 1–1000 characters')
 with c:
  _row(c,wid,wfid)
  c.execute('INSERT INTO sv56_workflow_notes VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wfid,wid,uid,body,int(time.time())))
  core.audit(c,uid,wid,'workflow_note_added',wfid)

def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 rows=c.execute('SELECT id,name,status,steps_json,created,approved_by FROM sv56_workflows WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,)).fetchall()
 workflows=[]
 for id,name,status,steps,created,approved_by in rows:
  workflow={'id':id,'name':name,'status':status,'steps':[{'key':s,'label':STEPS[s][0],'url':STEPS[s][1]+'?w='+urllib.parse.quote(wid,safe='')} for s in json.loads(steps) if s in STEPS],'created':created,'approved_by':approved_by}
  workflow['reviews']=c.execute('SELECT count(*) FROM sv56_workflow_reviews WHERE workspace_id=? AND workflow_id=?',(wid,id)).fetchone()[0]
  workflow['notes']=[{'body':body,'created':ts} for body,ts in c.execute('SELECT body,created FROM sv56_workflow_notes WHERE workspace_id=? AND workflow_id=? ORDER BY created DESC,id DESC LIMIT 5',(wid,id)).fetchall()]
  workflow['readiness']={'approval_step':any(s['key']=='approval' for s in workflow['steps']),'steps':len(workflow['steps']),'can_approve':status=='draft' and bool(workflow['steps']) and any(s['key']=='approval' for s in workflow['steps'])}
  workflows.append(workflow)
 return {'workspace_id':wid,'role':role,'workflows':workflows,'read_only_execution':True,'limitations':['Workflows are editable plans with human approval, not an automation engine.','Review only records a local preview; steps must be opened and performed manually.']}
def render(c,uid,wid,csrf):
 data=overview(c,uid,wid);h=lambda x:html.escape(str(x),quote=True);can_edit=data['role'] in ('owner','editor');owner=data['role']=='owner';out=[]
 for w in data['workflows']:
  nodes=[]
  for i,s in enumerate(w['steps']):
   controls=''
   if can_edit and w['status']=='draft':
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="workflow" value="'+h(w['id'])+'"><input type="hidden" name="step" value="'+h(s['key'])+'">'
    controls='<form method="post" action="/sovereign-workflows-v56" class="wf-step-actions">'+hidden+''.join('<button name="action" value="'+act+'" title="'+label+'">'+label+'</button>' for act,label in [('up','Move up'),('down','Move down'),('remove','Remove')])+'</form>'
   nodes.append('<div class="wf-node"><span class="wf-num">'+str(i+1)+'</span><div><b>'+h(s['label'])+'</b><small>Human-operated module</small><a href="'+h(s['url'])+'">Open module →</a></div>'+controls+'</div>')
  forms=''
  if can_edit and w['status']=='draft':
   opts=''.join('<option value="'+h(k)+'">'+h(v[0])+'</option>' for k,v in STEPS.items())
   forms='<form method="post" action="/sovereign-workflows-v56"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="workflow" value="'+h(w['id'])+'"><select name="step">'+opts+'</select><button name="action" value="add">Add step</button></form>'
  note_html='<div class="wf-insights"><span>Steps: '+str(w['readiness']['steps'])+'</span><span>Previews: '+str(w['reviews'])+'</span><span>'+('Approval gate ready' if w['readiness']['approval_step'] else 'Approval gate missing')+'</span></div>'
  note_html+='<div class="wf-notes"><h4>Decision journal</h4>'+''.join('<p>'+h(n['body'])+'</p>' for n in w['notes'])+'</div>'
  if can_edit:note_html+='<form method="post" action="/sovereign-workflows-v56"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="workflow" value="'+h(w['id'])+'"><textarea name="note" maxlength="1000" required placeholder="Record evidence, decisions, or questions"></textarea><button name="action" value="note">Save note</button></form>'
  actions='<form method="post" action="/sovereign-workflows-v56"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="workflow" value="'+h(w['id'])+'"><button name="action" value="review">Record safe preview</button>'+('<button name="action" value="duplicate">Duplicate as draft</button>' if can_edit else '')+(('<button name="action" value="approve">Owner approve plan</button>') if owner and w['status']=='draft' else '')+(('<button name="action" value="archive">Archive</button>') if can_edit and w['status']!='archived' else '')+'</form>'
  out.append('<article class="wf-card"><div class="wf-card-head"><h3>'+h(w['name'])+'</h3><span class="wf-tag">'+h(w['status'])+'</span></div><div class="wf-nodes">'+''.join(nodes)+'</div>'+forms+note_html+actions+'</article>')
 createform=''
 if can_edit:
  createform='<form method="post" action="/sovereign-workflows-v56" class="wf-create"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><label>Workflow name<input name="name" maxlength="100" minlength="3" required placeholder="e.g. Weekly opportunity review"></label><label>Starting blueprint<select name="template"><option value="discover">Discover opportunities</option><option value="plan">Compare strategies</option><option value="monitor">Monitor operations</option><option value="launch">Explore a product launch</option><option value="resilience">Review business resilience</option></select></label><button name="action" value="create">Create workflow</button></form>'
 return '<section class="wf-hero"><span class="wf-kicker">VELXTRIA / WORKFLOW STUDIO</span><h1>Design the way your business thinks.</h1><p>Compose a pathway across Genesis, Guardian, Strategies, and approvals. Preview before anyone acts. No external automation is enabled.</p><div class="wf-pills"><span>◇ Visual pathways</span><span>◇ Workspace-scoped</span><span>◇ Owner approval</span><span>◇ Local-only</span><a class="wf-run-link" href="/sovereign-workflow-runs-v56?w='+h(urllib.parse.quote(wid,safe=''))+'">Run operations →</a></div></section><section class="wf-section"><h2>Build a pathway</h2>'+createform+'</section><section class="wf-section"><h2>Saved workflows <small>'+str(len(out))+'</small></h2><div class="wf-grid">'+(''.join(out) if out else '<p>No workflows yet. Create one from a blueprint above.</p>')+'</div></section><p class="wf-foot">Design and preview only. Approving a plan does not run tasks, send emails, change prices, or spend money.</p>'
