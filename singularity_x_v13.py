"""V13: deterministic, sandbox-free declarative mini-app builder.
No arbitrary generated code, remote services, or automatic deployment.
"""
import html,json,re,secrets,time,hashlib

CSS='''\n.v13{max-width:1160px;margin:auto}.v13 .hero{padding:30px;border:1px solid #7454b4;border-radius:18px;background:linear-gradient(120deg,#251338,#101225)}.v13 h1{font-size:2.1rem}.v13 .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin:20px 0}.v13 .tile{padding:20px;background:#191529;border:1px solid #54456d;border-radius:14px}.v13 input,.v13 textarea,.v13 select{display:block;width:100%;box-sizing:border-box;margin:8px 0 14px;padding:10px;background:#0e1021;color:white;border:1px solid #6b568a;border-radius:8px}.v13 button,.v13 .btn{display:inline-block;background:#7850bf;color:white;border:0;padding:10px 16px;border-radius:8px;cursor:pointer;text-decoration:none}.v13 pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#101022;padding:12px;border-radius:8px}.v13 small{color:#bfb4d5}.v13 .good{color:#93eac3}.v13 .warn{color:#f2d48c}.v13 table{width:100%;border-collapse:collapse}.v13 td,.v13 th{border-bottom:1px solid #524464;padding:8px;text-align:left;overflow-wrap:anywhere}.v13 .pill{padding:4px 9px;border-radius:15px;background:#493266}'''
def esc(x):return html.escape(str(x),quote=True)
def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS v13_apps(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,title TEXT NOT NULL,goal TEXT NOT NULL,schema_json TEXT NOT NULL,state TEXT NOT NULL,tests_json TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS v13_records(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,app_id TEXT NOT NULL,values_json TEXT NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS v13_events(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,app_id TEXT NOT NULL,event TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS v13_apps_user ON v13_apps(user_id)')
 c.execute('CREATE INDEX IF NOT EXISTS v13_records_owner ON v13_records(user_id,app_id)')
def event(c,u,a,e,d=''):
 c.execute('INSERT INTO v13_events VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),u,a,e,d,int(time.time())))
def infer(goal):
 g=goal.lower()
 if any(s in g for s in ('appointment','booking','barber','salon','schedule')):
  kind='Appointments'; fields=[('customer','Customer','text',True),('service','Service','text',True),('date','Date','date',True),('time','Time','time',True),('status','Status','choice',True)]
 elif any(s in g for s in ('inventory','stock','warehouse','product')):
  kind='Inventory';fields=[('item','Item','text',True),('sku','SKU','text',True),('quantity','Quantity','number',True),('unit_price','Unit Price','number',False)]
 elif any(s in g for s in ('lead','customer','crm','client')):
  kind='Customer Tracker';fields=[('name','Name','text',True),('email','Email','email',False),('status','Status','choice',True),('notes','Notes','text',False)]
 elif any(s in g for s in ('invoice','expense','finance','payment')):
  kind='Invoice Ledger';fields=[('reference','Reference','text',True),('customer','Customer','text',True),('amount','Amount','number',True),('status','Status','choice',True)]
 else:
  kind='Project Tracker';fields=[('name','Name','text',True),('owner','Owner','text',False),('status','Status','choice',True),('notes','Notes','text',False)]
 return {'kind':kind,'fields':[{'key':k,'label':label,'type':t,'required':r,'choices':['New','In progress','Completed'] if t=='choice' else []} for k,label,t,r in fields],'rules':['required_fields','type_validation'],'version':1}
def create(c,u,title,goal):
 title=title.strip();goal=goal.strip()
 if not 3<=len(title)<=90 or not 12<=len(goal)<=2000:raise ValueError('Enter a title (3–90 characters) and description (12–2000 characters).')
 aid=secrets.token_hex(12);ts=int(time.time());schema=infer(goal)
 c.execute('INSERT INTO v13_apps VALUES(?,?,?,?,?,?,?,?,?)',(aid,u,title,goal,json.dumps(schema),'draft','[]',ts,ts));event(c,u,aid,'draft_created','Rule-based schema generated; no AI code executed')
 return aid
def get(c,u,aid):
 row=c.execute('SELECT id,title,goal,schema_json,state,tests_json FROM v13_apps WHERE id=? AND user_id=?',(aid,u)).fetchone()
 if not row:raise ValueError('Application not found')
 return row
def validate(schema,data):
 out={};issues=[]
 for f in schema['fields']:
  k=f['key'];v=str(data.get(k,'')).strip()
  if f['required'] and not v:issues.append(f['label']+' is required')
  if len(v)>500:issues.append(f['label']+' is too long')
  if v and f['type']=='number':
   try:float(v)
   except ValueError:issues.append(f['label']+' must be numeric')
  if v and f['type']=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v):issues.append(f['label']+' must be an email')
  if v and f['type']=='date' and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):issues.append(f['label']+' must be YYYY-MM-DD')
  if v and f['type']=='time' and not re.fullmatch(r'\d{2}:\d{2}',v):issues.append(f['label']+' must be HH:MM')
  if v and f['type']=='choice' and v not in f['choices']:issues.append(f['label']+' must be an allowed choice')
  out[k]=v
 return out,issues
def simulate(c,u,aid):
 row=get(c,u,aid)
 if row[4]!='draft':raise ValueError('Only draft apps can be tested')
 schema=json.loads(row[3]);sample={}
 for f in schema['fields']:
  sample[f['key']]={'number':'12.50','email':'sample@example.com','date':'2026-12-01','time':'09:30','choice':f['choices'][0] if f['choices'] else 'New'}.get(f['type'],'Sample')
 _,positive=validate(schema,sample)
 missing=dict(sample);missing[next(f['key'] for f in schema['fields'] if f['required'])]=''
 _,negative=validate(schema,missing)
 malformed=dict(sample)
 numeric=next((f for f in schema['fields'] if f['type']=='number'),None)
 if numeric:malformed[numeric['key']]='not-a-number'
 _,bad=validate(schema,malformed)
 tests=[{'name':'Valid sample accepted','pass':not positive},{'name':'Required field rejected','pass':bool(negative)},{'name':'Invalid number rejected','pass':bool(bad) if numeric else True},{'name':'Schema size and unique fields','pass':len(schema['fields'])<=12 and len({f['key'] for f in schema['fields']})==len(schema['fields'])}]
 c.execute('UPDATE v13_apps SET tests_json=?,updated=? WHERE id=? AND user_id=?',(json.dumps(tests),int(time.time()),aid,u));event(c,u,aid,'simulation_completed',json.dumps(tests))
 return tests
def publish(c,u,aid):
 row=get(c,u,aid)
 if row[4]!='draft':raise ValueError('Only drafts can be published')
 tests=json.loads(row[5]);
 if not tests or not all(t['pass'] for t in tests):raise ValueError('All simulation tests must pass before publishing')
 c.execute('UPDATE v13_apps SET state=?,updated=? WHERE id=? AND user_id=?',('published',int(time.time()),aid,u));event(c,u,aid,'published','Owner approved local publishing')
def add_record(c,u,aid,data):
 row=get(c,u,aid)
 if row[4]!='published':raise ValueError('Publish and approve the app before adding records')
 vals,errors=validate(json.loads(row[3]),data)
 if errors:raise ValueError('; '.join(errors))
 rid=secrets.token_hex(12);c.execute('INSERT INTO v13_records VALUES(?,?,?,?,?)',(rid,u,aid,json.dumps(vals),int(time.time())));event(c,u,aid,'record_added',rid)
 return rid
def delete_record(c,u,aid,rid):
 get(c,u,aid)
 cur=c.execute('DELETE FROM v13_records WHERE id=? AND app_id=? AND user_id=?',(rid,aid,u))
 if not cur.rowcount:raise ValueError('Record not found')
 event(c,u,aid,'record_deleted',rid)
def export(c,u,aid):
 row=get(c,u,aid)
 records=c.execute('SELECT values_json FROM v13_records WHERE app_id=? AND user_id=? ORDER BY created',(aid,u)).fetchall()
 return json.dumps({'format':'VELXTRIA-V13','title':row[1],'goal':row[2],'schema':json.loads(row[3]),'state':row[4],'records':[json.loads(r[0]) for r in records]},indent=2).encode()
def render(c,u,csrf,aid=''):
 apps=c.execute('SELECT id,title,state FROM v13_apps WHERE user_id=? ORDER BY created DESC LIMIT 50',(u,)).fetchall()
 h=['<div class="v13"><section class="hero"><small>VELXTRIA / V13 / SINGULARITY X</small><h1>✦ Software Creation Laboratory</h1><p>Describe a business app, generate a safe structured design, run simulated validation tests, approve local publication, and save records. No arbitrary generated code or external deployment.</p></section><div class="tiles"><section class="tile"><h2>Generate application</h2><form method="post" action="/singularity-x"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="create"><label>App name<input name="title" required maxlength="90" placeholder="Barbershop Appointment Manager"></label><label>Describe what it should do<textarea name="goal" required minlength="12" maxlength="2000" rows="5" placeholder="Manage barbershop appointments, customers, dates and booking statuses"></textarea></label><button>Create draft</button></form><small>Local rule-based templates: appointments, inventory, customers, invoices, projects.</small></section><section class="tile"><h2>Engineering safeguards</h2><p class="good">✓ Tenant-scoped application data</p><p class="good">✓ Automated positive and negative tests</p><p class="good">✓ Human publication approval</p><p class="good">✓ JSON export and event audit trail</p><p class="warn">No generated Python execution, live integrations, or deployment</p></section></div><h2>Your applications</h2><div class="tiles">']
 for appid,title,state in apps:h.append('<section class="tile"><h3>'+esc(title)+'</h3><p><span class="pill">'+esc(state)+'</span></p><a class="btn" href="/singularity-x?app='+esc(appid)+'">Open studio</a></section>')
 if not apps:h.append('<p>No applications yet.</p>')
 h.append('</div>')
 if aid:
  row=get(c,u,aid);schema=json.loads(row[3]);tests=json.loads(row[5]);h.append('<section class="tile"><h2>'+esc(row[1])+'</h2><p>'+esc(row[2])+'</p><p>Template: '+esc(schema['kind'])+' · '+esc(row[4])+'</p><details><summary>View generated schema</summary><pre>'+esc(json.dumps(schema,indent=2))+'</pre></details>')
  if row[4]=='draft':
   h.append('<form method="post" action="/singularity-x"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="app_id" value="'+esc(aid)+'"><input type="hidden" name="action" value="simulate"><button>Run simulation tests</button></form>')
   if tests:
    h.append('<h3>Test results</h3><ul>')
    for t in tests:h.append('<li>'+('✓ ' if t['pass'] else '✗ ')+esc(t['name'])+'</li>')
    h.append('</ul>')
    if all(t['pass'] for t in tests):h.append('<form method="post" action="/singularity-x"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="app_id" value="'+esc(aid)+'"><input type="hidden" name="action" value="publish"><button>Approve & publish locally</button></form>')
  else:
   h.append('<h3>New record</h3><form method="post" action="/singularity-x"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="app_id" value="'+esc(aid)+'"><input type="hidden" name="action" value="add_record">')
   for f in schema['fields']:
    h.append('<label>'+esc(f['label']))
    if f['type']=='choice':h.append('<select name="'+esc(f['key'])+'"><option value="">Choose...</option>'+''.join('<option value="'+esc(x)+'">'+esc(x)+'</option>' for x in f['choices'])+'</select>')
    else:h.append('<input name="'+esc(f['key'])+'" type="'+esc(f['type'] if f['type'] in ('number','email','date','time') else 'text')+'" maxlength="500" '+('required' if f['required'] else '')+'>')
    h.append('</label>')
   h.append('<button>Save record</button></form><p><a class="btn" href="/singularity-x/export?app='+esc(aid)+'">Export app + data (JSON)</a></p>')
   records=c.execute('SELECT id,values_json FROM v13_records WHERE user_id=? AND app_id=? ORDER BY created DESC LIMIT 100',(u,aid)).fetchall();h.append('<h3>Records</h3><div style="overflow:auto"><table><tr>'+''.join('<th>'+esc(f['label'])+'</th>' for f in schema['fields'])+'<th>Action</th></tr>')
   for rid,values in records:
    vals=json.loads(values);h.append('<tr>'+''.join('<td>'+esc(vals.get(f['key'],''))+'</td>' for f in schema['fields'])+'<td><form method="post" action="/singularity-x"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="app_id" value="'+esc(aid)+'"><input type="hidden" name="record_id" value="'+esc(rid)+'"><input type="hidden" name="action" value="delete_record"><button>Delete</button></form></td></tr>')
   h.append('</table></div>')
  events=c.execute('SELECT event,details,created FROM v13_events WHERE user_id=? AND app_id=? ORDER BY created DESC LIMIT 20',(u,aid)).fetchall();h.append('<details><summary>Audit trail</summary><ul>'+''.join('<li>'+esc(time.strftime('%Y-%m-%d %H:%M',time.gmtime(ts)))+' — '+esc(e)+' — '+esc(d[:120])+'</li>' for e,d,ts in events)+'</ul></details></section>')
 h.append('</div>');return ''.join(h)
