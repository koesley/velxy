"""Sovereign milestone 6: deterministic, evidence-bound hypothetical strategy comparison."""
import hashlib, html, json, math, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_opportunities_v56 as opp

POLICY='strategy-simulator-1'
TEMPLATES={
 'revenue_decline': [('retention_review', 'Retention review', 'conservative', 0.03,0.00,0.01),('customer_outreach','Customer outreach','balanced',0.08,0.03,0.04),('marketing_trial','Marketing trial','aggressive',0.15,0.12,0.10)],
 'expense_increase': [('expense_audit','Expense audit','conservative',0.00,-0.03,0.01),('vendor_review','Vendor review','balanced',0.00,-0.08,0.03),('process_redesign','Process redesign','aggressive',-0.02,-0.15,0.09)],
 'conversion_decline': [('funnel_audit','Funnel audit','conservative',0.02,0.00,0.01),('followup_trial','Follow-up trial','balanced',0.06,0.04,0.04),('acquisition_trial','Acquisition trial','aggressive',0.13,0.12,0.10)]}

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_strategy_runs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,opportunity_key TEXT NOT NULL,evidence_hash TEXT NOT NULL,policy_version TEXT NOT NULL,result_json TEXT NOT NULL CHECK(length(result_json)<=100000))''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_strategy_scope ON sv56_strategy_runs(workspace_id,created)')

def _category(op):
 key=op['category'].lower()
 if 'revenue' in key:return 'revenue_decline'
 if 'expense' in key:return 'expense_increase'
 if 'conversion' in key:return 'conversion_decline'
 return None

def _money(n):
 if not math.isfinite(n):raise ValueError('Non-finite scenario value')
 return round(n,2)

def simulate(revenue,expenses,template):
 """One-month arithmetic scenarios; percentages are illustrative, not estimated effects."""
 if not all(math.isfinite(float(x)) and float(x)>=0 for x in (revenue,expenses)):raise ValueError('Invalid baseline')
 code,label,risk,rev_delta,expense_delta,implementation_rate=template
 revenue=float(revenue);expenses=float(expenses)
 implementation_cost=expenses*implementation_rate
 projected_revenue=_money(revenue*(1+rev_delta))
 projected_expenses=_money(expenses*(1+expense_delta)+implementation_cost)
 baseline_margin=_money(revenue-expenses)
 projected_margin=_money(projected_revenue-projected_expenses)
 # Stress test: revenue outcome 10 percentage points worse, expenses 5 points higher.
 downside_revenue=_money(revenue*max(0,1+rev_delta-.10))
 downside_expenses=_money(expenses*(1+expense_delta+.05)+implementation_cost)
 return {'code':code,'name':label,'risk_label':risk,'assumptions':{'revenue_change_pct':round(rev_delta*100,2),'expense_change_pct':round(expense_delta*100,2),'implementation_cost_pct_of_baseline_expenses':round(implementation_rate*100,2)},'baseline':{'revenue':_money(revenue),'expenses':_money(expenses),'margin':baseline_margin},'hypothetical':{'revenue':projected_revenue,'expenses':projected_expenses,'margin':projected_margin,'margin_delta':_money(projected_margin-baseline_margin),'implementation_cost':_money(implementation_cost)},'downside':{'revenue':downside_revenue,'expenses':downside_expenses,'margin':_money(downside_revenue-downside_expenses)},'downside_assumptions':'Revenue change 10 percentage points below scenario assumption; expense change 5 points above it.','not_a_forecast':True}

def snapshot(c,uid,wid,key):
 core.access(c,uid,wid)
 discovered,digest=opp.snapshot(c,uid,wid)
 match=next((x for x in discovered['opportunities'] if x['key']==key),None)
 if not match:raise ValueError('Opportunity unavailable, stale, or not reconciled; run synchronization and discovery first')
 category=_category(match)
 if category is None:raise ValueError('No supported strategy template for this opportunity')
 facts=core.report(c,uid,wid)['facts']
 period=match['evidence']['current_period'];source=match['evidence']['source_import_ids'][-1]
 baseline=next((f for f in facts if f['period']==period and f['source_import_id']==source),None)
 if baseline is None:raise ValueError('Current evidence missing')
 scenarios=[simulate(baseline['revenue'],baseline['expenses'],t) for t in TEMPLATES[category]]
 # Not a real ROI rank: transparent hypothetical margin score with downside and risk penalty.
 penalties={'conservative':0,'balanced':0.02,'aggressive':0.05}
 for s in scenarios:
  s['illustrative_score']=_money(s['hypothetical']['margin_delta']+0.25*(s['downside']['margin']-s['baseline']['margin'])-baseline['revenue']*penalties[s['risk_label']])
 ranked=sorted(scenarios,key=lambda s:(-s['illustrative_score'],s['code']))
 result={'opportunity':match,'evidence_period':period,'source_import_id':source,'scenarios':scenarios,'illustrative_ranking':[s['code'] for s in ranked],'ranking_formula':'hypothetical margin delta + 0.25 × downside margin delta − baseline revenue × risk penalty (0%, 2%, 5%). Illustrative only.','recommended_for_review':ranked[0]['code'],'approval_required':True,'execution':'none','limitations':['All percentage changes and costs are illustrative assumptions, not predicted effects or verified ROI.','One-month simplified model; no taxes, timing, financing, or attribution.','A higher illustrative score does not establish a superior real-world strategy.','No actions are approved or executed by this module.']}
 evidence_hash=hashlib.sha256(json.dumps({'discovery_hash':digest,'key':key,'baseline':baseline,'policy':POLICY},sort_keys=True,allow_nan=False).encode()).hexdigest()
 return result,evidence_hash

