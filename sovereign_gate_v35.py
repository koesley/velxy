"""V35: operator evidence binding, strict release gate, and auditable review decisions.

Evidence hashes detect accidental edits, not malicious operator tampering. No deployment.
"""
import html, json, time, hashlib
import empire_v19, sentinel_v34

MAX_AGE=24*3600

def esc(x):return html.escape(str(x),quote=True)

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sovereign_evidence_links (release_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL, sha256 TEXT NOT NULL, linked_by INTEGER NOT NULL, linked_at INTEGER NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS sovereign_gate_events (id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id TEXT NOT NULL,release_id TEXT NOT NULL,actor_id INTEGER NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL,created INTEGER NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS sovereign_gate_events_lookup ON sovereign_gate_events(workspace_id,release_id,id)')

def audit(c,wid,rid,uid,event,detail):
 c.execute('INSERT INTO sovereign_gate_events(workspace_id,release_id,actor_id,event,detail,created) VALUES(?,?,?,?,?,?)',(wid,rid,uid,event,detail,int(time.time())))

def evidence(data_root,run_id):
 if len(run_id)!=32 or any(ch not in '0123456789abcdef' for ch in run_id):raise ValueError('Invalid run identifier')
 for item in sentinel_v34.load_reports(data_root,limit=100):
  if item.get('run_id')==run_id:
   if not item.get('verified') or item.get('status')!='passed' or item.get('output_truncated'):
    raise ValueError('Test report must be complete, passing, and checksum-verified')
   if item.get('finished',0)>int(time.time())+60 or int(time.time())-item.get('finished',0)>MAX_AGE:
    raise ValueError('Test report is expired or has an invalid timestamp')
   if not item.get('tests'):raise ValueError('Empty test suite')
   return item
 raise ValueError('Verified test report not found')

def attach(c,uid,wid,rid,run_id,data_root):
 if empire_v19.role(c,uid,wid) not in ('owner','editor'):raise ValueError('Insufficient workspace permission')
 row=c.execute('SELECT status FROM evolution_releases WHERE id=? AND workspace_id=?',(rid,wid)).fetchone()
 if not row or row[0] in ('approved','rejected'):raise ValueError('Release cannot be changed')
 report=evidence(data_root,run_id)
 c.execute('INSERT INTO sovereign_evidence_links(release_id,workspace_id,run_id,sha256,linked_by,linked_at) VALUES(?,?,?,?,?,?) ON CONFLICT(release_id) DO UPDATE SET run_id=excluded.run_id,sha256=excluded.sha256,linked_by=excluded.linked_by,linked_at=excluded.linked_at',(rid,wid,run_id,report['sha256'],uid,int(time.time())))
 audit(c,wid,rid,uid,'evidence_attached','Run '+run_id+' hash '+report['sha256'])

def verify_gate(c,wid,rid,data_root):
 row=c.execute('SELECT run_id,sha256 FROM sovereign_evidence_links WHERE workspace_id=? AND release_id=?',(wid,rid)).fetchone()
 if not row:raise ValueError('V35 gate: attach passing automated Sentinel evidence before approval')
 report=evidence(data_root,row[0])
 if report['sha256']!=row[1]:raise ValueError('V35 gate: test evidence changed since attachment')
 return report

def render(c,uid,csrf,wid,data_root,message=''):
 ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<section class="panel"><h1>Sovereign Gate V35</h1><p>Create a business workspace first.</p></section>'
 wid=wid or ws[0][0]
 role=empire_v19.role(c,uid,wid)
 if not role:raise ValueError('Workspace unavailable')
 opts=''.join('<option value="'+esc(i)+'"'+(' selected' if i==wid else '')+'>'+esc(n)+'</option>' for i,n in ws)
 reports=sentinel_v34.load_reports(data_root,limit=100)
 valid=[]
 for r in reports:
  try:valid.append(evidence(data_root,r['run_id']))
  except ValueError:pass
 releases=c.execute('SELECT id,title,version_label,status FROM evolution_releases WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()
 out=['<section class="hero"><p class="eyebrow">VELXTRIA V35 · SOVEREIGN GATE</p><h1>Proof required. Approval controlled.</h1><p>Bind verified, recent machine-generated regression evidence to release candidates before owners approve them. No automatic deployment.</p></section>', '<section class="panel"><form method="get" action="/sovereign-gate"><label>Workspace<select name="w">'+opts+'</select></label><button>Switch</button></form></section>']
 if message:out.append('<section class="panel"><p>'+esc(message)+'</p></section>')
 out.append('<section class="panel"><h2>Evidence status</h2><p>'+str(len(valid))+' passing, checksum-verified reports from the past 24 hours. Run <code>python sentinel_v34.py run</code> in your local terminal to generate evidence.</p></section>')
 for rid,title,version,status in releases:
  link=c.execute('SELECT run_id,sha256 FROM sovereign_evidence_links WHERE release_id=? AND workspace_id=?',(rid,wid)).fetchone()
  try:
   verify_gate(c,wid,rid,data_root); gate='PASS: verified recent evidence'
  except ValueError as e:gate='BLOCKED: '+str(e)
  out.append('<section class="panel"><h3>'+esc(title)+'</h3><p>'+esc(version)+' · '+esc(status)+' · '+esc(gate)+'</p>')
  if role in ('owner','editor') and status not in ('approved','rejected') and valid:
   options=''.join('<option value="'+esc(r['run_id'])+'">'+esc(r['run_id'][:12])+' · '+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(r['finished'])))+'</option>' for r in valid)
   out.append('<form method="post" action="/sovereign-gate"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="release" value="'+esc(rid)+'"><label>Passing automated run<select name="run">'+options+'</select></label><button>Attach test evidence</button></form>')
  events=c.execute('SELECT event,detail,created FROM sovereign_gate_events WHERE workspace_id=? AND release_id=? ORDER BY id DESC LIMIT 8',(wid,rid)).fetchall()
  for event,detail,created in events:out.append('<p><small>'+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(created)))+' · '+esc(event)+' · '+esc(detail)+'</small></p>')
  out.append('</section>')
 if not releases:out.append('<section class="panel"><p>No release candidates yet. Create one in Evolutionary Core.</p></section>')
 out.append('<section class="panel"><h2>Safety boundaries</h2><p>Checksum verification detects changes but is not a digital signature or independent security attestation. The operator controls the local test environment. Passing tests and owner approval do not certify production readiness or deploy software.</p><p><a href="/evolutionary-core?w='+esc(wid)+'">Review release candidates</a> · <a href="/sentinel?w='+esc(wid)+'">Sentinel diagnostics</a></p></section>')
 return ''.join(out)
