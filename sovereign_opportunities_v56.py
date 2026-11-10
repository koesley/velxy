"""Sovereign milestone 5: evidence-backed, non-autonomous opportunity discovery."""
import hashlib, html, json, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_intelligence_v56 as council
import sovereign_sync_v56 as sync

POLICY_VERSION='opportunity-rules-1'

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_opportunity_runs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,evidence_hash TEXT NOT NULL,policy_version TEXT NOT NULL,result_json TEXT NOT NULL CHECK(length(result_json)<=100000))''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_opportunity_scope ON sv56_opportunity_runs(workspace_id,created)')

def discover(report,sync_state):
 facts=report['facts']; conflicts=set(report['conflicting_periods']); linked={i['period']:i['source_import_id'] for i in sync_state['links']}
 opportunities=[]
 for raw in report['opportunities']:
  e=raw['evidence']; periods=[e['previous_period'],e['current_period']]; sources=e['source_import_ids']
  verified=all(p not in conflicts and linked.get(p)==src for p,src in zip(periods,sources))
  if not verified:continue
  key=raw['key']; code=key.split(':',1)[0]
  magnitude=abs(float(e['current'])-float(e['previous']))
  baseline=abs(float(e['previous']))
  relative=(magnitude/baseline) if baseline else None
  severity='high' if relative is not None and relative>=.2 else 'moderate' if relative is not None and relative>=.05 else 'low'
  opportunities.append({'key':key,'title':raw['title'],'category':code,'severity':severity,
   'relative_change_pct':round(relative*100,2) if relative is not None else None,
   'evidence':e,'recommended_review':raw['recommended_action'],
   'data_quality':'reconciled_source_links','priority_basis':'Magnitude of observed two-period change; not expected value or ROI.',
   'uncertainty':'No causal attribution, predictive confidence, or verified monetary upside.',
   'approval_required':True,'execution':'none'})
 opportunities.sort(key=lambda x:({'high':0,'moderate':1,'low':2}[x['severity']],x['key']))
 missing=[f['period'] for f in facts if linked.get(f['period'])!=f['source_import_id']]
 return {'opportunities':opportunities,'excluded_unlinked_periods':missing,
  'conflicting_periods':sorted(conflicts),'source_coverage':{'unconflicted_periods':len(facts),'linked_periods':len(facts)-len(missing)},
  'limitations':['Only validated, reconciled monthly CSV evidence is considered.','Rank is a triage heuristic, not estimated business value or forecast.','Findings are read-only and require human review; no external actions occur.']}

def snapshot(c,uid,wid):
 core.access(c,uid,wid)
 report=core.report(c,uid,wid); state=sync.status(c,uid,wid)
 result=discover(report,state)
 evidence={'facts':report['facts'],'conflicts':report['conflicting_periods'],'links':state['links'],'policy':POLICY_VERSION}
 digest=hashlib.sha256(json.dumps(evidence,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
 return result,digest

def run(c,uid,wid):
 core.access(c,uid,wid,write=True)
 result,digest=snapshot(c,uid,wid);rid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_opportunity_runs VALUES(?,?,?,?,?,?,?)',(rid,wid,uid,int(time.time()),digest,POLICY_VERSION,json.dumps(result,allow_nan=False)))
  core.audit(c,uid,wid,'opportunity_discovery',rid)
 return rid

def history(c,uid,wid):
 core.access(c,uid,wid)
 _,digest=snapshot(c,uid,wid)
 return [{'id':i,'timestamp':ts,'stale':h!=digest,'policy_version':v,'result':json.loads(payload)} for i,ts,h,v,payload in c.execute('SELECT id,created,evidence_hash,policy_version,result_json FROM sv56_opportunity_runs WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 30',(wid,))]

def render(c,uid,csrf,wid):
 core.access(c,uid,wid)
 esc=lambda x:html.escape(str(x),quote=True)
 h=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 5</p><h1>Opportunity Discovery</h1><p>Review evidence-backed changes from synchronized, unconflicted monthly records. Scores are triage labels, not forecasts.</p><form method="post" action="/sovereign-opportunities-v56"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><button>Run opportunity discovery</button></form><p><a href="/sovereign-opportunities-v56.json?w='+quote(wid,safe='')+'">Export discovery history</a></p></section>']
 for item in history(c,uid,wid):
  result=item['result'];h.append('<section class="panel"><h2>Discovery '+esc(item['id'])+'</h2><p>'+('STALE — source evidence changed' if item['stale'] else 'Evidence matches current sources')+'</p><p>'+str(len(result['opportunities']))+' review candidates; '+str(len(result['excluded_unlinked_periods']))+' unlinked periods excluded.</p>')
  for op in result['opportunities']:
   h.append('<article class="sv56-card"><h3>'+esc(op['title'])+' · '+esc(op['severity'])+'</h3><p>'+esc(op['recommended_review'])+'</p><p>Evidence: '+esc(json.dumps(op['evidence'],sort_keys=True))+'</p><p>'+esc(op['uncertainty'])+'</p></article>')
  if not result['opportunities']:h.append('<p>No qualified opportunities. Synchronize validated imports or collect additional months.</p>')
  h.append('</section>')
 if len(h)==1:h.append('<section class="panel"><p>No discovery runs yet.</p></section>')
 return ''.join(h)
