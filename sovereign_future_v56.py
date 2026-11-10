"""V56.9: deterministic, evidence-bound monthly what-if projection. No forecasts or actions."""
import hashlib, html, json, math, secrets, time
from urllib.parse import quote
import sovereign_v56 as core

POLICY='future-simulator-1'

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_future_runs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,evidence_hash TEXT NOT NULL,parameters_json TEXT NOT NULL,result_json TEXT NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_future_scope ON sv56_future_runs(workspace_id,created)')

def validated(horizon, revenue_pct, expense_pct, shock_pct, cash):
 try:
  months=int(horizon); values=[float(x) for x in (revenue_pct,expense_pct,shock_pct,cash)]
 except (TypeError,ValueError,OverflowError) as exc:raise ValueError('Invalid scenario parameters') from exc
 if str(months)!=str(horizon) or months<1 or months>36:raise ValueError('Horizon must be 1–36 whole months')
 if any(not math.isfinite(x) for x in values):raise ValueError('Non-finite parameter')
 r,e,s,b=values
 if not (-50<=r<=50 and -50<=e<=50 and 0<=s<=90 and 0<=b<=1e12):raise ValueError('Parameters outside safe bounds')
 return {'months':months,'revenue_change_pct':r,'expense_change_pct':e,'first_month_revenue_shock_pct':s,'opening_cash':b}

def evidence(c,uid,wid):
 core.access(c,uid,wid)
 report=core.report(c,uid,wid)
 raw_latest=c.execute('SELECT MAX(period) FROM sv56_metrics WHERE workspace_id=?',(wid,)).fetchone()[0]
 if raw_latest in report.get('conflicting_periods',[]):raise ValueError('Latest period has conflicting imports')
 facts=report['facts']
 if not facts:raise ValueError('Import verified metrics first')
 latest=max(facts,key=lambda f:f['period'])
 if any(f['period']==latest['period'] for f in facts if f is not latest):raise ValueError('Latest period has conflicting imports')
 # A conflicting earlier period is not silently used as a historical baseline.
 if latest['period'] in report.get('conflicting_periods',[]):raise ValueError('Latest period has conflicting imports')
 base={k:latest[k] for k in ('period','revenue','expenses','leads','customers','source_import_id')}
 digest=hashlib.sha256(json.dumps({'baseline':base,'policy':POLICY},sort_keys=True).encode()).hexdigest()
 return base,digest

def calculate(base,params):
 r=float(base['revenue']);e=float(base['expenses']);cash=params['opening_cash'];rows=[]
 for month in range(1,params['months']+1):
  r=r*(1+params['revenue_change_pct']/100)
  e=e*(1+params['expense_change_pct']/100)
  shock=params['first_month_revenue_shock_pct']/100 if month==1 else 0
  income=r*(1-shock)
  net=round(income-e,2);cash=round(cash+net,2)
  if any(not math.isfinite(v) or abs(v)>1e15 for v in (r,e,income,net,cash)):raise ValueError('Scenario exceeds numeric safety limits')
  rows.append({'month':month,'revenue':round(income,2),'expenses':round(e,2),'net_cash_flow':round(net,2),'ending_cash':round(cash,2),'cash_shortfall':cash<0})
 return {'baseline':base,'parameters':params,'months':rows,'ending_cash':rows[-1]['ending_cash'],'first_shortfall_month':next((x['month'] for x in rows if x['cash_shortfall']),None),'not_a_forecast':True,'limitations':['User-entered hypothetical changes, not predicted growth.','Cash flow approximated as revenue minus expenses; excludes receivables, taxes, debt, financing and timing.','No inferred causal effects or automated actions.']}

def preview(c,uid,wid,horizon,revenue_pct,expense_pct,shock_pct,cash):
 params=validated(horizon,revenue_pct,expense_pct,shock_pct,cash)
 base,digest=evidence(c,uid,wid)
 return calculate(base,params),digest

def run(c,uid,wid,horizon,revenue_pct,expense_pct,shock_pct,cash):
 core.access(c,uid,wid,write=True)
 result,digest=preview(c,uid,wid,horizon,revenue_pct,expense_pct,shock_pct,cash)
 rid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_future_runs VALUES(?,?,?,?,?,?,?)',(rid,wid,uid,int(time.time()),digest,json.dumps(result['parameters'],allow_nan=False),json.dumps(result,allow_nan=False)))
  core.audit(c,uid,wid,'future_scenario_saved',rid)
 return rid

def history(c,uid,wid):
 core.access(c,uid,wid)
 try:_,digest=evidence(c,uid,wid)
 except ValueError:digest=None
 rows=c.execute('SELECT id,created,evidence_hash,result_json FROM sv56_future_runs WHERE workspace_id=? ORDER BY created DESC,rowid DESC LIMIT 30',(wid,)).fetchall()
 return [{'id':rid,'created':created,'stale':digest!=source,'result':json.loads(data)} for rid,created,source,data in rows]

def render(c,uid,csrf,wid):
 core.access(c,uid,wid)
 esc=lambda x:html.escape(str(x),quote=True)
 out=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 9</p><h1>Business Future Simulator</h1><p>Hypothetical monthly cash-flow scenarios, not predictions or investment advice. Revenue and expense changes compound monthly.</p><form method="post" action="/sovereign-future-v56"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'">']
 for name,label,default in [('months','Months (1–36)','6'),('revenue_pct','Monthly revenue change %','0'),('expense_pct','Monthly expense change %','0'),('shock_pct','First-month revenue shock %','0'),('opening_cash','Opening cash','0')]:out.append('<label>'+label+'<input name="'+name+'" value="'+default+'" required></label>')
 out.append('<button>Save hypothetical simulation</button></form><p><a href="/sovereign-future-v56.json?w='+quote(wid,safe='')+'">Export scenario history</a></p></section>')
 for entry in history(c,uid,wid):
  result=entry['result'];out.append('<section class="panel"><h2>Scenario '+esc(entry['id'])+'</h2><p>'+('STALE — baseline evidence changed' if entry['stale'] else 'Baseline evidence current')+'</p><p>Source '+esc(result['baseline']['source_import_id'])+' · '+esc(result['baseline']['period'])+' · Ending hypothetical cash '+esc(result['ending_cash'])+'</p><div class="scroll"><table><thead><tr><th>Month</th><th>Revenue</th><th>Expenses</th><th>Net cash flow</th><th>Ending cash</th></tr></thead><tbody>')
  for row in result['months']:out.append('<tr><td>'+esc(row['month'])+'</td><td>'+esc(row['revenue'])+'</td><td>'+esc(row['expenses'])+'</td><td>'+esc(row['net_cash_flow'])+'</td><td>'+esc(row['ending_cash'])+'</td></tr>')
  out.append('</tbody></table></div><details><summary>Assumptions and limitations</summary><pre>'+esc(json.dumps({'parameters':result['parameters'],'limitations':result['limitations']},indent=2))+'</pre></details></section>')
 if not history(c,uid,wid):out.append('<section class="panel">No saved scenarios. Import metrics first.</section>')
 return ''.join(out)
