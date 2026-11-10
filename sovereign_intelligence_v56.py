# Sovereign milestone 2: bounded, deterministic evidence council with durable evaluations.
# No LLM, external tool calls, or independent action execution.
import hashlib, html, json, secrets, time
import sovereign_v56 as base

AGENTS={
 'finance': 'Financial Intelligence Analyst',
 'growth': 'Revenue Growth Analyst',
 'operations': 'Operations Architect',
 'risk': 'Risk and Compliance Reviewer',
 'synthesizer': 'Executive Intelligence Synthesizer',
}

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_council_runs(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,
 created INTEGER NOT NULL,evidence_hash TEXT NOT NULL,objective TEXT NOT NULL,
 result_json TEXT NOT NULL CHECK(length(result_json)<=100000))''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_council_scope ON sv56_council_runs(workspace_id,created)')

def evidence_digest(report):
 payload={'facts':report['facts'],'conflicts':report['conflicting_periods']}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def evaluate(report,objective):
 if objective not in ('overview','revenue','costs','operations'):
  raise ValueError('Unsupported council objective')
 facts=report['facts']; findings=[]; selected=[]
 def add(agent,kind,headline,evidence,uncertainty,next_step):
  if agent not in selected:selected.append(agent)
  findings.append({'agent':agent,'kind':kind,'headline':headline,'evidence':evidence,
   'uncertainty':uncertainty,'next_step':next_step})
 if objective in ('overview','revenue'):
  selected.append('growth')
  if len(facts)>=2:
   a,b=facts[-2:]; delta=round(b['revenue']-a['revenue'],2)
   add('growth','observed','Revenue changed by '+str(delta),{'periods':[a['period'],b['period']],
    'source_import_ids':[a['source_import_id'],b['source_import_id']],
    'previous_revenue':a['revenue'],'current_revenue':b['revenue']},
    'Two observations cannot establish trend, cause, or expected future revenue.',
    'Review sales and pricing records before deciding on a growth intervention.')
  else:add('growth','missing_evidence','Insufficient revenue history',{'available_periods':len(facts)},
   'At least two unconflicted periods are needed for comparison.','Import another validated month.')
 if objective in ('overview','costs'):
  selected.append('finance')
  if len(facts)>=2:
   a,b=facts[-2:]
   add('finance','observed','Expenses changed by '+str(round(b['expenses']-a['expenses'],2)),
    {'periods':[a['period'],b['period']],'source_import_ids':[a['source_import_id'],b['source_import_id']],
     'previous_expenses':a['expenses'],'current_expenses':b['expenses']},
    'Expense totals do not reveal expense categories, cash balances, or accounting profit.',
    'Review underlying expense categories and invoices.')
  else:add('finance','missing_evidence','Insufficient expense history',{'available_periods':len(facts)},
   'At least two unconflicted periods are needed.','Import another validated month.')
 if objective in ('overview','operations'):
  selected.append('operations')
  if len(facts)>=2 and all(f['leads']>0 for f in facts[-2:]):
   a,b=facts[-2:]; previous=a['customers']/a['leads']; current=b['customers']/b['leads']
   add('operations','observed','Lead conversion changed by '+str(round((current-previous)*100,2))+' percentage points',
    {'periods':[a['period'],b['period']],'source_import_ids':[a['source_import_id'],b['source_import_id']],
     'previous_conversion':previous,'current_conversion':current},
    'This simplified funnel assumes customers originate from the same period leads; no causal inference.',
    'Validate lead definitions and investigate response times.')
  else:add('operations','missing_evidence','Insufficient conversion evidence',{'available_periods':len(facts)},
   'Requires two periods with nonzero leads.','Import valid lead and customer counts.')
 selected.append('risk')
 if report['conflicting_periods']:
  add('risk','data_quality','Conflicting periods require reconciliation',
   {'conflicting_periods':report['conflicting_periods']},
   'Conflicting periods are excluded, which may hide relevant changes.',
   'Resolve discrepancies in the original source files before relying on comparisons.')
 else:add('risk','guardrail','Source coverage reviewed',{'valid_periods':len(facts)},
   'No conflicts detected does not prove that source data is complete or accurate.',
   'Verify imports against authoritative business records.')
 selected.append('synthesizer')
 opportunities=[{'key':o['key'],'title':o['title'],'source_import_ids':o['evidence']['source_import_ids'],
  'recommended_action':o['recommended_action'],'uncertainty':o['limitations'][0]} for o in report['opportunities']]
 return {'objective':objective,'agents_used':selected,'findings':findings,'opportunities':opportunities,
  'recommendation':'Review source records and propose a supervised internal task only after validating evidence.' if opportunities else 'Collect more verified data before proposing a strategy.',
  'execution_policy':'Observation only; this council cannot execute tools, approve actions, or send messages.',
  'limitations':['Deterministic bounded rules, not a generative AI model or independent agents.',
   'Results are based only on tenant-scoped manually imported monthly CSV records.',
   'Financial changes are observations, not attributed value or causal estimates.']}

def run(c,uid,wid,objective):
 base.access(c,uid,wid,write=True)
 r=base.report(c,uid,wid); result=evaluate(r,objective); digest=evidence_digest(r)
 run_id=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_council_runs VALUES(?,?,?,?,?,?,?)',
   (run_id,wid,uid,int(time.time()),digest,objective,json.dumps(result,allow_nan=False)))
  base.audit(c,uid,wid,'council_evaluated',run_id)
 return run_id

def history(c,uid,wid):
 base.access(c,uid,wid)
 current=evidence_digest(base.report(c,uid,wid))
 rows=c.execute('SELECT id,created,evidence_hash,objective,result_json FROM sv56_council_runs WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 30',(wid,)).fetchall()
 return [{'id':i,'timestamp':ts,'objective':obj,'stale':digest!=current,'result':json.loads(payload)} for i,ts,digest,obj,payload in rows]

def render(c,uid,csrf,wid):
 base.access(c,uid,wid)
 e=lambda s:html.escape(str(s),quote=True)
 h=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 2</p><h1>Evidence Intelligence Council</h1><p>Bounded deterministic analysis, tenant-scoped source references, and versioned evaluations. No AI model or external execution.</p>',
 '<form method="post" action="/sovereign-council-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><label>Objective<select name="objective">']
 for value,label in [('overview','Company overview'),('revenue','Revenue analysis'),('costs','Cost analysis'),('operations','Conversion and operations')]:h.append('<option value="'+value+'">'+label+'</option>')
 h.append('</select></label><button>Run bounded analysis</button></form><p><a href="/sovereign-council-v56.json?w='+e(wid)+'">Export council history JSON</a></p></section>')
 for item in history(c,uid,wid):
  h.append('<section class="panel"><h2>'+e(item['objective'])+' · '+e(item['id'])+'</h2><p>Evidence status: '+('STALE — underlying data changed' if item['stale'] else 'Matches current imports')+'</p>')
  for f in item['result']['findings']:
   h.append('<article class="sv56-card"><h3>'+e(AGENTS[f['agent']])+'</h3><p>'+e(f['headline'])+'</p><p><strong>Evidence:</strong> '+e(json.dumps(f['evidence'],sort_keys=True))+'</p><p><strong>Uncertainty:</strong> '+e(f['uncertainty'])+'</p><p><strong>Next step:</strong> '+e(f['next_step'])+'</p></article>')
  h.append('<p>'+e(item['result']['recommendation'])+'</p></section>')
 if len(h)==2:h.append('<section class="panel"><p>No council evaluations yet. Import monthly metrics, then run an analysis.</p></section>')
 return ''.join(h)
