"""Project Genesis V56.14: deterministic hypothesis discovery, adversarial review, bounded what-if worlds and evidence-bound learning. No autonomous actions."""
import hashlib, html, json, math, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_future_v56 as future

TEMPLATES=(
 ('subscription','Recurring service packages','Test whether recurring packages improve revenue stability.','customer_repeat_rate','Customers may resist subscriptions; churn can exceed acquisition gains.',2.0,1.0),
 ('premium','Premium service tier','Test a higher-value offering for a subset of customers.','willingness_to_pay','Premium demand and fulfillment cost are unknown.',3.0,2.0),
 ('retention','Customer reactivation','Test outreach to inactive customers before expanding acquisition.','customer_cohorts','Historic customer totals do not identify churn or reactivation potential.',1.5,0.8),
 ('efficiency','Workflow simplification','Test a reversible process change that could reduce operating costs.','cost_breakdown','Cutting expenses can degrade service and retention.',0.5,-2.0),
 ('bundle','Complementary offer bundles','Test whether combining offers changes average transaction value.','transaction_level_sales','Bundling may cannibalize existing purchases.',1.2,1.3),
)
POLICY='genesis-14.1'
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_genesis_sessions(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,evidence_hash TEXT NOT NULL,source_json TEXT NOT NULL,discoveries_json TEXT NOT NULL)""")
 c.execute('CREATE INDEX IF NOT EXISTS sv56_genesis_scope ON sv56_genesis_sessions(workspace_id,created)')
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_genesis_experiments(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,session_id TEXT NOT NULL,hypothesis_key TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('draft','approved','stopped','completed')),metric TEXT NOT NULL,baseline REAL NOT NULL,target REAL NOT NULL,observed REAL,notes TEXT NOT NULL DEFAULT '',reviewer INTEGER,updated INTEGER NOT NULL)""")
 c.execute('CREATE INDEX IF NOT EXISTS sv56_genesis_experiment_scope ON sv56_genesis_experiments(workspace_id,created)')

def discover(c,uid,wid):
 core.access(c,uid,wid)
 base,digest=future.evidence(c,uid,wid)
 if base['revenue']<0 or base['expenses']<0:raise ValueError('Nonnegative baseline required')
 discoveries=[]
 for key,title,claim,missing,criticism,rpct,epct in TEMPLATES:
  worlds=[]
  for label,mult in (('cautious',0.5),('balanced',1),('ambitious',1.5)):
   params=future.validated('6',str(rpct*mult),str(epct*mult),'0','0')
   simulation=future.calculate(base,params)
   worlds.append({'name':label,'assumptions':params,'hypothetical_ending_cash':simulation['ending_cash'],'first_shortfall_month':simulation['first_shortfall_month']})
  discoveries.append({'key':key,'title':title,'hypothesis':claim,'missing_evidence':[missing],'critic':criticism,'defender':'This is a candidate for a small, reversible test, not an established outcome.','referee':'UNVERIFIED — collect missing evidence and obtain approval before acting.','worlds':worlds,'suggested_experiment':{'metric':'monthly_revenue' if key!='efficiency' else 'monthly_expenses','baseline':base['revenue'] if key!='efficiency' else base['expenses'],'target':round((base['revenue']*1.02 if key!='efficiency' else base['expenses']*.98),2)}})
 return {'source':base,'evidence_hash':digest,'policy':POLICY,'hypotheses':discoveries,'limitations':['Generated from fixed local templates, not a generative AI model.','Worlds are hypothetical sensitivity calculations, not forecasts or validated causal effects.','Customer cohorts, pricing, transaction mix and competitor data are not available from aggregate metrics.','No external writes, spending, or unattended execution.']}

def create_session(c,uid,wid):
 core.access(c,uid,wid,write=True)
 report=discover(c,uid,wid);sid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_genesis_sessions VALUES(?,?,?,?,?,?,?)',(sid,wid,uid,int(time.time()),report['evidence_hash'],json.dumps(report['source'],allow_nan=False),json.dumps(report['hypotheses'],allow_nan=False)))
  core.audit(c,uid,wid,'genesis_discovery',sid)
 return sid

