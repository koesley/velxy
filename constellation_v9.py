"""V9: coordinated, evidence-backed mission dossier; local, read-only, account-scoped."""
import html,json,secrets,time
import sovereign_v8

def e(x):return html.escape(str(x),quote=True)
def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS vx9_dossiers(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,mission_id TEXT NOT NULL,created_at INTEGER NOT NULL,report_json TEXT NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS vx9_scope ON vx9_dossiers(user_id,mission_id,created_at)')

def build(c,uid,mid):
 row=c.execute('SELECT title FROM vx52_missions WHERE id=? AND user_id=?',(mid,uid)).fetchone()
 if not row:raise ValueError('Mission is not accessible.')
 evidence={}
 for tool in sovereign_v8.TOOLS:
  rid=sovereign_v8.run(c,uid,mid,tool)
  result=c.execute('SELECT status,output_json FROM vx8_tool_runs WHERE id=? AND user_id=?',(rid,uid)).fetchone()
  if result[0]!='completed':raise ValueError('A diagnostic failed; no dossier was saved.')
  evidence[tool]={'run_id':rid,'data':json.loads(result[1])}
 pipeline=evidence['pipeline_audit']['data']; mission=evidence['mission_audit']['data']; operations=evidence['operations_audit']['data']
 stages=pipeline.get('stages',{}); counts=mission.get('action_status_counts',{})
 pending=sum(int(counts.get(k,0)) for k in ('pending','approved'))
 total=pipeline.get('total_contacts',0)
 observations=mission.get('outcome_records')
 findings=[]
 if total==0:findings.append({'severity':'attention','title':'No CRM contacts recorded','evidence':'CRM audit returned zero contacts.','next':'Add verified customer records before attempting outreach.'})
 else:findings.append({'severity':'info','title':f'{total} CRM contacts in account','evidence':'Stage distribution: '+', '.join(f'{k}: {v}' for k,v in stages.items()),'next':'Review contacts for missing next steps; the audit does not establish last-contact dates.'})
 if pending:findings.append({'severity':'attention','title':f'{pending} proposals still pending or approved','evidence':'Mission action status counts from database.','next':'Review proposals individually before any execution.'})
 if int(counts.get('executed',0))>0 and not observations:findings.append({'severity':'attention','title':'Executed internal work lacks outcome observations','evidence':'Executed action(s) exist, no outcome records found.','next':'Record what actually happened; do not assume contact or revenue.'})
 elif int(counts.get('executed',0))>0:findings.append({'severity':'info','title':'Internal execution has recorded observations','evidence':f'{observations} outcome records; content and truth not independently verified.','next':'Confirm external results with reliable records before claiming success.'})
 findings.append({'severity':'info','title':'Operations snapshot available','evidence':'Internal task counts: '+json.dumps(operations.get('task_counts',{}),ensure_ascii=False),'next':'Compare tasks to mission objectives and assign an owner.'})
 report={'mission':row[0],'generated_at':int(time.time()),'method':'Deterministic multi-tool synthesis; no model inference','confidence':'Limited to recorded database facts','findings':findings,'evidence':evidence,'restrictions':['No external contact or financial actions','No customer response inferred from saved drafts','No background agent execution']}
 did=secrets.token_hex(16)
 c.execute('INSERT INTO vx9_dossiers VALUES(?,?,?,?,?)',(did,uid,mid,int(time.time()),json.dumps(report,ensure_ascii=False)))
 return did

def render(c,uid,csrf,mid=''):
 missions=c.execute('SELECT id,title FROM vx52_missions WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
 if mid not in [m[0] for m in missions]:mid=missions[0][0] if missions else ''
 out=['<section class="hero vx9hero"><p class="eyebrow">VELXTRIA V9 / PROJECT CONSTELLATION</p><h1>ONE MISSION. <em>THREE AGENTS.</em> ONE CLEAR PICTURE.</h1><p>Run coordinated CRM, mission, and operations diagnostics in one click. Receive a persistent, traceable mission dossier grounded in your own records—not invented business outcomes.</p></section>','<section class="panel"><h2>Mission intelligence scope</h2><form method="get" action="/constellation"><label>Select mission<select name="id">']
 for ident,title in missions:out.append('<option value="'+e(ident)+'"'+(' selected' if ident==mid else '')+'>'+e(title)+'</option>')
 out.append('</select></label><button>Load mission</button></form></section>')
 if not mid:return ''.join(out)+'<section class="panel">Create a mission first.</section>'
 out.append('<section class="panel"><p class="eyebrow">01 / COORDINATED INTELLIGENCE</p><h2>Mission Dossier Generator</h2><div class="vx9steps"><div>◈ CRM SIGNALS<br><small>Contacts & pipeline</small></div><div>◈ MISSION SIGNALS<br><small>Actions & evidence</small></div><div>◈ OPERATIONS SIGNALS<br><small>Tasks & entries</small></div></div><p>Each run executes all three account-scoped read-only tools, then creates a structured findings report. Nothing is sent to customers or changed in your CRM.</p><form method="post" action="/constellation"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="mission_id" value="'+e(mid)+'"><button>✦ Generate mission dossier</button></form></section>')
 rows=c.execute('SELECT id,created_at,report_json FROM vx9_dossiers WHERE user_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 15',(uid,mid)).fetchall()
 out.append('<section class="panel"><p class="eyebrow">02 / MISSION DOSSIERS</p><h2>Evidence-backed intelligence archive</h2>')
 if not rows:out.append('<p>No dossiers yet. Generate your first briefing above.</p>')
 for i,(did,ts,raw) in enumerate(rows):
  try:report=json.loads(raw)
  except ValueError:continue
  out.append('<details class="vx9dossier"'+(' open' if i==0 else '')+'><summary>✦ '+e(report.get('mission','Mission'))+' · '+e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(ts)))+'</summary><p><strong>Method:</strong> '+e(report.get('method',''))+' · <strong>Evidence:</strong> '+e(report.get('confidence',''))+'</p>')
  for f in report.get('findings',[]):out.append('<article class="vx9finding"><span class="vx9tag">'+e(f.get('severity','info'))+'</span><h3>'+e(f.get('title',''))+'</h3><p><strong>Evidence:</strong> '+e(f.get('evidence',''))+'</p><p><strong>Next action:</strong> '+e(f.get('next',''))+'</p></article>')
  out.append('<details><summary>Inspect raw diagnostic evidence</summary><pre class="vx9raw">'+e(json.dumps(report.get('evidence',{}),indent=2,ensure_ascii=False))+'</pre></details></details>')
 out.append('</section><section class="panel"><h2>Honest execution boundary</h2><p>This version coordinates three deterministic, read-only diagnostic agents. It does not use an LLM to choose tools, autonomously execute changes, or verify customer outcomes outside your database. Results are snapshots, not live monitoring.</p></section>')
 return ''.join(out)
CSS='''\n.vx9hero{background:linear-gradient(120deg,#171024,#291640);border:1px solid #8e64c2}.vx9hero em{color:#dbb9ff}.vx9steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}.vx9steps>div,.vx9finding,.vx9dossier{border:1px solid #62447e;background:#1a1529;padding:16px;border-radius:14px}.vx9steps small{color:#baa5d4}.vx9dossier{margin:12px 0}.vx9finding{margin:12px 0}.vx9tag{color:#dcbaff;font-size:12px;text-transform:uppercase;letter-spacing:.1em}.vx9raw{white-space:pre-wrap;overflow-wrap:anywhere;color:#d5c3eb}\n'''
