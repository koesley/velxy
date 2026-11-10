"""V46 Evolution Engine: explainable opportunity-to-experiment planning, no autonomous execution."""
import html,json,secrets,time,math
from urllib.parse import urlencode
import empire_v19,neural_network_v45 as neural,autonomous_core_v43 as core,infinity_engine_v42

TEMPLATES={
 'review':('Investigate unfavorable outcomes','Review the underlying data, segment the affected records, and document plausible confounders before changing a process.','decrease'),
 'investigate':('Validate a promising intervention','Repeat a narrowly scoped, reversible human-led change while collecting a comparable baseline and follow-up.','increase'),
 'data-needed':('Improve measurement coverage','Document a measurement plan and capture sufficient observations before deciding whether a change helped.','increase')}

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS evolution_proposals_v46(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,goal_id TEXT NOT NULL,source_key TEXT NOT NULL,source_priority TEXT NOT NULL,title TEXT NOT NULL,hypothesis TEXT NOT NULL,planned_action TEXT NOT NULL,direction TEXT NOT NULL CHECK(direction IN ('increase','decrease')),status TEXT NOT NULL CHECK(status IN ('draft','dismissed','submitted')),created_by INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,experiment_id TEXT,source_evidence TEXT NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS evolution_events_v46(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,proposal_id TEXT NOT NULL,actor_id INTEGER NOT NULL,event TEXT NOT NULL,created INTEGER NOT NULL,details TEXT NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS evolution_proposals_scope_v46 ON evolution_proposals_v46(workspace_id,status,created)')
 c.execute('CREATE UNIQUE INDEX IF NOT EXISTS evolution_source_dedup_v46 ON evolution_proposals_v46(workspace_id,source_key,status) WHERE status="draft"')

def _role(c,uid,wid,write=False):
 role=empire_v19.role(c,uid,wid)
 if not role or (write and role not in ('owner','editor')):raise ValueError('Workspace unavailable or insufficient permission')
 return role

def _event(c,wid,pid,uid,kind,details=''):
 c.execute('INSERT INTO evolution_events_v46 VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,pid,uid,kind,int(time.time()),details))

def candidates(c,uid,wid):
 _role(c,uid,wid)
 r=neural.report(c,uid,wid)
 items=[]
 for opportunity in r['opportunities']:
  priority=opportunity['priority'];gid=opportunity['goal_id'];title,action,_=TEMPLATES[priority]
  goal=next((g for g in r['goal_patterns'] if g['goal_id']==gid),None)
  # Direction comes from the underlying goal's most recent experiment, never inferred from priority.
  experiment=next((e for e in r['experiments'] if e['goal_id']==gid),None)
  if not experiment:continue
  direction=experiment['direction']
  evidence=opportunity['evidence'];key=priority+':'+gid
  items.append({'source_key':key,'priority':priority,'goal_id':gid,'title':title+' — '+goal['goal_title'],'hypothesis':'A carefully controlled, human-executed review may clarify the observed pattern: '+evidence,'planned_action':action+' '+opportunity['next_step'],'direction':direction,'evidence':evidence,'completed':goal['completed'],'limitations':'Generated planning suggestion; not causal proof or a forecast.'})
 return items

def generate(c,uid,wid):
 _role(c,uid,wid,write=True)
 items=candidates(c,uid,wid);created=[];now=int(time.time())
 for item in items[:25]:
  existing=c.execute('SELECT id FROM evolution_proposals_v46 WHERE workspace_id=? AND source_key=? AND status="draft"',(wid,item['source_key'])).fetchone()
  if existing:continue
  pid=secrets.token_hex(12)
  c.execute('INSERT INTO evolution_proposals_v46(id,workspace_id,goal_id,source_key,source_priority,title,hypothesis,planned_action,direction,status,created_by,created,updated,source_evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,wid,item['goal_id'],item['source_key'],item['priority'],item['title'][:120],item['hypothesis'][:1000],item['planned_action'][:1000],item['direction'],'draft',uid,now,now,json.dumps(item,sort_keys=True)))
  _event(c,wid,pid,uid,'generated',item['evidence']);created.append(pid)
 return created

def decide(c,uid,wid,pid,action):
 _role(c,uid,wid,write=True)
 if action not in ('dismiss','submit'):raise ValueError('Unknown decision')
 row=c.execute('SELECT goal_id,title,hypothesis,planned_action,direction,status FROM evolution_proposals_v46 WHERE workspace_id=? AND id=?',(wid,pid)).fetchone()
 if not row or row[5]!='draft':raise ValueError('Only draft proposals can be changed')
 eid=None
 if action=='submit':
  # Reuses V43's baseline measurement and owner-approval gates. Submission does NOT approve or execute.
  eid=core.propose(c,uid,wid,*row[:5]);status='submitted'
 else:status='dismissed'
 c.execute('UPDATE evolution_proposals_v46 SET status=?,experiment_id=?,updated=? WHERE workspace_id=? AND id=? AND status="draft"',(status,eid,int(time.time()),wid,pid))
 _event(c,wid,pid,uid,status,'V43 experiment '+eid if eid else 'Dismissed by authorized user')
 return eid

def report(c,uid,wid=''):
 _,wid=infinity_engine_v42.scope(c,uid,wid)
 if not wid:return {'workspace_id':None,'candidates':[],'proposals':[],'events':[],'summary':{}}
 _role(c,uid,wid)
 cols=('id','goal_id','source_key','priority','title','hypothesis','planned_action','direction','status','created','experiment_id','source_evidence')
 proposals=[dict(zip(cols,r)) for r in c.execute('SELECT id,goal_id,source_key,source_priority,title,hypothesis,planned_action,direction,status,created,experiment_id,source_evidence FROM evolution_proposals_v46 WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 250',(wid,)).fetchall()]
 for p in proposals:
  p['source_evidence']=json.loads(p['source_evidence'])
 events=[dict(zip(('proposal_id','actor_id','event','created','details'),r)) for r in c.execute('SELECT proposal_id,actor_id,event,created,details FROM evolution_events_v46 WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 250',(wid,)).fetchall()]
 return {'workspace_id':wid,'candidates':candidates(c,uid,wid),'proposals':proposals,'events':events,'summary':{'draft':sum(p['status']=='draft' for p in proposals),'submitted':sum(p['status']=='submitted' for p in proposals),'dismissed':sum(p['status']=='dismissed' for p in proposals)},'limitations':['Proposals use deterministic rules, not a trained AI model','Suggestions are based on observational evidence and may be misleading','Submitting a proposal creates a proposed V43 experiment; an owner must still approve it','No customer data or external system is modified automatically','Opportunity lists and proposal history have bounded display limits']}

def render(c,uid,csrf,wid=''):
 r=report(c,uid,wid);e=lambda s:html.escape(str(s),quote=True)
 if not r['workspace_id']:return '<section class="panel"><h1>Evolution Engine V46</h1><p>Create a workspace first.</p></section>'
 wid=r['workspace_id'];role=_role(c,uid,wid);q=e(urlencode({'w':wid}));base='<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'">'
 out=['<section class="panel"><h1>✦ EVOLUTION ENGINE V46</h1><p>From observed patterns to reviewable experiments. Human approval is required. No automated business actions.</p><p><a href="/evolution-engine.json?'+q+'">Export evidence JSON</a> · <a href="/neural-network?'+q+'">Neural evidence</a> · <a href="/autonomous-core?'+q+'">Approval queue</a></p></section>']
 out.append('<section class="panel"><h2>Opportunity pipeline</h2><p>Suggested: '+str(len(r['candidates']))+' · Draft: '+str(r['summary']['draft'])+' · Submitted: '+str(r['summary']['submitted'])+' · Dismissed: '+str(r['summary']['dismissed'])+'</p>')
 if role in ('owner','editor'):out.append('<form method="post" action="/evolution-engine">'+base+'<input type="hidden" name="action" value="generate"><button>Generate reviewable proposals</button></form>')
 out.append('</section><section class="panel"><h2>Prioritized opportunities</h2>')
 for item in r['candidates'][:25]:out.append('<article style="border-top:1px solid #655777;padding:12px 0"><h3>'+e(item['title'])+'</h3><p>'+e(item['priority'])+' · '+e(item['evidence'])+'</p><p>'+e(item['limitations'])+'</p></article>')
 if not r['candidates']:out.append('<p>No opportunities meet the current evidence thresholds. Complete experiments and measurements first.</p>')
 out.append('</section><section class="panel"><h2>Proposals and approval handoff</h2>')
 for p in r['proposals']:
  out.append('<article style="border-top:1px solid #655777;padding:14px 0"><h3>'+e(p['title'])+'</h3><p><strong>'+e(p['status'])+'</strong> · '+e(p['priority'])+' · Expected direction: '+e(p['direction'])+'</p><p>'+e(p['hypothesis'])+'</p><p>Human action: '+e(p['planned_action'])+'</p>')
  if p['experiment_id']:out.append('<p>Submitted to experiment approval queue: '+e(p['experiment_id'])+'</p>')
  if p['status']=='draft' and role in ('owner','editor'):
   for action,label in [('submit','Submit for owner approval'),('dismiss','Dismiss')]:out.append('<form method="post" action="/evolution-engine">'+base+'<input type="hidden" name="proposal" value="'+e(p['id'])+'"><input type="hidden" name="action" value="'+action+'"><button>'+label+'</button></form>')
  out.append('</article>')
 if not r['proposals']:out.append('<p>Generate proposals to begin.</p>')
 out.append('</section><section class="panel"><h2>Evidence limitations</h2><ul>')
 for note in r['limitations']:out.append('<li>'+e(note)+'</li>')
 out.append('</ul></section>');return ''.join(out)