def history(c,uid,wid):
 core.access(c,uid,wid)
 try:current=discover(c,uid,wid)['evidence_hash']
 except ValueError:current=None
 rows=c.execute('SELECT id,created,evidence_hash,source_json,discoveries_json FROM sv56_genesis_sessions WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 15',(wid,)).fetchall()
 return [{'id':r[0],'created':r[1],'stale':r[2]!=current,'source':json.loads(r[3]),'hypotheses':json.loads(r[4])} for r in rows]

def propose(c,uid,wid,sid,key):
 core.access(c,uid,wid,write=True)
 row=c.execute('SELECT discoveries_json FROM sv56_genesis_sessions WHERE id=? AND workspace_id=?',(sid,wid)).fetchone()
 if not row:raise ValueError('Discovery session not found')
 current=history(c,uid,wid)
 if next(x for x in current if x['id']==sid)['stale']:raise ValueError('Cannot propose an experiment from stale evidence')
 hypothesis=next((x for x in json.loads(row[0]) if x['key']==key),None)
 if not hypothesis:raise ValueError('Unknown hypothesis')
 metric= hypothesis['suggested_experiment'];eid=secrets.token_hex(12);now=int(time.time())
 with c:
  c.execute('INSERT INTO sv56_genesis_experiments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,wid,sid,key,uid,now,'draft',metric['metric'],metric['baseline'],metric['target'],None,'',None,now))
  core.audit(c,uid,wid,'genesis_experiment_proposed',eid)
 return eid

def update(c,uid,wid,eid,action,observed=None,notes=''):
 core.access(c,uid,wid,owner=True)
 row=c.execute('SELECT status,baseline,target,metric FROM sv56_genesis_experiments WHERE id=? AND workspace_id=?',(eid,wid)).fetchone()
 if not row:raise ValueError('Experiment not found')
 status,baseline,target,metric=row
 allowed={'draft':{'approve':'approved','stop':'stopped'},'approved':{'complete':'completed','stop':'stopped'}}
 if action not in allowed.get(status,{}):raise ValueError('Invalid experiment transition')
 if not isinstance(notes,str) or len(notes)>1000:raise ValueError('Notes must be at most 1000 characters')
 value=None
 if action=='complete':
  try:value=float(observed)
  except (ValueError,TypeError,OverflowError) as exc:raise ValueError('Provide a measured outcome') from exc
  if not math.isfinite(value) or value<0 or value>1e12:raise ValueError('Outcome out of bounds')
  if not notes.strip():raise ValueError('Provide outcome provenance or limitations in notes')
 with c:
  c.execute('UPDATE sv56_genesis_experiments SET status=?,observed=?,notes=?,reviewer=?,updated=? WHERE id=? AND workspace_id=?',(allowed[status][action],value,notes,uid,int(time.time()),eid,wid))
  core.audit(c,uid,wid,'genesis_experiment_'+action,eid)

def experiments(c,uid,wid):
 core.access(c,uid,wid)
 rows=c.execute('SELECT id,session_id,hypothesis_key,status,metric,baseline,target,observed,notes,created FROM sv56_genesis_experiments WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 50',(wid,)).fetchall()
 return [dict(zip(('id','session_id','hypothesis_key','status','metric','baseline','target','observed','notes','created'),r)) for r in rows]

def render(c,uid,csrf,wid):
 core.access(c,uid,wid);e=lambda v:html.escape(str(v),quote=True);q=quote(wid,safe='')
 out=['<div class="genesis-shell"><section class="genesis-hero"><p class="genesis-kicker">✦ VELXTRIA / PROJECT GENESIS · MILESTONE 14</p><h1>Discover the <em>unimagined.</em></h1><p>Question the obvious. Explore parallel possibilities. Challenge assumptions. Test before you trust.</p><form method="post" action="/sovereign-genesis-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="discover"><button class="genesis-btn">✦ Start discovery session</button></form><p class="genesis-small">Local deterministic analysis · No autonomous actions · Hypotheses are not verified findings</p></section>']
 try:live=discover(c,uid,wid)
 except ValueError as exc:out.append('<section class="genesis-card"><h2>Evidence needed</h2><p>'+e(exc)+'</p><a href="/sovereign-v56?w='+q+'">Import business metrics →</a></section>');live=None
 sessions=history(c,uid,wid);exp=experiments(c,uid,wid)
 out.append('<div class="genesis-stats"><div><b>'+str(len(sessions))+'</b><span>Discovery sessions</span></div><div><b>'+str(len(exp))+'</b><span>Experiments</span></div><div><b>'+str(sum(x['status']=='completed' for x in exp))+'</b><span>Measured outcomes</span></div></div>')
 if sessions:
  session=sessions[0];out.append('<section class="genesis-section"><h2>Latest discovery <small>'+('STALE · Refresh evidence' if session['stale'] else 'Evidence snapshot current')+'</small></h2><div class="genesis-grid">')
  for h in session['hypotheses']:
   out.append('<article class="genesis-card"><span class="genesis-kicker">POSSIBILITY / '+e(h['key'].upper())+'</span><h3>'+e(h['title'])+'</h3><p>'+e(h['hypothesis'])+'</p><details><summary>Parallel worlds</summary><div class="genesis-worlds">')
   for w in h['worlds']:out.append('<div><strong>'+e(w['name'])+'</strong><span>Illustrative cash: '+e(w['hypothetical_ending_cash'])+'</span></div>')
   out.append('</div></details><details><summary>Adversarial review & blind spots</summary><p><b>Critic:</b> '+e(h['critic'])+'</p><p><b>Defender:</b> '+e(h['defender'])+'</p><p><b>Referee:</b> '+e(h['referee'])+'</p><p>Missing: '+e(', '.join(h['missing_evidence']))+'</p></details>')
   if not session['stale']:out.append('<form method="post" action="/sovereign-genesis-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="propose"><input type="hidden" name="session" value="'+e(session['id'])+'"><input type="hidden" name="hypothesis" value="'+e(h['key'])+'"><button class="genesis-btn genesis-secondary">Design experiment</button></form>')
   out.append('</article>')
  out.append('</div></section>')
 if exp:
  out.append('<section class="genesis-section"><h2>Evolution lab</h2><div class="genesis-grid">')
  for x in exp:
   out.append('<article class="genesis-card"><span class="genesis-kicker">'+e(x['status'].upper())+'</span><h3>'+e(x['hypothesis_key'].replace('_',' ').title())+'</h3><p>Metric: '+e(x['metric'])+' · Baseline: '+e(x['baseline'])+' · Target: '+e(x['target'])+'</p>')
   if x['observed'] is not None:out.append('<p><strong>Observed: '+e(x['observed'])+'</strong> · Change from baseline: '+e(round(x['observed']-x['baseline'],2))+' (not proof of causation)</p><p>'+e(x['notes'])+'</p>')
   if x['status'] in ('draft','approved'):
    for action in (('approve','stop') if x['status']=='draft' else ('complete','stop')):
     out.append('<form method="post" action="/sovereign-genesis-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="'+action+'"><input type="hidden" name="experiment" value="'+e(x['id'])+'">')
     if action=='complete':out.append('<label>Measured value<input name="observed" type="number" min="0" step="any" required></label><label>Source and limitations<textarea name="notes" maxlength="1000" required></textarea></label>')
     out.append('<button class="genesis-btn genesis-secondary">'+action.title()+'</button></form>')
   out.append('</article>')
  out.append('</div></section>')
 out.append('<section class="genesis-card"><h2>Scientific boundaries</h2><p>Ideas are generated from fixed templates and aggregate business metrics. No LLM, causal inference, external platform writes, automated rollout, or autonomous spending. Approvals authorize experiment tracking only. A recorded outcome must be entered by an owner and may be influenced by external factors.</p><a href="/sovereign-genesis-v56.json?w='+q+'">View workspace JSON history →</a></section></div>')
 return ''.join(out)
