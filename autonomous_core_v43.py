"""V43 Autonomous Core: approval-gated, human-executed measurable experiments.
No background agents, external side effects, or automatic customer-data changes.
"""
import html,json,math,secrets,time
from urllib.parse import urlencode
import empire_v19,nexus_v25,infinity_engine_v42

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS core_experiments_v43(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,goal_id TEXT NOT NULL,title TEXT NOT NULL,hypothesis TEXT NOT NULL,planned_action TEXT NOT NULL,success_direction TEXT NOT NULL CHECK(success_direction IN ('increase','decrease')),status TEXT NOT NULL CHECK(status IN ('proposed','approved','rejected','completed','cancelled')),baseline REAL NOT NULL,baseline_sample INTEGER NOT NULL,followup REAL,followup_sample INTEGER,created_by INTEGER NOT NULL,reviewed_by INTEGER,created INTEGER NOT NULL,reviewed INTEGER,completed INTEGER,notes TEXT NOT NULL DEFAULT '')''')
 c.execute('''CREATE TABLE IF NOT EXISTS core_events_v43(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,experiment_id TEXT NOT NULL,actor_id INTEGER NOT NULL,event TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS core_experiments_scope_v43 ON core_experiments_v43(workspace_id,created)')
 c.execute('CREATE INDEX IF NOT EXISTS core_events_scope_v43 ON core_events_v43(workspace_id,experiment_id,created)')

def _role(c,uid,wid,write=False,owner=False):
 r=empire_v19.role(c,uid,wid)
 if not r or (write and r not in ('owner','editor')) or (owner and r!='owner'):raise ValueError('Workspace unavailable or insufficient permission')
 return r

def _event(c,wid,eid,uid,kind,detail):
 c.execute('INSERT INTO core_events_v43 VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,eid,uid,kind,detail,int(time.time())))

def _clean(value,label,minimum=3,maximum=500):
 value=str(value or '').strip()
 if not minimum<=len(value)<=maximum:raise ValueError(label+' must be '+str(minimum)+'-'+str(maximum)+' characters')
 return value

def _measurement(c,uid,wid,gid):
 result=nexus_v25.measure(c,uid,wid,gid)
 v=result['value']
 if v is None or not math.isfinite(float(v)):raise ValueError('Goal needs a valid measurement before proceeding')
 return result

def propose(c,uid,wid,gid,title,hypothesis,action,direction):
 _role(c,uid,wid,write=True)
 nexus_v25._goal(c,uid,wid,gid)
 title=_clean(title,'Title',3,120);hypothesis=_clean(hypothesis,'Hypothesis',10,1000);action=_clean(action,'Planned human action',10,1000)
 if direction not in ('increase','decrease'):raise ValueError('Choose an expected direction')
 m=_measurement(c,uid,wid,gid)
 eid=secrets.token_hex(12);ts=int(time.time())
 c.execute('INSERT INTO core_experiments_v43(id,workspace_id,goal_id,title,hypothesis,planned_action,success_direction,status,baseline,baseline_sample,created_by,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,wid,gid,title,hypothesis,action,direction,'proposed',m['value'],m['sampled_records'],uid,ts))
 _event(c,wid,eid,uid,'proposed',json.dumps({'baseline':m['value'],'sampled':m['sampled_records'],'direction':direction}))
 return eid

def decision(c,uid,wid,eid,approve):
 _role(c,uid,wid,owner=True)
 r=c.execute('SELECT status FROM core_experiments_v43 WHERE workspace_id=? AND id=?',(wid,eid)).fetchone()
 if not r or r[0]!='proposed':raise ValueError('Only proposed experiments can be reviewed')
 status='approved' if approve else 'rejected'
 c.execute('UPDATE core_experiments_v43 SET status=?,reviewed_by=?,reviewed=? WHERE workspace_id=? AND id=? AND status=?',(status,uid,int(time.time()),wid,eid,'proposed'))
 _event(c,wid,eid,uid,status,'Owner decision; no action executed')

def complete(c,uid,wid,eid,notes):
 _role(c,uid,wid,write=True)
 row=c.execute('SELECT goal_id,status,baseline,success_direction FROM core_experiments_v43 WHERE workspace_id=? AND id=?',(wid,eid)).fetchone()
 if not row or row[1]!='approved':raise ValueError('Only approved experiments can be completed')
 notes=_clean(notes,'Outcome notes',10,1500)
 m=_measurement(c,uid,wid,row[0]);delta=round(m['value']-row[2],4)
 c.execute('UPDATE core_experiments_v43 SET status=?,followup=?,followup_sample=?,completed=?,notes=? WHERE workspace_id=? AND id=? AND status=?',('completed',m['value'],m['sampled_records'],int(time.time()),notes,wid,eid,'approved'))
 _event(c,wid,eid,uid,'completed',json.dumps({'followup':m['value'],'sampled':m['sampled_records'],'delta':delta,'interpretation':'Descriptive change only; not causal proof'}))
 return delta

def cancel(c,uid,wid,eid):
 _role(c,uid,wid,owner=True)
 row=c.execute('SELECT status FROM core_experiments_v43 WHERE workspace_id=? AND id=?',(wid,eid)).fetchone()
 if not row or row[0]!='approved':raise ValueError('Only approved experiments can be cancelled')
 c.execute('UPDATE core_experiments_v43 SET status=? WHERE workspace_id=? AND id=?',('cancelled',wid,eid))
 _event(c,wid,eid,uid,'cancelled','Owner cancelled; no action executed')

def report(c,uid,wid=''):
 ws,wid=infinity_engine_v42.scope(c,uid,wid)
 if not wid:return {'workspace_id':None,'experiments':[],'summary':{},'events':[]}
 rows=c.execute('''SELECT e.id,e.goal_id,g.title,e.title,e.hypothesis,e.planned_action,e.success_direction,e.status,e.baseline,e.baseline_sample,e.followup,e.followup_sample,e.notes,e.created FROM core_experiments_v43 e JOIN nexus_goals g ON g.id=e.goal_id AND g.workspace_id=e.workspace_id WHERE e.workspace_id=? ORDER BY e.created DESC,e.id DESC LIMIT 100''',(wid,)).fetchall()
 keys=('id','goal_id','goal_title','title','hypothesis','planned_action','direction','status','baseline','baseline_sample','followup','followup_sample','notes','created')
 experiments=[]
 for row in rows:
  d=dict(zip(keys,row));d['delta']=round(d['followup']-d['baseline'],4) if d['followup'] is not None else None
  d['direction_matched']=(d['delta']>0 if d['direction']=='increase' else d['delta']<0) if d['delta'] is not None else None
  experiments.append(d)
 events=[dict(zip(('experiment_id','actor_id','event','details','created'),r)) for r in c.execute('SELECT experiment_id,actor_id,event,details,created FROM core_events_v43 WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 200',(wid,)).fetchall()]
 return {'workspace_id':wid,'experiments':experiments,'events':events,'summary':{s:sum(e['status']==s for e in experiments) for s in ('proposed','approved','rejected','completed','cancelled')},'limitations':['No changes or tasks are executed automatically','Baseline and follow-up are descriptive measurements, not causal evidence','Recent record sampling and concurrent changes may distort comparisons']}

def render(c,uid,csrf,wid=''):
 esc=lambda x:html.escape(str(x),quote=True)
 r=report(c,uid,wid)
 if not r['workspace_id']:return '<section class="panel"><h1>Autonomous Core V43</h1><p>Create a workspace first.</p><a href="/empire">Create workspace</a></section>'
 wid=r['workspace_id'];role=_role(c,uid,wid);q=urlencode({'w':wid});base='<input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'">'
 out=['<section class="panel"><h1>✦ AUTONOMOUS CORE V43</h1><p>Human-approved business experiments, measurable baselines, and outcome evidence. No automatic execution or profit guarantees.</p><p><a href="/autonomous-core.json?'+esc(q)+'">Export JSON evidence</a> · <a href="/infinity-engine?'+esc(q)+'">Infinity Engine insights</a></p></section>']
 out.append('<section class="panel"><h2>Experiment pipeline</h2><p>'+''.join(esc(k.title())+': <strong>'+str(v)+'</strong> &nbsp; ' for k,v in r['summary'].items())+'</p></section>')
 if role in ('owner','editor'):
  goals=c.execute('SELECT id,title FROM nexus_goals WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()
  out.append('<section class="panel"><h2>Propose a measurable experiment</h2>')
  if not goals:out.append('<p>Create a measurable goal in <a href="/nexus-intelligence?'+esc(q)+'">Nexus Intelligence</a> first.</p>')
  else:
   out.append('<form method="post" action="/autonomous-core">'+base+'<input type="hidden" name="action" value="propose"><label>Goal<select name="goal">'+''.join('<option value="'+esc(g)+'">'+esc(n)+'</option>' for g,n in goals)+'</select></label><label>Experiment title<input name="title" maxlength="120" required></label><label>Hypothesis<textarea name="hypothesis" maxlength="1000" required></textarea></label><label>Planned action (performed manually)<textarea name="planned_action" maxlength="1000" required></textarea></label><label>Expected measurement direction<select name="direction"><option value="increase">Increase</option><option value="decrease">Decrease</option></select></label><button>Submit for owner approval</button></form>')
  out.append('</section>')
 out.append('<section class="panel"><h2>Experiments</h2>')
 for e in r['experiments']:
  out.append('<article style="border-top:1px solid #655777;padding:16px 0"><h3>'+esc(e['title'])+'</h3><p><strong>'+esc(e['status'].upper())+'</strong> · '+esc(e['goal_title'])+'</p><p>Hypothesis: '+esc(e['hypothesis'])+'</p><p>Human action: '+esc(e['planned_action'])+'</p><p>Baseline '+esc(e['baseline'])+' ('+esc(e['baseline_sample'])+' sampled) · Follow-up '+esc(e['followup'] if e['followup'] is not None else 'not recorded')+' · Delta '+esc(e['delta'] if e['delta'] is not None else 'pending')+'</p>')
  if e['status']=='completed':out.append('<p>Expected direction matched: '+('yes' if e['direction_matched'] else 'no or unchanged')+' · Notes: '+esc(e['notes'])+'. This is not causal proof.</p>')
  if role=='owner' and e['status']=='proposed':
   for action,label in [('approve','Approve'),('reject','Reject')]:out.append('<form method="post" action="/autonomous-core">'+base+'<input type="hidden" name="experiment" value="'+esc(e['id'])+'"><input type="hidden" name="action" value="'+action+'"><button>'+label+'</button></form>')
  if e['status']=='approved' and role in ('owner','editor'):out.append('<form method="post" action="/autonomous-core">'+base+'<input type="hidden" name="experiment" value="'+esc(e['id'])+'"><input type="hidden" name="action" value="complete"><label>What was done, and what else changed?<textarea name="notes" maxlength="1500" required></textarea></label><button>Record follow-up measurement</button></form>')
  if e['status']=='approved' and role=='owner':out.append('<form method="post" action="/autonomous-core">'+base+'<input type="hidden" name="experiment" value="'+esc(e['id'])+'"><input type="hidden" name="action" value="cancel"><button>Cancel experiment</button></form>')
  out.append('</article>')
 if not r['experiments']:out.append('<p>No experiments yet.</p>')
 out.append('</section><section class="panel"><h2>Audit trail</h2><ul>')
 for event in r['events'][:40]:out.append('<li>'+esc(event['event'])+' · actor '+esc(event['actor_id'])+' · '+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(event['created'])))+'</li>')
 out.append('</ul><p>Measurement changes are observational, not proof the intervention caused an outcome.</p></section>')
 return ''.join(out)
