"""Omniverse V57.4: evidence-linked deterministic scenario and decision laboratory."""
import html,json,math,secrets,time
import sovereign_v56 as core
import sovereign_council_v57 as council

def init(c):
 council.init(c)
 c.execute("CREATE TABLE IF NOT EXISTS ov57_lab_plans(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,investigation_id TEXT NOT NULL,name TEXT NOT NULL,metric TEXT NOT NULL,baseline REAL NOT NULL,unit TEXT NOT NULL,horizon INTEGER NOT NULL,assumptions TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',created_by INTEGER NOT NULL,created INTEGER NOT NULL,approved_by INTEGER,review_note TEXT NOT NULL DEFAULT '')")
 c.execute('CREATE INDEX IF NOT EXISTS ov57_lab_scope ON ov57_lab_plans(workspace_id,investigation_id)')
 c.execute("CREATE TABLE IF NOT EXISTS ov57_lab_options(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,plan_id TEXT NOT NULL,name TEXT NOT NULL,change_pct REAL NOT NULL,cost REAL NOT NULL,risk_pct REAL NOT NULL,created INTEGER NOT NULL)")
 c.execute('CREATE INDEX IF NOT EXISTS ov57_lab_options_scope ON ov57_lab_options(workspace_id,plan_id)')
 c.execute('CREATE TABLE IF NOT EXISTS ov57_lab_measurements(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,plan_id TEXT NOT NULL,observed REAL NOT NULL,evidence TEXT NOT NULL,recorded_by INTEGER NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS ov57_lab_measurements_scope ON ov57_lab_measurements(workspace_id,plan_id)')
def txt(s,n=300):
 if not isinstance(s,str) or not s.strip() or len(s.strip())>n or any(ord(ch)<32 and ch not in '\n\t' for ch in s):raise ValueError('Invalid text')
 return s.strip()
def number(s,low,high):
 try:v=float(s)
 except (ValueError,TypeError,OverflowError):raise ValueError('Invalid numeric value')
 if not math.isfinite(v) or not low<=v<=high:raise ValueError('Numeric value outside allowed range')
 return v
def plan(c,uid,wid,iid,name,metric,baseline,unit,horizon,assumptions):
 core.access(c,uid,wid,write=True);init(c)
 row=c.execute('SELECT status FROM ov57_investigations WHERE id=? AND workspace_id=?',(iid,wid)).fetchone()
 if not row:raise ValueError('Investigation not found')
 name=txt(name,120);metric=txt(metric,100);unit=txt(unit,24);assumptions=txt(assumptions,1000)
 baseline=number(baseline,0,1e12);horizon=int(number(horizon,1,365));pid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO ov57_lab_plans(id,workspace_id,investigation_id,name,metric,baseline,unit,horizon,assumptions,status,created_by,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,wid,iid,name,metric,baseline,unit,horizon,assumptions,'draft',uid,int(time.time())))
  core.audit(c,uid,wid,'lab_plan_created',pid)
 return pid
