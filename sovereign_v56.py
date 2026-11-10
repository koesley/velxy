"""V56 Sovereign foundation: tenant-scoped, local CSV facts -> graph -> opportunities -> approved tasks -> outcomes.
No LLM, network connector, background worker, financial attribution or automatic external action.
"""
import csv, io, hashlib, html, json, math, secrets, time
from urllib.parse import urlencode
import empire_v19

FIELDS=('period','revenue','expenses','leads','customers')
MAX_ROWS=5000

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_imports(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, filename TEXT NOT NULL, sha256 TEXT NOT NULL, imported_by INTEGER NOT NULL, created INTEGER NOT NULL, row_count INTEGER NOT NULL, UNIQUE(workspace_id,sha256))''')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_metrics(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, import_id TEXT NOT NULL, period TEXT NOT NULL, revenue REAL NOT NULL CHECK(revenue>=0), expenses REAL NOT NULL CHECK(expenses>=0), leads INTEGER NOT NULL CHECK(leads>=0), customers INTEGER NOT NULL CHECK(customers>=0), FOREIGN KEY(import_id) REFERENCES sv56_imports(id))''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_metrics_scope ON sv56_metrics(workspace_id,period)')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_actions(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, opportunity_key TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('proposed','approved','completed','rejected')), created_by INTEGER NOT NULL, approved_by INTEGER, created INTEGER NOT NULL, completed INTEGER, outcome TEXT NOT NULL DEFAULT '')''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_actions_scope ON sv56_actions(workspace_id,status)')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_audit(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, actor INTEGER NOT NULL, event TEXT NOT NULL, object_id TEXT NOT NULL, created INTEGER NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_audit_scope ON sv56_audit(workspace_id,created)')

def access(c,uid,wid,write=False,owner=False):
 r=empire_v19.role(c,uid,wid)
 if not r or (write and r not in ('owner','editor')) or (owner and r!='owner'):
  raise ValueError('Workspace not found or insufficient permission')
 return r

def audit(c,uid,wid,event,obj):
 c.execute('INSERT INTO sv56_audit VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wid,uid,event,obj,int(time.time())))

def import_csv(c,uid,wid,filename,data):
 access(c,uid,wid,write=True)
 if not isinstance(data,bytes) or not data or len(data)>1024*1024:raise ValueError('CSV must be between 1 byte and 1 MB')
 if not filename.lower().endswith('.csv') or len(filename)>120:raise ValueError('Provide a CSV filename')
 if b'\x00' in data:raise ValueError('Invalid CSV content')
 try:
  raw=data.decode('utf-8-sig'); reader=csv.DictReader(io.StringIO(raw,newline=''),strict=True)
  if reader.fieldnames!=list(FIELDS):raise ValueError('Expected headers: '+', '.join(FIELDS))
  rows=[];seen=set()
  for row in reader:
   if len(rows)>=MAX_ROWS:raise ValueError('CSV exceeds 5000 rows')
   if None in row or any(row.get(k) is None for k in FIELDS):raise ValueError('Malformed row')
   period=row['period'].strip()
   if len(period)!=7 or period[4]!='-' or not period[:4].isdigit() or not period[5:].isdigit() or not 1<=int(period[5:])<=12:raise ValueError('Use YYYY-MM periods')
   if period in seen:raise ValueError('Duplicate period')
   seen.add(period)
   nums=[]
   for k in ('revenue','expenses'):
    v=float(row[k]);
    if not math.isfinite(v) or v<0 or v>1e12:raise ValueError('Invalid financial value')
    nums.append(v)
   counts=[]
   for k in ('leads','customers'):
    v=int(row[k]);
    if str(v)!=row[k].strip() or v<0 or v>1000000000:raise ValueError('Invalid count')
    counts.append(v)
   if counts[1]>counts[0]:raise ValueError('Customers cannot exceed leads in this simplified funnel')
   rows.append((period,*nums,*counts))
 except (UnicodeError,csv.Error,OverflowError,ValueError) as e:raise ValueError('Invalid CSV encoding or format') from e
 if not rows:raise ValueError('No data rows')
 digest=hashlib.sha256(data).hexdigest()
 if c.execute('SELECT 1 FROM sv56_imports WHERE workspace_id=? AND sha256=?',(wid,digest)).fetchone():raise ValueError('This file was already imported')
 iid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_imports VALUES(?,?,?,?,?,?,?)',(iid,wid,filename,digest,uid,int(time.time()),len(rows)))
  for row in rows:c.execute('INSERT INTO sv56_metrics VALUES(?,?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,iid,*row))
  audit(c,uid,wid,'csv_imported',iid)
 return iid

def report(c,uid,wid):
 access(c,uid,wid)
 rows=c.execute('SELECT m.period,m.revenue,m.expenses,m.leads,m.customers,m.import_id FROM sv56_metrics m WHERE m.workspace_id=? ORDER BY m.period,m.rowid',(wid,)).fetchall()
 # Imported datasets may overlap; show conflicts rather than silently aggregate or overwrite.
 periods={};conflicts=[]
 for row in rows:
  if row[0] in periods:conflicts.append(row[0])
  else:periods[row[0]]=row
 clean=[v for k,v in sorted(periods.items()) if k not in conflicts]
 facts=[{'period':p,'revenue':r,'expenses':e,'leads':l,'customers':cu,'source_import_id':src,'net_cash_proxy':round(r-e,2)} for p,r,e,l,cu,src in clean]
 opportunities=[]
 if len(facts)>=2:
  a,b=facts[-2:]
  checks=[('revenue_decline',b['revenue']<a['revenue'],'Revenue declined',a['revenue'],b['revenue'],'Investigate changes in sales and pricing.'),('expense_increase',b['expenses']>a['expenses'],'Expenses increased',a['expenses'],b['expenses'],'Review expense categories and suppliers.'),('conversion_decline',a['leads']>0 and b['leads']>0 and b['customers']/b['leads']<a['customers']/a['leads'],'Lead conversion declined',a['customers']/a['leads'] if a['leads'] else None,b['customers']/b['leads'] if b['leads'] else None,'Audit lead qualification and follow-up timing.')]
  for code,hit,title,old,new,action in checks:
   if hit:opportunities.append({'key':code+':'+b['period'],'title':title,'evidence':{'previous_period':a['period'],'current_period':b['period'],'previous':old,'current':new,'source_import_ids':[a['source_import_id'],b['source_import_id']]},'recommended_action':action,'confidence':'observed_change_only','potential_value':None,'requires_approval':True,'limitations':['Two-period comparison cannot establish causation or financial benefit.']})
 actions=[{'id':i,'opportunity_key':k,'title':t,'status':s,'outcome':o} for i,k,t,s,o in c.execute('SELECT id,opportunity_key,title,status,outcome FROM sv56_actions WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()]
 audits=[{'event':e,'object_id':o,'timestamp':ts} for e,o,ts in c.execute('SELECT event,object_id,created FROM sv56_audit WHERE workspace_id=? ORDER BY created DESC LIMIT 50',(wid,)).fetchall()]
 return {'workspace_id':wid,'facts':facts,'conflicting_periods':sorted(set(conflicts)),'opportunities':opportunities,'actions':actions,'audit':audits,'graph':{'nodes':[{'id':'period:'+f['period'],'type':'period','source_import_id':f['source_import_id']} for f in facts]+[{'id':'import:'+f['source_import_id'],'type':'source'} for f in facts],'edges':[{'from':'import:'+f['source_import_id'],'to':'period:'+f['period'],'relation':'supplies'} for f in facts]},'limitations':['CSV imports are local and manually supplied; not a live connector.','Cash proxy is revenue minus expenses, not accounting profit or cash runway.','Conflicting periods are excluded from comparisons until reconciled.','No causal inference, autonomous external actions, or AI model is enabled.']}

def simulate(c,uid,wid,revenue_change=0,expense_change=0):
 r=report(c,uid,wid)
 if not r['facts']:return {'baseline':None,'scenario':None,'limitations':['Import valid data first.']}
 try:rc=float(revenue_change);ec=float(expense_change)
 except (ValueError,TypeError):raise ValueError('Invalid scenario assumption')
 if not all(math.isfinite(x) and -100<=x<=300 for x in (rc,ec)):raise ValueError('Assumptions must be between -100% and +300%')
 f=r['facts'][-1];sr=round(f['revenue']*(1+rc/100),2);se=round(f['expenses']*(1+ec/100),2)
 return {'baseline':{'period':f['period'],'revenue':f['revenue'],'expenses':f['expenses'],'net_cash_proxy':f['net_cash_proxy'],'source_import_id':f['source_import_id']},'scenario':{'revenue':sr,'expenses':se,'net_cash_proxy':round(sr-se,2)},'assumptions':{'revenue_change_pct':rc,'expense_change_pct':ec},'formulas':['scenario_revenue = baseline_revenue * (1 + revenue_change_pct / 100)','scenario_expenses = baseline_expenses * (1 + expense_change_pct / 100)','net_cash_proxy = scenario_revenue - scenario_expenses'],'limitations':['Deterministic what-if only, not a forecast or expected outcome.']}

def propose(c,uid,wid,key):
 access(c,uid,wid,write=True)
 op=next((o for o in report(c,uid,wid)['opportunities'] if o['key']==key),None)
 if not op:raise ValueError('Opportunity not found')
 aid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_actions(id,workspace_id,opportunity_key,title,status,created_by,created) VALUES(?,?,?,?,?,?,?)',(aid,wid,key,op['recommended_action'],'proposed',uid,int(time.time())))
  audit(c,uid,wid,'action_proposed',aid)
 return aid

def transition(c,uid,wid,aid,action,outcome=''):
 access(c,uid,wid,owner=True)
 if action not in ('approve','reject','complete'):raise ValueError('Invalid transition')
 row=c.execute('SELECT status FROM sv56_actions WHERE workspace_id=? AND id=?',(wid,aid)).fetchone()
 if not row:raise ValueError('Action not found')
 old=row[0];new={'approve':'approved','reject':'rejected','complete':'completed'}[action]
 if (old,new) not in (('proposed','approved'),('proposed','rejected'),('approved','completed')):raise ValueError('Invalid action state transition')
 if action=='complete' and not 5<=len(outcome.strip())<=2000:raise ValueError('Document observed outcome (5–2000 characters)')
 with c:
  changed=c.execute('UPDATE sv56_actions SET status=?,approved_by=?,completed=?,outcome=? WHERE workspace_id=? AND id=? AND status=?',(new,uid if action=='approve' else None,int(time.time()) if action=='complete' else None,outcome.strip() if action=='complete' else '',wid,aid,old)).rowcount
  if changed!=1:raise ValueError('Concurrent action update')
  audit(c,uid,wid,'action_'+new,aid)
 return new

def render(c,uid,csrf,wid='',rc=0,ec=0):
 e=lambda x:html.escape(str(x),quote=True)
 workspaces=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not wid and workspaces:wid=workspaces[0][0]
 if not wid:return '<section class="panel"><h1>Sovereign V56</h1><p>Create a workspace in Empire before importing data.</p><a href="/empire">Create workspace</a></section>'
 r=report(c,uid,wid);s=simulate(c,uid,wid,rc,ec);role=access(c,uid,wid)
 h=['<section class="panel sv56"><p class="eyebrow">VELXTRIA V56 · PROJECT SOVEREIGN · FOUNDATION</p><h1>Business Intelligence Operations</h1><p>Real imported metrics, traceable findings, owner-approved internal actions and recorded outcomes. Local SQLite only.</p><p><a href="/sovereign-v56.json?'+e(urlencode({'w':wid}))+'">Export JSON evidence</a></p><form method="get" action="/sovereign-v56"><label>Workspace<select name="w">']
 for w,name in workspaces:h.append('<option value="'+e(w)+'"'+(' selected' if w==wid else '')+'>'+e(name)+'</option>')
 h.append('</select></label><button>Open</button></form></section>')
 if role in ('owner','editor'):
  h.append('<section class="panel"><h2>1 · Import authorized monthly metrics</h2><p>CSV columns: period,revenue,expenses,leads,customers. YYYY-MM periods; no customer-identifying data.</p><form method="post" action="/sovereign-v56" enctype="multipart/form-data"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="import"><input type="file" name="file" accept=".csv" required><button>Validate and import CSV</button></form></section>')
 h.append('<section class="panel"><h2>2 · Digital twin and opportunity radar</h2><p>Validated periods: '+e(len(r['facts']))+' · Conflicts: '+e(', '.join(r['conflicting_periods']) or 'none')+'</p>')
 for f in r['facts'][-12:]:h.append('<p>'+e(f['period'])+' · Revenue '+e(f['revenue'])+' · Expenses '+e(f['expenses'])+' · Leads '+e(f['leads'])+' · Customers '+e(f['customers'])+' · Source '+e(f['source_import_id'])+'</p>')
 for op in r['opportunities']:
  h.append('<article class="sv56-card"><h3>'+e(op['title'])+'</h3><p>'+e(op['recommended_action'])+'</p><p>Observed: '+e(op['evidence']['previous'])+' → '+e(op['evidence']['current'])+' · Sources: '+e(', '.join(op['evidence']['source_import_ids']))+'</p>')
  if role in ('owner','editor'):h.append('<form method="post" action="/sovereign-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="propose"><input type="hidden" name="key" value="'+e(op['key'])+'"><button>Propose internal review task</button></form>')
  h.append('</article>')
 if not r['opportunities']:h.append('<p>No detectable two-period opportunities yet. This is not proof that no opportunities exist.</p>')
 h.append('</section><section class="panel"><h2>3 · Futures laboratory</h2><form method="get" action="/sovereign-v56"><input type="hidden" name="w" value="'+e(wid)+'"><label>Revenue change %<input name="rc" type="number" step="0.1" min="-100" max="300" value="'+e(rc)+'"></label><label>Expense change %<input name="ec" type="number" step="0.1" min="-100" max="300" value="'+e(ec)+'"></label><button>Recalculate</button></form>')
 if s['scenario']:h.append('<p>Hypothetical revenue: '+e(s['scenario']['revenue'])+' · Expenses: '+e(s['scenario']['expenses'])+' · Net proxy: '+e(s['scenario']['net_cash_proxy'])+'</p>')
 h.append('<p>Formula: revenue × (1 + change / 100), expenses × (1 + change / 100). This is not a forecast.</p></section><section class="panel"><h2>4 · Supervised internal actions</h2>')
 for a in r['actions']:
  h.append('<article class="sv56-card"><strong>'+e(a['title'])+'</strong><p>Status: '+e(a['status'])+' · ID '+e(a['id'])+'</p>')
  if a['outcome']:h.append('<p>Recorded outcome: '+e(a['outcome'])+'</p>')
  if role=='owner' and a['status'] in ('proposed','approved'):
   actions=('approve','reject') if a['status']=='proposed' else ('complete',)
   for act in actions:
    h.append('<form method="post" action="/sovereign-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="id" value="'+e(a['id'])+'"><input type="hidden" name="action" value="'+act+'">')
    if act=='complete':h.append('<label>Actual observed outcome<textarea name="outcome" minlength="5" maxlength="2000" required></textarea></label>')
    h.append('<button>'+e(act.title())+'</button></form>')
  h.append('</article>')
 h.append('<p>Approval creates an internal review record only. No external operation is performed.</p></section><section class="panel"><h2>5 · Audit trail</h2>')
 for a in r['audit'][:20]:h.append('<p>'+e(a['event'])+' · '+e(a['object_id'])+' · '+e(a['timestamp'])+'</p>')
 h.append('</section><section class="panel"><h2>Known limits</h2><ul>')
 for limit in r['limitations']:h.append('<li>'+e(limit)+'</li>')
 return ''.join(h)+'</ul></section>'

CSS='''.sv56{background:linear-gradient(130deg,#1a142e,#0d2731);border:1px solid #7658a8}.sv56-card{background:#1b2030;border:1px solid #4e476a;border-radius:12px;padding:14px;margin:12px 0;overflow-wrap:anywhere}'''
