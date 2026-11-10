"""VELXTRIA V12: approval-gated, local-only workflow engine.
No network calls, email sending, payment changes or arbitrary code execution.
"""
import html, json, secrets, time

CSS='''\n.v12{max-width:1100px;margin:auto}.v12 .hero{padding:28px;border:1px solid #6348a2;border-radius:18px;background:linear-gradient(130deg,#211335,#0e1022)}.v12 h1{font-size:2rem}.v12 .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px;margin:20px 0}.v12 .tile{padding:20px;border:1px solid #56426d;border-radius:14px;background:#181627}.v12 input,.v12 textarea,.v12 select{display:block;max-width:100%;width:100%;margin:8px 0 12px;padding:10px;border-radius:8px;background:#0c1020;color:#fff;border:1px solid #67578d}.v12 button{background:#7955c4;color:white;border:0;border-radius:8px;padding:10px 16px;cursor:pointer}.v12 pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0c1020;padding:12px;border-radius:8px}.v12 small{color:#bbb}.v12 .ok{color:#8ae4bd}.v12 .warning{color:#f5d390}'''

def esc(x):return html.escape(str(x),quote=True)
def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS v12_flows(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,title TEXT NOT NULL,trigger_kind TEXT NOT NULL,steps_json TEXT NOT NULL,status TEXT NOT NULL,created INTEGER NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS v12_runs(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,flow_id TEXT NOT NULL,state TEXT NOT NULL,preview_json TEXT NOT NULL,log_json TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS v12_flows_user ON v12_flows(user_id)')
 c.execute('CREATE INDEX IF NOT EXISTS v12_runs_user ON v12_runs(user_id)')

# Intentionally fixed, auditable internal tools. These never write customer records.
TOOLS={'customer_count':'Count CRM customers','proposal_count':'Count Nexus proposals','app_count':'Count Genesis apps','mission_count':'Count missions (if supported)','summary':'Create an internal summary'}

def create(c,user,title,steps):
 title=title.strip()
 if not 3<=len(title)<=100:raise ValueError('Workflow name must be 3–100 characters')
 parsed=[s.strip() for s in steps.split(',') if s.strip()]
 if not 1<=len(parsed)<=8 or any(s not in TOOLS for s in parsed):raise ValueError('Use 1–8 supported tools, comma-separated')
 fid=secrets.token_hex(12)
 c.execute('INSERT INTO v12_flows VALUES (?,?,?,?,?,?,?)',(fid,user,title,'manual',json.dumps(parsed),'active',int(time.time())))
 return fid

def get_flow(c,user,fid):
 row=c.execute('SELECT id,title,steps_json,status FROM v12_flows WHERE user_id=? AND id=?',(user,fid)).fetchone()
 if not row:raise ValueError('Workflow not found')
 return row

def _count(c,table,user):
 # These are read-only, user-scoped queries against existing tables.
 allowed={'customers':('business_customers','crm_customers','v3_customers'),'proposals':('v10_nexus','trinity_nexus'),'apps':('v10_apps','trinity_apps'),'missions':('v52_missions','missions')}
 for t in allowed[table]:
  exists=c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()
  if exists:
   cols=[r[1] for r in c.execute('PRAGMA table_info("'+t+'")')]
   if 'user_id' in cols:return {'value':c.execute('SELECT COUNT(*) FROM "'+t+'" WHERE user_id=?',(user,)).fetchone()[0],'source':t}
 return {'value':None,'source':'No compatible user-scoped table found'}

def inspect(c,user,fid):
 row=get_flow(c,user,fid)
 findings=[]
 for step in json.loads(row[2]):
  if step=='summary':findings.append({'tool':step,'result':'Summary will be assembled from preceding read-only checks.'})
  else:
   kind={'customer_count':'customers','proposal_count':'proposals','app_count':'apps','mission_count':'missions'}[step]
   findings.append({'tool':step,'result':_count(c,kind,user)})
 rid=secrets.token_hex(12);ts=int(time.time())
 c.execute('INSERT INTO v12_runs VALUES (?,?,?,?,?,?,?,?)',(rid,user,fid,'pending_approval',json.dumps(findings),json.dumps([{'at':ts,'event':'Prepared read-only preview; awaiting approval'}]),ts,ts))
 return rid

def approve(c,user,rid):
 row=c.execute('SELECT flow_id,state,preview_json,log_json FROM v12_runs WHERE user_id=? AND id=?',(user,rid)).fetchone()
 if not row:raise ValueError('Run not found')
 if row[1]!='pending_approval':raise ValueError('Only pending runs can be approved')
 get_flow(c,user,row[0])
 ts=int(time.time());log=json.loads(row[3]);log.append({'at':ts,'event':'Approved; read-only results saved. No external actions executed.'})
 c.execute('UPDATE v12_runs SET state=?,log_json=?,updated=? WHERE id=? AND user_id=? AND state=?',('completed',json.dumps(log),ts,rid,user,'pending_approval'))

def reject(c,user,rid):
 row=c.execute('SELECT state,log_json FROM v12_runs WHERE id=? AND user_id=?',(rid,user)).fetchone()
 if not row or row[0]!='pending_approval':raise ValueError('Only pending runs can be rejected')
 log=json.loads(row[1]);log.append({'at':int(time.time()),'event':'Rejected by account owner'})
 c.execute('UPDATE v12_runs SET state=?,log_json=?,updated=? WHERE id=? AND user_id=?',('rejected',json.dumps(log),int(time.time()),rid,user))

def render(c,user,csrf):
 flows=c.execute('SELECT id,title,steps_json FROM v12_flows WHERE user_id=? ORDER BY created DESC LIMIT 40',(user,)).fetchall()
 runs=c.execute('SELECT r.id,f.title,r.state,r.preview_json,r.log_json FROM v12_runs r JOIN v12_flows f ON f.id=r.flow_id AND f.user_id=r.user_id WHERE r.user_id=? ORDER BY r.created DESC LIMIT 30',(user,)).fetchall()
 h=['<div class="v12"><section class="hero"><small>VELXTRIA / V12</small><h1>✦ PROJECT OMNIPOTENCE</h1><p>Build local workflows, inspect real account-scoped data, and approve or reject saved runs. No messages or payments are sent.</p></section><div class="tiles"><section class="tile"><h2>Create workflow</h2><form method="post" action="/omnipotence"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="create"><label>Workflow name<input name="title" required maxlength="100" placeholder="Weekly business pulse"></label><label>Tools (comma-separated)<input name="steps" required value="customer_count,proposal_count,app_count,summary"></label><small>Supported: '+', '.join(TOOLS)+'</small><p><button>Create workflow</button></p></form></section><section class="tile"><h2>Execution policy</h2><p class="ok">✓ Manual approval required</p><p class="ok">✓ Account-scoped read-only tools</p><p class="ok">✓ Persistent audit trail</p><p class="warning">No autonomous external writes, email, or payments</p></section></div><h2>Workflows</h2><div class="tiles">']
 for fid,title,steps in flows:
  h.append('<section class="tile"><h3>'+esc(title)+'</h3><small>'+esc(', '.join(json.loads(steps)))+'</small><form method="post" action="/omnipotence"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="inspect"><input type="hidden" name="flow_id" value="'+esc(fid)+'"><p><button>Prepare approval preview</button></p></form></section>')
 if not flows:h.append('<p>No workflows yet. Create your first above.</p>')
 h.append('</div><h2>Runs & approvals</h2><div class="tiles">')
 for rid,title,state,preview,log in runs:
  h.append('<section class="tile"><h3>'+esc(title)+'</h3><p>Status: <strong>'+esc(state)+'</strong></p><details><summary>Read-only findings</summary><pre>'+esc(json.dumps(json.loads(preview),indent=2))+'</pre></details><details><summary>Audit log</summary><pre>'+esc(json.dumps(json.loads(log),indent=2))+'</pre></details>')
  if state=='pending_approval':
   for action,label in [('approve','Approve & save'),('reject','Reject')]:h.append('<form method="post" action="/omnipotence" style="display:inline-block;margin:8px"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="'+action+'"><input type="hidden" name="run_id" value="'+esc(rid)+'"><button>'+label+'</button></form>')
  h.append('</section>')
 if not runs:h.append('<p>No runs yet.</p>')
 h.append('</div></div>')
 return ''.join(h)