def option(c,uid,wid,pid,name,change_pct,cost,risk_pct):
 core.access(c,uid,wid,write=True);init(c)
 row=c.execute('SELECT status FROM ov57_lab_plans WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
 if not row or row[0]!='draft':raise ValueError('Only draft plans can be changed')
 name=txt(name,120);change=number(change_pct,-100,1000);cost=number(cost,0,1e12);risk=number(risk_pct,0,100)
 with c:
  count=c.execute('SELECT COUNT(*) FROM ov57_lab_options WHERE workspace_id=? AND plan_id=?',(wid,pid)).fetchone()[0]
  if count>=12:raise ValueError('Maximum 12 options per plan')
  oid=secrets.token_hex(12)
  c.execute('INSERT INTO ov57_lab_options VALUES(?,?,?,?,?,?,?,?)',(oid,wid,pid,name,change,cost,risk,int(time.time())))
  core.audit(c,uid,wid,'lab_option_added',pid)
 return oid
def review(c,uid,wid,pid,decision,reason):
 core.access(c,uid,wid,write=True,owner=True);init(c)
 if decision not in ('approved','rejected'):raise ValueError('Invalid review')
 reason=txt(reason,600)
 with c:
  row=c.execute('SELECT status FROM ov57_lab_plans WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
  if not row or row[0]!='draft':raise ValueError('Plan is not a draft')
  if decision=='approved' and not c.execute('SELECT 1 FROM ov57_lab_options WHERE plan_id=? AND workspace_id=?',(pid,wid)).fetchone():raise ValueError('Add an option before approval')
  c.execute('UPDATE ov57_lab_plans SET status=?,approved_by=?,review_note=? WHERE id=? AND workspace_id=?',(decision,uid,reason,pid,wid))
  core.audit(c,uid,wid,'lab_plan_'+decision,pid)
def measure(c,uid,wid,pid,observed,evidence):
 core.access(c,uid,wid,write=True);init(c)
 observed=number(observed,0,1e12);evidence=txt(evidence,600)
 with c:
  row=c.execute('SELECT status FROM ov57_lab_plans WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
  if not row or row[0]!='approved':raise ValueError('Plan must be approved')
  mid=secrets.token_hex(12)
  c.execute('INSERT INTO ov57_lab_measurements VALUES(?,?,?,?,?,?,?)',(mid,wid,pid,observed,evidence,uid,int(time.time())))
  core.audit(c,uid,wid,'lab_measurement_recorded',pid)
 return mid
def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 investigations=[dict(id=r[0],question=r[1]) for r in c.execute('SELECT id,question FROM ov57_investigations WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,))]
 plans=[]
 for r in c.execute('SELECT id,investigation_id,name,metric,baseline,unit,horizon,assumptions,status,review_note FROM ov57_lab_plans WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,)):
  p=dict(zip(('id','investigation_id','name','metric','baseline','unit','horizon','assumptions','status','review_note'),r))
  p['options']=[]
  for o in c.execute('SELECT name,change_pct,cost,risk_pct FROM ov57_lab_options WHERE workspace_id=? AND plan_id=? ORDER BY created,id',(wid,p['id'])):
   name,change,cost,risk=o;projected=p['baseline']*(1+change/100);p['options'].append(dict(name=name,change_pct=change,cost=cost,risk_pct=risk,projected=round(projected,4),risk_adjusted=round(projected*(1-risk/100),4)))
  p['measurements']=[dict(observed=m[0],evidence=m[1],created=m[2],delta=round(m[0]-p['baseline'],4),delta_pct=round((m[0]-p['baseline'])/p['baseline']*100,2) if p['baseline'] else None) for m in c.execute('SELECT observed,evidence,created FROM ov57_lab_measurements WHERE workspace_id=? AND plan_id=? ORDER BY created DESC,id DESC LIMIT 30',(wid,p['id']))]
  plans.append(p)
 return dict(workspace_id=wid,role=role,investigations=investigations,plans=plans,counts=dict(plans=len(plans),approved=sum(p['status']=='approved' for p in plans),options=sum(len(p['options']) for p in plans),measurements=sum(len(p['measurements']) for p in plans)),limitations=['Scenarios are arithmetic projections from user-entered assumptions, not predictions.','Risk-adjusted values are illustrative sensitivity figures, not probability-calibrated forecasts.','Measurements are user-reported and do not establish causation.','Approval records a decision; no external actions or spending occur.'])
def render(c,uid,wid,csrf):
 d=overview(c,uid,wid);h=lambda x:html.escape(str(x),quote=True);hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">';url='/sovereign-lab-v57'
 out=['<section class="ov-hero"><span>PROJECT OMNIVERSE · DECISION LABORATORY</span><h1>Explore futures. Measure reality.</h1><p>Turn Council investigations into comparable scenarios with explicit assumptions, human decisions, and evidence-linked measurements.</p><a href="/sovereign-council-v57?w='+h(wid)+'">Intelligence Council</a></section>']
 out.append('<section class="ov-metrics">'+''.join('<article class="ov-card"><strong>'+h(k.title())+'</strong><span>'+h(v)+'</span></article>' for k,v in d['counts'].items())+'</section>')
 if d['role'] in ('owner','editor'):
  opts=''.join('<option value="'+h(i['id'])+'">'+h(i['question'])+'</option>' for i in d['investigations'])
  out.append('<section class="ov-panel"><h2>Create scenario study</h2><form method="post" action="'+url+'">'+hidden+'<label>Council investigation<select name="investigation_id" required>'+opts+'</select></label><label>Study name<input name="name" maxlength="120" required></label><label>Metric<input name="metric" maxlength="100" placeholder="Monthly revenue" required></label><label>Baseline<input type="number" step="any" min="0" name="baseline" required></label><label>Unit<input name="unit" maxlength="24" value="USD" required></label><label>Horizon (days)<input type="number" name="horizon" min="1" max="365" value="30" required></label><label>Assumptions<input name="assumptions" maxlength="1000" required></label><button name="action" value="create">Create study</button></form></section>')
 for p in d['plans']:
  out.append('<section class="ov-panel" style="margin-top:18px"><h2>'+h(p['name'])+'</h2><p>'+h(p['metric'])+' · baseline '+h(p['baseline'])+' '+h(p['unit'])+' · '+h(p['horizon'])+' days · <strong>'+h(p['status'])+'</strong></p><p>Assumptions: '+h(p['assumptions'])+'</p>')
  for o in p['options']:out.append('<article class="ov-job"><strong>'+h(o['name'])+'</strong><p>Change: '+h(o['change_pct'])+'% · Estimated cost: '+h(o['cost'])+' · Assumed risk: '+h(o['risk_pct'])+'%</p><p>Projected metric: '+h(o['projected'])+' '+h(p['unit'])+' · illustrative risk-adjusted: '+h(o['risk_adjusted'])+'</p></article>')
  for m in p['measurements']:out.append('<article class="ov-job"><strong>Recorded observation: '+h(m['observed'])+' '+h(p['unit'])+'</strong><p>Baseline difference: '+h(m['delta'])+' · '+h(m['delta_pct'] if m['delta_pct'] is not None else 'undefined (zero baseline)')+'%</p><small>'+h(m['evidence'])+'</small></article>')
  if p['status']=='draft' and d['role'] in ('owner','editor'):
   out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="plan" value="'+h(p['id'])+'"><label>Option name<input name="name" maxlength="120" required></label><label>Assumed change %<input name="change_pct" type="number" step="any" min="-100" max="1000" required></label><label>Estimated cost<input name="cost" type="number" step="any" min="0" required></label><label>Assumed risk %<input name="risk_pct" type="number" step="any" min="0" max="100" required></label><button name="action" value="option">Add scenario</button></form>')
  if p['status']=='draft' and d['role']=='owner':out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="plan" value="'+h(p['id'])+'"><label>Decision<select name="decision"><option>approved</option><option>rejected</option></select></label><label>Review reason<input name="reason" maxlength="600" required></label><button name="action" value="review">Record owner review</button></form>')
  if p['status']=='approved' and d['role'] in ('owner','editor'):out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="plan" value="'+h(p['id'])+'"><label>Observed metric<input type="number" step="any" min="0" name="observed" required></label><label>Evidence reference and limitations<input name="evidence" maxlength="600" required></label><button name="action" value="measure">Record observation</button></form>')
  if p['review_note']:out.append('<p>Owner review: '+h(p['review_note'])+'</p>')
  out.append('</section>')
 out.append('<section class="ov-panel"><h2>Interpretation safeguards</h2>'+''.join('<p>'+h(x)+'</p>' for x in d['limitations'])+'</section>')
 return ''.join(out)