def run(c,uid,wid,key):
 core.access(c,uid,wid,write=True)
 result,digest=snapshot(c,uid,wid,key);rid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_strategy_runs VALUES(?,?,?,?,?,?,?,?)',(rid,wid,uid,int(time.time()),key,digest,POLICY,json.dumps(result,allow_nan=False)))
  core.audit(c,uid,wid,'strategy_simulated',rid)
 return rid

def history(c,uid,wid):
 core.access(c,uid,wid)
 rows=c.execute('SELECT id,created,opportunity_key,evidence_hash,policy_version,result_json FROM sv56_strategy_runs WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 30',(wid,)).fetchall()
 out=[]
 for rid,created,key,digest,policy,payload in rows:
  try:_,now=snapshot(c,uid,wid,key);stale=now!=digest
  except ValueError:stale=True
  out.append({'id':rid,'created':created,'opportunity_key':key,'stale':stale,'policy_version':policy,'result':json.loads(payload)})
 return out

def render(c,uid,csrf,wid):
 core.access(c,uid,wid)
 esc=lambda x:html.escape(str(x),quote=True)
 available,_=opp.snapshot(c,uid,wid)
 h=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 6</p><h1>Strategy Simulation</h1><p>Compare illustrative one-month strategies based on reconciled opportunity evidence. These are NOT predictions or guaranteed returns.</p><form method="post" action="/sovereign-strategies-v56"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><label>Verified opportunity<select name="opportunity_key" required>']
 for item in available['opportunities']:h.append('<option value="'+esc(item['key'])+'">'+esc(item['title'])+' ('+esc(item['key'])+')</option>')
 h.append('</select></label><button '+('' if available['opportunities'] else 'disabled')+'>Simulate strategies</button></form><p><a href="/sovereign-strategies-v56.json?w='+quote(wid,safe='')+'">Export strategy history</a></p></section>')
 for entry in history(c,uid,wid):
  r=entry['result'];h.append('<section class="panel"><h2>Simulation '+esc(entry['id'])+'</h2><p>'+('STALE — evidence changed or is no longer eligible' if entry['stale'] else 'Evidence current')+'</p><p>Source import: '+esc(r['source_import_id'])+' · Period: '+esc(r['evidence_period'])+'</p><div class="scroll"><table><thead><tr><th>Scenario</th><th>Risk</th><th>Revenue</th><th>Expenses</th><th>Margin</th><th>Downside margin</th><th>Illustrative score</th></tr></thead><tbody>')
  for s in r['scenarios']:h.append('<tr><td>'+esc(s['name'])+'</td><td>'+esc(s['risk_label'])+'</td><td>'+esc(s['hypothetical']['revenue'])+'</td><td>'+esc(s['hypothetical']['expenses'])+'</td><td>'+esc(s['hypothetical']['margin'])+'</td><td>'+esc(s['downside']['margin'])+'</td><td>'+esc(s['illustrative_score'])+'</td></tr>')
  h.append('</tbody></table></div><p>Highest illustrative score: '+esc(r['recommended_for_review'])+' — review only; no execution.</p><details><summary>Assumptions and evidence</summary><pre>'+esc(json.dumps({'opportunity':r['opportunity'],'scenarios':[{'code':s['code'],'assumptions':s['assumptions']} for s in r['scenarios']],'ranking_formula':r['ranking_formula'],'limitations':r['limitations']},indent=2))+'</pre></details></section>')
 if not history(c,uid,wid):h.append('<section class="panel"><p>No simulations yet. Import, synchronize, and discover opportunities first.</p></section>')
 return ''.join(h)
