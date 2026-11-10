"""V44 Synapse: explicit human-owned execution plans and recurring evidence snapshots.
No network side effects, scheduler, AI autonomy, or automatic customer data writes.
"""
import html, json, secrets, time, math
from urllib.parse import urlencode
import empire_v19, autonomous_core_v43 as core, nexus_v25

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS synapse_tasks_v44 (id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,experiment_id TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('todo','in_progress','done','cancelled')),created_by INTEGER NOT NULL,completed_by INTEGER,created INTEGER NOT NULL,completed INTEGER,proof TEXT NOT NULL DEFAULT '')''')
 c.execute('''CREATE TABLE IF NOT EXISTS synapse_snapshots_v44 (id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,experiment_id TEXT NOT NULL,value REAL NOT NULL,sampled INTEGER NOT NULL,actor_id INTEGER NOT NULL,created INTEGER NOT NULL,note TEXT NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS synapse_task_scope_v44 ON synapse_tasks_v44(workspace_id,experiment_id,created)')
 c.execute('CREATE INDEX IF NOT EXISTS synapse_snapshot_scope_v44 ON synapse_snapshots_v44(workspace_id,experiment_id,created)')

def _experiment(c,uid,wid,eid,write=False,owner=False):
 core._role(c,uid,wid,write=write,owner=owner)
 row=c.execute('SELECT id,goal_id,status,title FROM core_experiments_v43 WHERE workspace_id=? AND id=?',(wid,eid)).fetchone()
 if not row:raise ValueError('Experiment unavailable in workspace')
 return row

def _event(c,wid,eid,uid,action,details):core._event(c,wid,eid,uid,'synapse:'+action,details)

def create_task(c,uid,wid,eid,title,description):
 row=_experiment(c,uid,wid,eid,write=True)
 if row[2]!='approved':raise ValueError('Only approved experiments accept new tasks')
 title=core._clean(title,'Task title',3,120);description=core._clean(description,'Task description',10,1000)
 task_id=secrets.token_hex(12)
 c.execute('INSERT INTO synapse_tasks_v44(id,workspace_id,experiment_id,title,description,status,created_by,created) VALUES(?,?,?,?,?,?,?,?)',(task_id,wid,eid,title,description,'todo',uid,int(time.time())))
 _event(c,wid,eid,uid,'task-created',json.dumps({'task_id':task_id,'title':title}))
 return task_id

def update_task(c,uid,wid,tid,status,proof=''):
 core._role(c,uid,wid,write=True)
 row=c.execute('''SELECT t.experiment_id,t.status,e.status FROM synapse_tasks_v44 t JOIN core_experiments_v43 e ON e.id=t.experiment_id AND e.workspace_id=t.workspace_id WHERE t.workspace_id=? AND t.id=?''',(wid,tid)).fetchone()
 if not row:raise ValueError('Task unavailable')
 if row[2]!='approved':raise ValueError('Experiment is no longer active')
 if row[1] in ('done','cancelled'):raise ValueError('Finalized task is immutable')
 if status not in ('in_progress','done','cancelled'):raise ValueError('Invalid task transition')
 if status=='in_progress' and row[1]!='todo':raise ValueError('Task already started')
 if status=='done':proof=core._clean(proof,'Completion evidence',10,1500)
 else:proof=''
 c.execute('UPDATE synapse_tasks_v44 SET status=?,proof=?,completed_by=?,completed=? WHERE workspace_id=? AND id=?',(status,proof,uid if status=='done' else None,int(time.time()) if status=='done' else None,wid,tid))
 _event(c,wid,row[0],uid,'task-'+status,json.dumps({'task_id':tid,'proof':proof}))

def snapshot(c,uid,wid,eid,note):
 row=_experiment(c,uid,wid,eid,write=True)
 if row[2]!='approved':raise ValueError('Snapshots require an approved active experiment')
 note=core._clean(note,'Measurement context',10,500)
 m=nexus_v25.measure(c,uid,wid,row[1]);value=float(m['value'])
 if not math.isfinite(value):raise ValueError('Invalid goal measurement')
 sid=secrets.token_hex(12)
 c.execute('INSERT INTO synapse_snapshots_v44 VALUES(?,?,?,?,?,?,?,?)',(sid,wid,eid,value,int(m['sampled_records']),uid,int(time.time()),note))
 _event(c,wid,eid,uid,'measurement',json.dumps({'snapshot_id':sid,'value':value,'sampled':m['sampled_records']}))
 return sid

def finalize(c,uid,wid,eid,notes):
 row=_experiment(c,uid,wid,eid,write=True)
 if row[2]!='approved':raise ValueError('Experiment must be approved')
 outstanding=c.execute("SELECT count(*) FROM synapse_tasks_v44 WHERE workspace_id=? AND experiment_id=? AND status IN ('todo','in_progress')",(wid,eid)).fetchone()[0]
 if outstanding:raise ValueError('Complete or cancel all open tasks before finalizing')
 return core.complete(c,uid,wid,eid,notes)

def report(c,uid,wid=''):
 base=core.report(c,uid,wid);wid=base['workspace_id']
 if not wid:return dict(base,tasks=[],snapshots=[],progress={})
 tasks=[dict(zip(('id','experiment_id','title','description','status','created_by','completed_by','created','completed','proof'),r)) for r in c.execute('SELECT id,experiment_id,title,description,status,created_by,completed_by,created,completed,proof FROM synapse_tasks_v44 WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 500',(wid,)).fetchall()]
 snapshots=[dict(zip(('id','experiment_id','value','sampled','actor_id','created','note'),r)) for r in c.execute('SELECT id,experiment_id,value,sampled,actor_id,created,note FROM synapse_snapshots_v44 WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 500',(wid,)).fetchall()]
 progress={}
 for e in base['experiments']:
  ts=[t for t in tasks if t['experiment_id']==e['id']];ss=[s for s in snapshots if s['experiment_id']==e['id']]
  progress[e['id']]={'tasks_total':len(ts),'tasks_done':sum(t['status']=='done' for t in ts),'tasks_open':sum(t['status'] in ('todo','in_progress') for t in ts),'snapshots':len(ss),'latest_value':ss[0]['value'] if ss else None,'change_from_baseline':round(ss[0]['value']-e['baseline'],4) if ss else None}
 return dict(base,tasks=tasks,snapshots=snapshots,progress=progress,limitations=base['limitations']+['Tasks are manual instructions, not automatically executed','Snapshots are taken only when a user requests them','Observed changes do not prove causation'])

def render(c,uid,csrf,wid=''):
 r=report(c,uid,wid);esc=lambda v:html.escape(str(v),quote=True)
 if not r['workspace_id']:return '<section class="panel"><h1>Synapse V44</h1><p>Create a workspace first.</p></section>'
 wid=r['workspace_id'];role=core._role(c,uid,wid);q=urlencode({'w':wid})
 hidden='<input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'">'
 out=['<section class="panel"><h1>✦ SYNAPSE V44</h1><p>Human-controlled execution plans, verified task completion, measurement snapshots and progress tracking.</p><p><a href="/synapse.json?'+esc(q)+'">Export Synapse evidence (JSON)</a> · <a href="/autonomous-core?'+esc(q)+'">Manage experiment approvals</a></p></section>']
 for e in r['experiments']:
  p=r['progress'][e['id']];out.append('<section class="panel"><h2>'+esc(e['title'])+'</h2><p>Status: <strong>'+esc(e['status'])+'</strong> · Goal: '+esc(e['goal_title'])+'</p><p>Tasks: '+str(p['tasks_done'])+'/'+str(p['tasks_total'])+' completed · '+str(p['tasks_open'])+' open · '+str(p['snapshots'])+' snapshots</p><p>Baseline: '+esc(e['baseline'])+' · Latest snapshot: '+esc(p['latest_value'] if p['latest_value'] is not None else 'none')+' · Change: '+esc(p['change_from_baseline'] if p['change_from_baseline'] is not None else 'n/a')+'</p>')
  for t in [t for t in r['tasks'] if t['experiment_id']==e['id']]:
   out.append('<article style="padding:10px;border-top:1px solid #655777"><strong>'+esc(t['title'])+'</strong> — '+esc(t['status'])+'<p>'+esc(t['description'])+'</p>')
   if t['proof']:out.append('<p>Evidence: '+esc(t['proof'])+'</p>')
   if role in ('owner','editor') and e['status']=='approved' and t['status'] in ('todo','in_progress'):
    out.append('<form method="post" action="/synapse">'+hidden+'<input type="hidden" name="action" value="task-status"><input type="hidden" name="task" value="'+esc(t['id'])+'"><select name="status">'+(' <option value="in_progress">Start task</option>' if t['status']=='todo' else '')+'<option value="done">Mark done</option><option value="cancelled">Cancel task</option></select><label>Completion evidence (required when done)<textarea name="proof" maxlength="1500"></textarea></label><button>Update task</button></form>')
   out.append('</article>')
  for s in [s for s in r['snapshots'] if s['experiment_id']==e['id']][:10]:out.append('<p>Measurement '+esc(s['value'])+' · sample '+esc(s['sampled'])+' · '+esc(s['note'])+'</p>')
  if role in ('owner','editor') and e['status']=='approved':
   out.append('<h3>Add a manual task</h3><form method="post" action="/synapse">'+hidden+'<input type="hidden" name="action" value="task-create"><input type="hidden" name="experiment" value="'+esc(e['id'])+'"><label>Task<input name="title" maxlength="120" required></label><label>Instructions<textarea name="description" maxlength="1000" required></textarea></label><button>Create task</button></form>')
   out.append('<h3>Record a measurement</h3><form method="post" action="/synapse">'+hidden+'<input type="hidden" name="action" value="snapshot"><input type="hidden" name="experiment" value="'+esc(e['id'])+'"><label>Measurement context<input name="note" maxlength="500" required></label><button>Capture current goal value</button></form>')
   out.append('<h3>Finalize experiment</h3><form method="post" action="/synapse">'+hidden+'<input type="hidden" name="action" value="finalize"><input type="hidden" name="experiment" value="'+esc(e['id'])+'"><label>Outcome notes<textarea name="notes" maxlength="1500" required></textarea></label><button>Finalize after tasks close</button></form>')
  out.append('</section>')
 if not r['experiments']:out.append('<section class="panel"><p>No experiments yet. <a href="/autonomous-core?'+esc(q)+'">Propose one in Autonomous Core</a>.</p></section>')
 out.append('<section class="panel"><p>Safety: no tasks are executed automatically. Measurements are observational and do not guarantee business improvements.</p></section>')
 return ''.join(out)
