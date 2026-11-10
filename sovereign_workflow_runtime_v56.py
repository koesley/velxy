"""Workflow Operations: manual checklists, run history, evidence, and approval gates.
No scheduler, outbound requests, or automatic external execution.
"""
import html, json, secrets, time, urllib.parse
import sovereign_v56 as core
import sovereign_workflows_v56 as planner

def init(c):
 planner.init(c)
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_workflow_runs(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','paused','completed','cancelled')), snapshot_json TEXT NOT NULL, created_by INTEGER NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_workflow_tasks(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, step_key TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','done','blocked')), note TEXT NOT NULL DEFAULT '', updated_by INTEGER, updated INTEGER NOT NULL, UNIQUE(run_id,ordinal))""")
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_workflow_run_meta(run_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'normal', due_date TEXT NOT NULL DEFAULT '', owner_label TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '')""")
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_workflow_events(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL, actor INTEGER NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL, created INTEGER NOT NULL)""")
 c.execute("CREATE INDEX IF NOT EXISTS sv56_workflow_events_scope ON sv56_workflow_events(workspace_id,run_id,created)")
 c.execute("CREATE INDEX IF NOT EXISTS sv56_runtime_scope ON sv56_workflow_runs(workspace_id,workflow_id,created)")
 c.execute("CREATE INDEX IF NOT EXISTS sv56_runtime_tasks_scope ON sv56_workflow_tasks(workspace_id,run_id,ordinal)")

def _run(c,wid,rid):
 row=c.execute('SELECT id,workflow_id,status,snapshot_json FROM sv56_workflow_runs WHERE workspace_id=? AND id=?',(wid,rid)).fetchone()
 if not row:raise ValueError('Run not found in workspace')
 return row

def start(c,uid,wid,wfid):
 core.access(c,uid,wid,write=True);init(c)
 with c:
  w=planner._row(c,wid,wfid)
  if w[2]!='approved':raise ValueError('Only approved workflows can start a manual run')
  steps=json.loads(w[3]);
  if 'approval' not in steps or not steps or len(steps)>12 or any(s not in planner.STEPS for s in steps):raise ValueError('Invalid approved workflow steps')
  rid=secrets.token_hex(12);now=int(time.time())
  c.execute('INSERT INTO sv56_workflow_runs VALUES(?,?,?,?,?,?,?,?)',(rid,wid,wfid,'active',json.dumps({'name':w[1],'steps':steps,'approved_by':w[5]}),uid,now,now))
  for i,s in enumerate(steps):c.execute('INSERT INTO sv56_workflow_tasks VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,rid,i,s,'pending','',None,now))
  _event(c,uid,wid,rid,'started','Approved blueprint instantiated')
  core.audit(c,uid,wid,'workflow_run_started',rid)
 return rid

def change(c,uid,wid,rid,action,task='',note=''):
 core.access(c,uid,wid,write=True);init(c)
 with c:
  run=_run(c,wid,rid);now=int(time.time())
  if action in ('pause','resume','cancel','complete'):
   transitions={'pause':('active','paused'),'resume':('paused','active'),'cancel':('active','cancelled'),'complete':('active','completed')}
   old,new=transitions[action]
   if run[2]!=old and not (action=='cancel' and run[2]=='paused'):raise ValueError('Invalid run status transition')
   if action=='complete':
    pending=c.execute("SELECT COUNT(*) FROM sv56_workflow_tasks WHERE workspace_id=? AND run_id=? AND status!='done'",(wid,rid)).fetchone()[0]
    if pending:raise ValueError('Complete every checkpoint before finishing')
   c.execute('UPDATE sv56_workflow_runs SET status=?,updated=? WHERE workspace_id=? AND id=?',(new,now,wid,rid))
  elif action in ('done','blocked','reset'):
   if run[2]!='active':raise ValueError('Only active runs can update checkpoints')
   row=c.execute('SELECT ordinal,step_key,status FROM sv56_workflow_tasks WHERE workspace_id=? AND run_id=? AND id=?',(wid,rid,task)).fetchone()
   if not row:raise ValueError('Checkpoint not found')
   if action=='done':
    if row[1]=='approval':core.access(c,uid,wid,owner=True)
    previous=c.execute("SELECT COUNT(*) FROM sv56_workflow_tasks WHERE workspace_id=? AND run_id=? AND ordinal<? AND status!='done'",(wid,rid,row[0])).fetchone()[0]
    if previous:raise ValueError('Complete earlier checkpoints first')
   status={'done':'done','blocked':'blocked','reset':'pending'}[action]
   note=note.strip()
   if len(note)>1000:raise ValueError('Checkpoint note exceeds 1000 characters')
   if action=='done' and row[1]=='approval' and not note:raise ValueError('Owner approval requires a recorded reason')
   c.execute('UPDATE sv56_workflow_tasks SET status=?,note=?,updated_by=?,updated=? WHERE workspace_id=? AND run_id=? AND id=?',(status,note,uid,now,wid,rid,task))
  else:raise ValueError('Unknown run action')
  _event(c,uid,wid,rid,action,(note or '')[:1000])
  core.audit(c,uid,wid,'workflow_run_'+action,rid)

def _event(c,uid,wid,rid,kind,detail):
 c.execute('INSERT INTO sv56_workflow_events VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,rid,uid,kind,detail,int(time.time())))

def annotate(c,uid,wid,rid,action,priority='',due_date='',owner_label='',summary='',note=''):
 core.access(c,uid,wid,write=True);init(c)
 import datetime
 with c:
  _run(c,wid,rid)
  if action=='metadata':
   if priority not in ('low','normal','high','critical'):raise ValueError('Invalid priority')
   if due_date:
    try:datetime.date.fromisoformat(due_date)
    except ValueError:raise ValueError('Invalid due date')
   if len(owner_label)>100 or len(summary)>1000:raise ValueError('Metadata too long')
   c.execute('INSERT INTO sv56_workflow_run_meta VALUES(?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET priority=excluded.priority,due_date=excluded.due_date,owner_label=excluded.owner_label,summary=excluded.summary',(rid,wid,priority,due_date,owner_label.strip(),summary.strip()))
   detail='Updated priority, due date, owner label and summary'
  elif action=='comment':
   detail=note.strip()
   if not detail or len(detail)>1000:raise ValueError('Comment must be 1–1000 characters')
  else:raise ValueError('Unknown annotation action')
  _event(c,uid,wid,rid,action,detail)
  core.audit(c,uid,wid,'workflow_run_'+action,rid)

def export_csv(c,uid,wid):
 import csv,io
 data=overview(c,uid,wid);f=io.StringIO();writer=csv.writer(f)
 writer.writerow(['run_id','workflow','status','priority','due_date','owner_label','completed','total','step','step_status','step_note'])
 for run in data['runs']:
  for task in run['tasks']:
   writer.writerow([run['id'],run['name'],run['status'],run['priority'],run['due_date'],run['owner_label'],run['completed'],run['total'],task['label'],task['status'],task['note']])
 return f.getvalue()

def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 rows=c.execute('SELECT id,workflow_id,status,snapshot_json,created,updated FROM sv56_workflow_runs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 60',(wid,)).fetchall()
 result=[]
 for rid,wfid,status,snapshot,created,updated in rows:
  snap=json.loads(snapshot)
  tasks=[{'id':tid,'ordinal':ord,'key':key,'label':planner.STEPS.get(key,(key,''))[0],'url':planner.STEPS.get(key,('','#'))[1]+'?w='+urllib.parse.quote(wid,safe=''),'status':state,'note':note,'updated_by':actor} for tid,ord,key,state,note,actor in c.execute('SELECT id,ordinal,step_key,status,note,updated_by FROM sv56_workflow_tasks WHERE workspace_id=? AND run_id=? ORDER BY ordinal',(wid,rid)).fetchall()]
  meta=c.execute('SELECT priority,due_date,owner_label,summary FROM sv56_workflow_run_meta WHERE workspace_id=? AND run_id=?',(wid,rid)).fetchone() or ('normal','','','')
  events=c.execute('SELECT event,details,created FROM sv56_workflow_events WHERE workspace_id=? AND run_id=? ORDER BY created DESC,id DESC LIMIT 30',(wid,rid)).fetchall()
  result.append({'priority':meta[0],'due_date':meta[1],'owner_label':meta[2],'summary':meta[3],'events':[{'event':e,'details':d,'created':ts} for e,d,ts in events], 'id':rid,'workflow_id':wfid,'name':snap['name'],'status':status,'created':created,'updated':updated,'tasks':tasks,'completed':sum(t['status']=='done' for t in tasks),'total':len(tasks)})
 return {'workspace_id':wid,'role':role,'stats':{'total':len(result),'active':sum(r['status']=='active' for r in result),'paused':sum(r['status']=='paused' for r in result),'blocked':sum(any(t['status']=='blocked' for t in r['tasks']) for r in result),'completed':sum(r['status']=='completed' for r in result),'critical':sum(r['priority']=='critical' for r in result)},'runs':result,'limitations':['Runs are manually updated checklists, not external automation.','Completion reflects human-reported checkpoints, not verified business outcomes.']}

def render(c,uid,wid,csrf):
 data=overview(c,uid,wid);h=lambda x:html.escape(str(x),quote=True)
 editable=data['role'] in ('owner','editor');owner=data['role']=='owner';out=[]
 for run in data['runs']:
  base='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="run" value="'+h(run['id'])+'">'
  task_html=[]
  for t in run['tasks']:
   form=''
   if editable and run['status']=='active':
    form='<form method="post" action="/sovereign-workflow-runs-v56">'+base+'<input type="hidden" name="task" value="'+h(t['id'])+'"><input name="note" maxlength="1000" placeholder="Evidence or reason (required for approval)" aria-label="Checkpoint evidence"><button name="action" value="done"'+(' disabled title="Only owners can approve"' if t['key']=='approval' and not owner else '')+'>Mark done</button><button name="action" value="blocked">Block</button><button name="action" value="reset">Reset</button></form>'
   task_html.append('<div class="wfr-task"><span class="wfr-status">'+h(t['status'])+'</span><div><b>'+str(t['ordinal']+1)+'. '+h(t['label'])+'</b> <a href="'+h(t['url'])+'">Open module</a><p>'+h(t['note'])+'</p>'+form+'</div></div>')
  meta_form=''
  if editable:
   meta_form='<details class="wfr-details"><summary>Plan details / ownership</summary><form method="post" action="/sovereign-workflow-runs-v56">'+base+'<label>Priority <select name="priority">'+''.join('<option value="'+x+'"'+(' selected' if run['priority']==x else '')+'>'+x.title()+'</option>' for x in ('low','normal','high','critical'))+'</select></label><label>Due date <input type="date" name="due_date" value="'+h(run['due_date'])+'"></label><label>Responsible person <input maxlength="100" name="owner_label" value="'+h(run['owner_label'])+'"></label><label>Objective <input maxlength="1000" name="summary" value="'+h(run['summary'])+'"></label><button name="action" value="metadata">Save plan</button></form></details>'
  comments='<details class="wfr-details"><summary>Activity & notes ('+str(len(run['events']))+')</summary><ol class="wfr-events">'+''.join('<li><strong>'+h(e['event'])+'</strong> · '+h(e['details'])+' <small>'+h(e['created'])+'</small></li>' for e in run['events'])+'</ol>'+('<form method="post" action="/sovereign-workflow-runs-v56">'+base+'<input name="note" maxlength="1000" required placeholder="Add a team note"><button name="action" value="comment">Add note</button></form>' if editable else '')+'</details>'
  actions=''
  if editable and run['status'] in ('active','paused'):
   actions='<form method="post" action="/sovereign-workflow-runs-v56">'+base+''.join('<button name="action" value="'+a+'">'+label+'</button>' for a,label in ([('pause','Pause'),('complete','Finish'),('cancel','Cancel')] if run['status']=='active' else [('resume','Resume'),('cancel','Cancel')]))+'</form>'
  out.append('<article class="wfr-card"><div class="wfr-head"><h3>'+h(run['name'])+'</h3><span>'+h(run['status'])+'</span></div><p><strong>'+h(run['priority']).upper()+'</strong> · Due '+h(run['due_date'] or 'unscheduled')+' · '+h(run['owner_label'] or 'unassigned')+'</p><p>'+h(run['summary'])+'</p><p>'+str(run['completed'])+' of '+str(run['total'])+' checkpoints recorded</p><progress value="'+str(run['completed'])+'" max="'+str(max(1,run['total']))+'"></progress>'+''.join(task_html)+meta_form+comments+actions+'</article>')
 starts=[]
 if editable:
  rows=c.execute("SELECT id,name FROM sv56_workflows WHERE workspace_id=? AND status='approved' ORDER BY updated DESC LIMIT 30",(wid,)).fetchall()
  for wfid,name in rows:starts.append('<form method="post" action="/sovereign-workflow-runs-v56"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="workflow" value="'+h(wfid)+'"><button name="action" value="start">Start manual run: '+h(name)+'</button></form>')
 stats=data['stats'];kpis='<section class="wfr-kpis">'+''.join('<div><strong>'+str(value)+'</strong><span>'+h(key.title())+'</span></div>' for key,value in stats.items())+'</section>'
 return '<section class="wfr-hero"><span>VELXTRIA / OPERATIONS</span><h1>From plans to accountable progress.</h1><p>Track manual checkpoints, document evidence, pause work, and require workspace-owner approval at the human gate. No automatic external execution.</p><a href="/sovereign-workflows-v56?w='+h(urllib.parse.quote(wid,safe=''))+'">← Workflow designer</a></section>'+kpis+'<section class="wfr-panel"><h2>Start from an approved blueprint</h2>'+(''.join(starts) if starts else '<p>No approved workflows yet. Approve a blueprint in Workflow Studio.</p>')+'</section><section class="wfr-panel"><h2>Run history</h2><p><a href="/sovereign-workflow-runs-v56.csv?w='+h(urllib.parse.quote(wid,safe=''))+'">Export checkpoints as CSV</a></p><div class="wfr-grid">'+(''.join(out) if out else '<p>No runs yet.</p>')+'</div></section><p class="wf-foot">This is a human-operated progress tracker, not an autonomous scheduler or execution engine.</p>'
