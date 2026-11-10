"""Milestone 10: auditable deterministic executive review, not autonomous LLM agents."""
import hashlib, html, json, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_intelligence_v56 as council
import sovereign_future_v56 as future

POLICY='executive-council-v2.0.1'
OBJECTIVES=('overview','revenue','costs','operations')

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_executive_runs(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, actor INTEGER NOT NULL, created INTEGER NOT NULL, objective TEXT NOT NULL, evidence_hash TEXT NOT NULL, result_json TEXT NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_executive_scope ON sv56_executive_runs(workspace_id,created)')

def evidence(c,uid,wid):
 core.access(c,uid,wid)
 report=core.report(c,uid,wid)
 latest=c.execute('SELECT MAX(period) FROM sv56_metrics WHERE workspace_id=?',(wid,)).fetchone()[0]
 digest=hashlib.sha256(json.dumps({'policy':POLICY,'facts':report['facts'],'conflicts':report['conflicting_periods'],'latest_period':latest},sort_keys=True,allow_nan=False).encode()).hexdigest()
 return report,digest,latest

def evaluate(report,objective,latest):
 if objective not in OBJECTIVES:raise ValueError('Unsupported objective')
 base=council.evaluate(report,objective)
 facts=report['facts']; conflicts=report['conflicting_periods']; recent=facts[-1] if facts else None
 specialists=[]
 def specialist(name,stance,claim,refs,limits):
  specialists.append({'specialist':name,'stance':stance,'claim':claim,'evidence':refs,'limitations':limits})
 refs={'period':recent['period'],'source_import_id':recent['source_import_id']} if recent else {'source_import_id':None}
 if recent:
  margin=round(recent['revenue']-recent['expenses'],2)
  specialist('finance','review' if margin<0 else 'observe',f'Latest revenue minus expenses is {margin:.2f}',refs,'This is not accounting profit or verified cash flow.')
  specialist('revenue','review' if len(facts)<2 else 'observe','Revenue comparison requires two verified periods' if len(facts)<2 else base['findings'][0]['headline'] if objective in ('overview','revenue') else 'Revenue recorded for latest period',refs,'No evidence of causal impact or future growth.')
  specialist('operations','review' if recent['leads']==0 else 'observe','Latest leads: '+str(recent['leads'])+'; customers: '+str(recent['customers']),refs,'Customers and leads may not belong to the same cohort.')
 else:
  for name in ('finance','revenue','operations'):specialist(name,'insufficient','No unconflicted monthly metrics available',refs,'Import and reconcile source records first.')
 unsafe=bool(conflicts) or (latest is not None and latest in conflicts)
 specialist('risk','block' if unsafe else 'caution','Conflicting source periods exist' if unsafe else 'No source conflicts detected',{'conflicting_periods':conflicts},'Absence of detected conflicts is not proof of completeness.')
 objections=[]
 if unsafe:objections.append({'raised_by':'risk','against':'executive','reason':'Conflicting imports make recommendations unreliable.','resolution':'Reconcile source imports; no action recommendation.'})
 if len(facts)<2:objections.append({'raised_by':'revenue','against':'executive','reason':'Insufficient history for comparisons.','resolution':'Collect another verified monthly period.'})
 if recent and recent['leads'] and recent['customers']>recent['leads']:objections.append({'raised_by':'operations','against':'revenue','reason':'Customers exceed same-period leads; cohort definition may differ.','resolution':'Validate funnel attribution before claiming conversion.'})
 opportunities=base['opportunities']
 verdict='BLOCKED_DATA_QUALITY' if unsafe else 'INSUFFICIENT_EVIDENCE' if len(facts)<2 else 'REVIEW_ONLY'
 recommendations=[]
 if verdict=='REVIEW_ONLY':
  for o in opportunities[:3]:recommendations.append({'title':o['title'],'evidence_source_import_ids':o['source_import_ids'],'action':'Review supporting records and compare hypothetical strategies before any approval.','uncertainty':o['uncertainty']})
 return {'policy':POLICY,'objective':objective,'verdict':verdict,'specialists':specialists,'critic_objections':objections,'recommendations':recommendations,'prior_council':base,'decision':'Reconcile conflicting evidence first.' if unsafe else 'Gather more evidence.' if len(facts)<2 else 'Human review only; no strategy approval or execution.','limits':['Deterministic rules, not independent AI agents.','No autonomous execution, external calls, or financial guarantees.','Only manually imported tenant-scoped metrics are assessed.']}

def run(c,uid,wid,objective):
 core.access(c,uid,wid,write=True)
 report,digest,latest=evidence(c,uid,wid)
 result=evaluate(report,objective,latest)
 rid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_executive_runs VALUES(?,?,?,?,?,?,?)',(rid,wid,uid,int(time.time()),objective,digest,json.dumps(result,allow_nan=False)))
  core.audit(c,uid,wid,'executive_council_review',rid)
 return rid

def history(c,uid,wid):
 core.access(c,uid,wid)
 _,current,_=evidence(c,uid,wid)
 rows=c.execute('SELECT id,actor,created,objective,evidence_hash,result_json FROM sv56_executive_runs WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 30',(wid,)).fetchall()
 return [{'id':rid,'actor':actor,'created':created,'objective':objective,'stale':digest!=current,'result':json.loads(payload)} for rid,actor,created,objective,digest,payload in rows]

def render(c,uid,csrf,wid):
 core.access(c,uid,wid)
 esc=lambda x:html.escape(str(x),quote=True)
 out=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 10</p><h1>Executive Intelligence Council 2.0</h1><p>Evidence-bound specialist reviews, explicit objections and a conservative executive verdict. This is deterministic analysis, not independent AI agents.</p><form method="post" action="/sovereign-executive-v56"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><label>Review objective<select name="objective">']
 for x in OBJECTIVES:out.append('<option value="'+x+'">'+x.title()+'</option>')
 out.append('</select></label><button>Run executive review</button></form><p><a href="/sovereign-executive-v56.json?w='+quote(wid,safe='')+'">Export review history JSON</a></p></section>')
 entries=history(c,uid,wid)
 for item in entries:
  r=item['result'];out.append('<section class="panel"><h2>Review '+esc(item['id'])+'</h2><p><strong>'+esc(r['verdict'])+'</strong> · '+('STALE — evidence changed' if item['stale'] else 'Evidence current')+'</p><p>'+esc(r['decision'])+'</p>')
  for x in r['specialists']:out.append('<article class="sv56-card"><h3>'+esc(x['specialist'].title())+' · '+esc(x['stance'])+'</h3><p>'+esc(x['claim'])+'</p><p>Evidence: '+esc(json.dumps(x['evidence'],sort_keys=True))+'</p><p>Limitations: '+esc(x['limitations'])+'</p></article>')
  out.append('<h3>Critic objections</h3>')
  for o in r['critic_objections']:out.append('<p>'+esc(o['raised_by'])+': '+esc(o['reason'])+' Resolution: '+esc(o['resolution'])+'</p>')
  if not r['critic_objections']:out.append('<p>No rule-triggered objections; underlying evidence still needs human validation.</p>')
  out.append('<h3>Recommendations for human review</h3>')
  for rec in r['recommendations']:out.append('<p>'+esc(rec['title'])+' — '+esc(rec['action'])+'</p>')
  out.append('</section>')
 if not entries:out.append('<section class="panel"><p>No reviews yet. Import monthly metrics, then run a review.</p></section>')
 return ''.join(out)
