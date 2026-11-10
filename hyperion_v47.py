"""Hyperion V47: human-controlled delivery plans, dependencies, milestones, and risk review."""
import html,json,secrets,time,datetime
from urllib.parse import urlencode
import synapse_v44 as syn, autonomous_core_v43 as core

def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS hyperion_plans_v47(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,experiment_id TEXT NOT NULL,title TEXT NOT NULL,owner_id INTEGER NOT NULL,due_date TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','closed')),created INTEGER NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS hyperion_steps_v47(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,plan_id TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,depends_on TEXT,due_date TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('todo','doing','done','cancelled')),proof TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,completed INTEGER)""")
 c.execute("""CREATE TABLE IF NOT EXISTS hyperion_events_v47(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,plan_id TEXT NOT NULL,actor_id INTEGER NOT NULL,action TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL)""")
 c.execute('CREATE INDEX IF NOT EXISTS hyperion_plan_scope ON hyperion_plans_v47(workspace_id,experiment_id)')
 c.execute('CREATE INDEX IF NOT EXISTS hyperion_step_scope ON hyperion_steps_v47(workspace_id,plan_id)')
def _date(s):
 try:d=datetime.date.fromisoformat(str(s));assert 2020<=d.year<=2100;return d.isoformat()
 except (ValueError,AssertionError):raise ValueError('Use a valid YYYY-MM-DD date')
def _event(c,wid,pid,uid,action,detail):c.execute('INSERT INTO hyperion_events_v47 VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,pid,uid,action,detail,int(time.time())))
def _plan(c,uid,wid,pid,write=False):
 core._role(c,uid,wid,write=write)
 p=c.execute('SELECT id,experiment_id,status FROM hyperion_plans_v47 WHERE workspace_id=? AND id=?',(wid,pid)).fetchone()
 if not p:raise ValueError('Plan unavailable in workspace')
 return p
def create_plan(c,uid,wid,eid,title,due_date):
 row=syn._experiment(c,uid,wid,eid,write=True)
 if row[2]!='approved':raise ValueError('An approved experiment is required')
 title=core._clean(title,'Plan title',3,120);due_date=_date(due_date);pid=secrets.token_hex(12)
 c.execute('INSERT INTO hyperion_plans_v47 VALUES(?,?,?,?,?,?,?,?)',(pid,wid,eid,title,uid,due_date,'active',int(time.time())))
 _event(c,wid,pid,uid,'plan-created',title);return pid
def add_step(c,uid,wid,pid,title,description,due_date,depends_on=''):
 p=_plan(c,uid,wid,pid,True)
 if p[2]!='active':raise ValueError('Plan closed')
 if syn._experiment(c,uid,wid,p[1])[2]!='approved':raise ValueError('Experiment not active')
 title=core._clean(title,'Milestone title',3,120);description=core._clean(description,'Instructions',10,1000);due_date=_date(due_date)
 if depends_on:
  dep=c.execute('SELECT id FROM hyperion_steps_v47 WHERE id=? AND workspace_id=? AND plan_id=?',(depends_on,wid,pid)).fetchone()
  if not dep:raise ValueError('Dependency must belong to this plan')
 sid=secrets.token_hex(12)
 c.execute('INSERT INTO hyperion_steps_v47 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,wid,pid,title,description,depends_on or None,due_date,'todo','',int(time.time()),None))
 _event(c,wid,pid,uid,'step-created',sid);return sid
def transition(c,uid,wid,sid,status,proof=''):
 core._role(c,uid,wid,write=True)
 row=c.execute("""SELECT s.plan_id,s.status,s.depends_on,p.status,p.experiment_id FROM hyperion_steps_v47 s JOIN hyperion_plans_v47 p ON p.id=s.plan_id AND p.workspace_id=s.workspace_id WHERE s.id=? AND s.workspace_id=?""",(sid,wid)).fetchone()
 if not row:raise ValueError('Milestone unavailable')
 pid,old,dep,pstatus,eid=row
 if pstatus!='active' or syn._experiment(c,uid,wid,eid)[2]!='approved':raise ValueError('Plan or experiment not active')
 if old in ('done','cancelled'):raise ValueError('Completed milestone immutable')
 if status not in ('doing','done','cancelled') or (status=='doing' and old!='todo'):raise ValueError('Invalid transition')
 if status in ('doing','done') and dep:
  dr=c.execute('SELECT status FROM hyperion_steps_v47 WHERE id=? AND workspace_id=? AND plan_id=?',(dep,wid,pid)).fetchone()
  if not dr or dr[0]!='done':raise ValueError('Complete prerequisite milestone first')
 if status=='done':proof=core._clean(proof,'Completion evidence',10,1500)
 else:proof=''
 c.execute('UPDATE hyperion_steps_v47 SET status=?,proof=?,completed=? WHERE id=? AND workspace_id=?',(status,proof,int(time.time()) if status=='done' else None,sid,wid))
 _event(c,wid,pid,uid,'step-'+status,sid)
def close_plan(c,uid,wid,pid):
 p=_plan(c,uid,wid,pid,True)
 if p[2]!='active':raise ValueError('Already closed')
 n=c.execute("SELECT count(*) FROM hyperion_steps_v47 WHERE workspace_id=? AND plan_id=? AND status IN ('todo','doing')",(wid,pid)).fetchone()[0]
 if n:raise ValueError('Resolve every open milestone before closing')
 c.execute('UPDATE hyperion_plans_v47 SET status=? WHERE id=? AND workspace_id=?',('closed',pid,wid));_event(c,wid,pid,uid,'plan-closed','All milestones resolved')
def report(c,uid,wid=''):
 base=syn.report(c,uid,wid);wid=base['workspace_id']
 if not wid:return {'workspace_id':None,'plans':[],'events':[],'summary':{}}
 plans=[];today=datetime.date.today()
 for r in c.execute('SELECT id,experiment_id,title,owner_id,due_date,status,created FROM hyperion_plans_v47 WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 200',(wid,)).fetchall():
  p=dict(zip(('id','experiment_id','title','owner_id','due_date','status','created'),r))
  p['steps']=[dict(zip(('id','title','description','depends_on','due_date','status','proof','created','completed'),s)) for s in c.execute('SELECT id,title,description,depends_on,due_date,status,proof,created,completed FROM hyperion_steps_v47 WHERE workspace_id=? AND plan_id=? ORDER BY created,id',(wid,p['id'])).fetchall()]
  p['open']=sum(s['status'] in ('todo','doing') for s in p['steps']);p['done']=sum(s['status']=='done' for s in p['steps']);p['overdue']=sum(s['status'] in ('todo','doing') and s['due_date']<today.isoformat() for s in p['steps']);p['blocked']=sum(s['status'] in ('todo','doing') and bool(s['depends_on']) and next((x['status'] for x in p['steps'] if x['id']==s['depends_on']),None)!='done' for s in p['steps']);plans.append(p)
 events=[dict(zip(('plan_id','actor_id','action','details','created'),r)) for r in c.execute('SELECT plan_id,actor_id,action,details,created FROM hyperion_events_v47 WHERE workspace_id=? ORDER BY created DESC LIMIT 200',(wid,)).fetchall()]
 return {'workspace_id':wid,'plans':plans,'events':events,'summary':{'plans':len(plans),'open':sum(p['open'] for p in plans),'overdue':sum(p['overdue'] for p in plans),'blocked':sum(p['blocked'] for p in plans)},'limitations':['No automated task execution or scheduled background monitoring','Deadlines are user-entered; risk flags are descriptive','Human approval remains mandatory for experiments']}
def render(c,uid,csrf,wid=''):
 r=report(c,uid,wid);esc=lambda x:html.escape(str(x),quote=True)
 if not r['workspace_id']:return '<section class="panel"><h1>Hyperion</h1><p>Create a workspace first.</p></section>'
 wid=r['workspace_id'];role=core._role(c,uid,wid);q=urlencode({'w':wid});hidden='<input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'">'
 out=['<section class="panel"><h1>✦ HYPERION V47 — Delivery Command</h1><p>Approval-gated operational plans, milestone dependencies, deadlines, evidence and delivery risks.</p><p><a href="/hyperion.json?'+esc(q)+'">Download audit JSON</a> · <a href="/synapse?'+esc(q)+'">Synapse</a> · <a href="/evolution-engine?'+esc(q)+'">Evolution Engine</a></p><h2>Delivery pulse</h2><p>'+esc(r['summary'])+'</p></section>']
 if role in ('owner','editor'):
  approved=c.execute("SELECT id,title FROM core_experiments_v43 WHERE workspace_id=? AND status='approved' ORDER BY created DESC LIMIT 100",(wid,)).fetchall()
  out.append('<section class="panel"><h2>Create delivery plan</h2><form method="post" action="/hyperion">'+hidden+'<input type="hidden" name="action" value="create"><label>Approved experiment<select name="experiment">'+''.join('<option value="'+esc(x)+'">'+esc(y)+'</option>' for x,y in approved)+'</select></label><label>Plan title<input name="title" required maxlength="120"></label><label>Target date<input type="date" name="due" required></label><button>Create plan</button></form></section>')
 for p in r['plans']:
  out.append('<section class="panel"><h2>'+esc(p['title'])+'</h2><p>'+esc(p['status'])+' · '+esc(p['done'])+' completed · '+esc(p['open'])+' open · '+esc(p['overdue'])+' overdue · '+esc(p['blocked'])+' blocked · Due '+esc(p['due_date'])+'</p>')
  for s in p['steps']:
   out.append('<article style="border-top:1px solid #655777;padding:12px 0"><strong>'+esc(s['title'])+'</strong> · '+esc(s['status'])+' · Due '+esc(s['due_date'])+'<p>'+esc(s['description'])+'</p>'+('<p>Evidence: '+esc(s['proof'])+'</p>' if s['proof'] else ''))
   if role in ('owner','editor') and p['status']=='active' and s['status'] in ('todo','doing'):
    out.append('<form method="post" action="/hyperion">'+hidden+'<input type="hidden" name="action" value="transition"><input type="hidden" name="step" value="'+esc(s['id'])+'"><label>Status<select name="status">'+('<option value="doing">Start</option>' if s['status']=='todo' else '')+'<option value="done">Done</option><option value="cancelled">Cancel</option></select></label><label>Completion evidence<textarea name="proof" maxlength="1500"></textarea></label><button>Update milestone</button></form>')
   out.append('</article>')
  if role in ('owner','editor') and p['status']=='active':
   out.append('<h3>Add milestone</h3><form method="post" action="/hyperion">'+hidden+'<input type="hidden" name="action" value="add"><input type="hidden" name="plan" value="'+esc(p['id'])+'"><label>Title<input name="title" maxlength="120" required></label><label>Instructions<textarea name="description" maxlength="1000" required></textarea></label><label>Due date<input type="date" name="due" required></label><label>Prerequisite<select name="depends"><option value="">None</option>'+''.join('<option value="'+esc(s['id'])+'">'+esc(s['title'])+'</option>' for s in p['steps'])+'</select></label><button>Add milestone</button></form><form method="post" action="/hyperion">'+hidden+'<input type="hidden" name="action" value="close"><input type="hidden" name="plan" value="'+esc(p['id'])+'"><button>Close resolved plan</button></form>')
  out.append('</section>')
 out.append('<section class="panel"><p>Human-controlled execution only. Overdue indicators do not trigger automatic changes or messages.</p></section>');return ''.join(out)
