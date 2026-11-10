"""Quantum Command V48: tenant-isolated capacity planning and explainable scenarios.
All forecasts are estimates, not promises. No background execution or record mutation.
"""
import datetime,html,json,math,time
from urllib.parse import urlencode
import hyperion_v47 as hyper
import autonomous_core_v43 as core

def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS quantum_capacity_v48(workspace_id TEXT PRIMARY KEY,weekly_hours REAL NOT NULL CHECK(weekly_hours>0 AND weekly_hours<=10000),updated INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS quantum_estimates_v48(workspace_id TEXT NOT NULL,step_id TEXT NOT NULL,hours REAL NOT NULL CHECK(hours>0 AND hours<=10000),updated INTEGER NOT NULL,PRIMARY KEY(workspace_id,step_id))')

def _hours(x):
 try:
  n=float(x)
  if not math.isfinite(n) or not 0<n<=10000:raise ValueError()
  return round(n,2)
 except (TypeError,ValueError):raise ValueError('Hours must be a finite number greater than zero and at most 10000')

def set_capacity(c,uid,wid,hours):
 core._role(c,uid,wid,write=True);n=_hours(hours)
 c.execute('INSERT INTO quantum_capacity_v48 VALUES(?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET weekly_hours=excluded.weekly_hours,updated=excluded.updated',(wid,n,int(time.time())))

def set_estimate(c,uid,wid,step_id,hours):
 core._role(c,uid,wid,write=True);n=_hours(hours)
 step=c.execute('''SELECT p.status,s.status FROM hyperion_steps_v47 s JOIN hyperion_plans_v47 p ON p.id=s.plan_id AND p.workspace_id=s.workspace_id WHERE s.workspace_id=? AND s.id=?''',(wid,step_id)).fetchone()
 if not step:raise ValueError('Milestone unavailable in workspace')
 if step[0]!='active' or step[1] in ('done','cancelled'):raise ValueError('Only active unfinished milestones can be estimated')
 c.execute('INSERT INTO quantum_estimates_v48 VALUES(?,?,?,?) ON CONFLICT(workspace_id,step_id) DO UPDATE SET hours=excluded.hours,updated=excluded.updated',(wid,step_id,n,int(time.time())))

def _critical_path(steps):
 byid={s['id']:s for s in steps};memo={};visiting=set()
 def visit(sid):
  if sid in memo:return memo[sid]
  if sid in visiting:return 0.0
  visiting.add(sid);s=byid[sid];parent=s.get('depends_on');v=s['estimated_hours']+(visit(parent) if parent in byid else 0);visiting.remove(sid);memo[sid]=v;return v
 return round(max((visit(s['id']) for s in steps),default=0),2)

def _scenario(steps,weekly,scale):
 total=round(sum(s['estimated_hours'] for s in steps),2)
 capacity=round(weekly*scale,2)
 weeks=math.ceil(total/capacity) if capacity else None
 return {'capacity_hours_per_week':capacity,'remaining_hours':total,'minimum_capacity_weeks':weeks,'critical_chain_hours':_critical_path(steps),'note':'Lower-bound capacity estimate; not a calendar commitment. Dependencies, staffing and competing work may delay completion.'}

def report(c,uid,wid=''):
 h=hyper.report(c,uid,wid);wid=h['workspace_id']
 if not wid:return {'workspace_id':None,'plans':[],'scenarios':{},'summary':{},'limitations':[]}
 row=c.execute('SELECT weekly_hours FROM quantum_capacity_v48 WHERE workspace_id=?',(wid,)).fetchone();weekly=row[0] if row else 40.0
 estimates=dict(c.execute('SELECT step_id,hours FROM quantum_estimates_v48 WHERE workspace_id=?',(wid,)).fetchall())
 plans=[];pending=[];today=datetime.date.today().isoformat()
 for p in h['plans']:
  steps=[]
  for s in p['steps']:
   s=dict(s);s['estimated_hours']=estimates.get(s['id']);s['needs_estimate']=s['status'] in ('todo','doing') and s['estimated_hours'] is None
   if s['status'] in ('todo','doing') and p['status']=='active':
    if s['estimated_hours'] is not None:pending.append(s)
    s['risk']='overdue' if s['due_date']<today else ('blocked' if s['depends_on'] and next((x['status'] for x in p['steps'] if x['id']==s['depends_on']),None)!='done' else 'scheduled')
   else:s['risk']='resolved'
   steps.append(s)
  plans.append({**{k:v for k,v in p.items() if k!='steps'},'steps':steps,'estimated_remaining_hours':round(sum(s['estimated_hours'] or 0 for s in steps if s['status'] in ('todo','doing')),2),'missing_estimates':sum(s['needs_estimate'] for s in steps)})
 missing=sum(p['missing_estimates'] for p in plans)
 return {'workspace_id':wid,'weekly_capacity_hours':weekly,'capacity_is_default':row is None,'plans':plans,'scenarios':{name:_scenario(pending,weekly,factor) for name,factor in [('conservative',0.5),('baseline',1),('accelerated',1.5)]},'summary':{'active_plans':sum(p['status']=='active' for p in plans),'open_milestones':h['summary']['open'],'overdue_milestones':h['summary']['overdue'],'blocked_milestones':h['summary']['blocked'],'unestimated_milestones':missing,'estimated_remaining_hours':round(sum(s['estimated_hours'] for s in pending),2)},'limitations':['Capacity is a manually entered assumption; default is 40 hours per week','Unestimated milestones are excluded from workload totals','Scenarios are illustrative capacity bounds, not date forecasts','No automated task execution, reminders or staffing allocation']}

def render(c,uid,csrf,wid=''):
 r=report(c,uid,wid);esc=lambda v:html.escape(str(v),quote=True)
 if not r['workspace_id']:return '<section class="panel"><h1>Quantum Command</h1><p>Create a workspace first.</p></section>'
 wid=r['workspace_id'];role=core._role(c,uid,wid);q=urlencode({'w':wid});hidden='<input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'">'
 out=['<section class="panel"><h1>✦ QUANTUM COMMAND V48</h1><p>Workload intelligence, milestone risk and transparent what-if capacity scenarios.</p><p><a href="/quantum-command.json?'+esc(q)+'">Export evidence JSON</a> · <a href="/hyperion?'+esc(q)+'">Open Hyperion plans</a></p><h2>Operational pulse</h2><p>'+esc(json.dumps(r['summary']))+'</p></section>']
 if role in ('owner','editor'):
  out.append('<section class="panel"><h2>Weekly delivery capacity</h2><p>Current: '+esc(r['weekly_capacity_hours'])+' hours'+(' (default assumption)' if r['capacity_is_default'] else '')+'</p><form method="post" action="/quantum-command">'+hidden+'<input type="hidden" name="action" value="capacity"><label>Hours available per week<input name="hours" type="number" min="0.01" max="10000" step="0.01" value="'+esc(r['weekly_capacity_hours'])+'" required></label><button>Save capacity</button></form></section>')
 out.append('<section class="panel"><h2>Capacity scenarios</h2><div class="grid">')
 for name,s in r['scenarios'].items():out.append('<article><h3>'+esc(name.title())+'</h3><p>'+esc(s['capacity_hours_per_week'])+' h/week · '+esc(s['minimum_capacity_weeks'])+' minimum weeks · '+esc(s['remaining_hours'])+' estimated hours</p><small>'+esc(s['note'])+'</small></article>')
 out.append('</div></section>')
 for p in r['plans']:
  out.append('<section class="panel"><h2>'+esc(p['title'])+'</h2><p>'+esc(p['status'])+' · '+esc(p['estimated_remaining_hours'])+' estimated hours remaining · '+esc(p['missing_estimates'])+' unestimated</p>')
  for s in p['steps']:
   out.append('<article style="border-top:1px solid #655777;padding:10px 0"><strong>'+esc(s['title'])+'</strong> · '+esc(s['status'])+' · '+esc(s['risk'])+' · Due '+esc(s['due_date'])+' · '+esc(s['estimated_hours'] if s['estimated_hours'] is not None else 'Not estimated')+' hours')
   if role in ('owner','editor') and p['status']=='active' and s['status'] in ('todo','doing'):
    out.append('<form method="post" action="/quantum-command">'+hidden+'<input type="hidden" name="action" value="estimate"><input type="hidden" name="step" value="'+esc(s['id'])+'"><label>Estimated effort (hours)<input type="number" name="hours" min="0.01" max="10000" step="0.01" required></label><button>Set estimate</button></form>')
   out.append('</article>')
  out.append('</section>')
 out.append('<section class="panel"><h2>Model limitations</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in r['limitations'])+'</ul></section>')
 return ''.join(out)
