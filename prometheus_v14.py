# Prometheus V14 local declarative app designer
import json,re,html,time,secrets,urllib.request,urllib.parse
import singularity_x_v13 as v13
CSS='''\n.v14{max-width:1050px;margin:auto}.v14 .panel{background:#1a1429;border:1px solid #635080;border-radius:16px;padding:20px;margin:16px 0}.v14 input,.v14 textarea,.v14 select{width:100%;box-sizing:border-box;background:#111022;color:white;border:1px solid #756190;border-radius:7px;padding:10px;margin:7px 0}.v14 button{background:#7652b6;color:white;padding:10px 16px;border:0;border-radius:8px;cursor:pointer}.v14 pre{white-space:pre-wrap;overflow-wrap:anywhere}.v14 a{color:#d7baff}'''
def e(x):return html.escape(str(x),quote=True)
def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS v14_versions(id TEXT PRIMARY KEY,app_id TEXT NOT NULL,user_id INTEGER NOT NULL,schema_json TEXT NOT NULL,note TEXT NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS v14_versions_owner ON v14_versions(user_id,app_id,created)')
 c.execute('CREATE TABLE IF NOT EXISTS v14_reviews(id TEXT PRIMARY KEY,app_id TEXT NOT NULL,user_id INTEGER NOT NULL,report_json TEXT NOT NULL,created INTEGER NOT NULL)')
def normalize(raw):
 if not isinstance(raw,dict):raise ValueError('Design must be a JSON object')
 fields=raw.get('fields')
 if not isinstance(fields,list) or not 2<=len(fields)<=12:raise ValueError('Design must have 2–12 fields')
 clean=[];used=set();allowed={'text','number','email','date','time','choice'}
 for f in fields:
  if not isinstance(f,dict):raise ValueError('Invalid field')
  key=str(f.get('key','')).lower().strip();label=str(f.get('label','')).strip();kind=str(f.get('type','text')).lower()
  if not re.fullmatch('[a-z][a-z0-9_]{0,29}',key) or key in used:raise ValueError('Field keys must be unique lowercase identifiers')
  if not 1<=len(label)<=50 or kind not in allowed:raise ValueError('Invalid label or field type')
  choices=f.get('choices',[]) if kind=='choice' else []
  if kind=='choice' and (not isinstance(choices,list) or not 2<=len(choices)<=12 or any(not isinstance(x,str) or not 1<=len(x)<=50 for x in choices) or len(set(choices))!=len(choices)):raise ValueError('Choice fields need 2–12 unique options')
  used.add(key);clean.append({'key':key,'label':label,'type':kind,'required':bool(f.get('required',False)),'choices':choices})
 if not any(x['required'] for x in clean):raise ValueError('At least one field must be required')
 return {'kind':str(raw.get('kind','Custom App'))[:70],'fields':clean,'rules':['required_fields','type_validation'],'version':14}
def propose(goal,model='llama3.2'):
 if not 12<=len(goal.strip())<=2000:raise ValueError('Describe the app in 12–2000 characters')
 if not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,70}',model):raise ValueError('Invalid local model name')
 prompt=('Design a small business app schema. Return ONLY one JSON object with kind and fields. Each field has key (lowercase snake_case), label, type (text,number,email,date,time,choice), required boolean, choices array for choice fields. 2 to 12 fields, at least one required, no code or instructions. Business request: '+goal)
 req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=json.dumps({'model':model,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0}}).encode(),headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=25) as resp:
   if resp.status!=200 or int(resp.headers.get('Content-Length','0') or '0')>250000:raise ValueError('Ollama response too large')
   obj=json.loads(resp.read(250001))
  result=json.loads(obj['response']);return normalize(result)
 except (OSError,TimeoutError,KeyError,TypeError,json.JSONDecodeError) as ex:raise ValueError('Local Ollama is unavailable or returned invalid JSON. Start Ollama and pull the model, then retry.') from ex
def design(c,u,aid,mode,model='llama3.2'):
 row=v13.get(c,u,aid)
 if row[4]!='draft':raise ValueError('Only drafts may be redesigned. Published apps and records are preserved.')
 schema=propose(row[2],model) if mode=='ollama' else normalize(v13.infer(row[2]))
 c.execute('INSERT INTO v14_versions VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),aid,u,row[3],'Before redesign',int(time.time())))
 c.execute('UPDATE v13_apps SET schema_json=?,tests_json=?,updated=? WHERE id=? AND user_id=?',(json.dumps(schema),'[]',int(time.time()),aid,u))
 v13.event(c,u,aid,'v14_redesign',mode+'; simulation tests invalidated')
def review(c,u,aid):
 row=v13.get(c,u,aid);schema=json.loads(row[3]);fields=schema['fields'];keys=[f['key'] for f in fields]
 checks=[('Architect: valid declarative schema',bool(normalize(schema))),('Developer: unique supported fields',len(keys)==len(set(keys))),('Tester: required fields exist',any(f['required'] for f in fields)),('Security: no executable code',set(schema)=={'kind','fields','rules','version'}),('Business analyst: reasonable field count',2<=len(fields)<=12)]
 report={'checks':[{'name':k,'pass':v} for k,v in checks],'notice':'Static review only. Does not prove app security or real-world suitability.'}
 c.execute('INSERT INTO v14_reviews VALUES(?,?,?,?,?)',(secrets.token_hex(12),aid,u,json.dumps(report),int(time.time())))
 v13.event(c,u,aid,'v14_review','Five deterministic specialist checks');return report
def restore(c,u,aid,vid):
 row=v13.get(c,u,aid)
 if row[4]!='draft':raise ValueError('Only drafts may restore versions')
 found=c.execute('SELECT schema_json FROM v14_versions WHERE id=? AND user_id=? AND app_id=?',(vid,u,aid)).fetchone()
 if not found:raise ValueError('Version not found')
 normalize(json.loads(found[0]))
 c.execute('INSERT INTO v14_versions VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),aid,u,row[3],'Before restore',int(time.time())))
 c.execute('UPDATE v13_apps SET schema_json=?,tests_json=?,updated=? WHERE id=? AND user_id=?',(found[0],'[]',int(time.time()),aid,u));v13.event(c,u,aid,'v14_restore','Restored previous schema; tests invalidated')
def manifest(c,u,aid):
 row=v13.get(c,u,aid)
 return json.dumps({'format':'velxtria.prometheus.manifest.v1','app_id':row[0],'title':row[1],'state':row[4],'schema':json.loads(row[3]),'deployment':'local-only; review required','requires':['Python','SQLite'],'warning':'Manifest is not a deployable container or source code'},indent=2).encode()
def render(c,u,csrf,aid):
 apps=c.execute('SELECT id,title FROM v13_apps WHERE user_id=? ORDER BY created DESC LIMIT 100',(u,)).fetchall()
 if not aid and apps:aid=apps[0][0]
 h=['<div class="v14"><div class="panel"><h1>✦ PROMETHEUS V14</h1><p>AI-assisted declarative app design · five static reviews · version snapshots · deployment manifests. No arbitrary code execution.</p><p><a href="/singularity-x">Open V13 app builder</a></p></div><div class="panel"><form method="get" action="/prometheus"><label>Choose an existing application<select name="app">']
 h += ['<option value="'+e(i)+'" '+('selected' if i==aid else '')+'>'+e(t)+'</option>' for i,t in apps]
 h.append('</select></label><button>Open app</button></form></div>')
 if aid:
  row=v13.get(c,u,aid);draft=row[4]=='draft';h.append('<div class="panel"><h2>'+e(row[1])+'</h2><p>'+e(row[2])+'</p><p>State: '+e(row[4])+'</p><pre>'+e(json.dumps(json.loads(row[3]),indent=2))+'</pre>')
  if draft:
   h.append('<form method="post" action="/prometheus"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="app_id" value="'+e(aid)+'"><input type="hidden" name="action" value="design"><label>Design mode<select name="mode"><option value="ollama">Local Ollama (AI proposal)</option><option value="rules">Deterministic fallback</option></select></label><label>Ollama model<input name="model" value="llama3.2" maxlength="70"></label><button>Propose new design (saves previous version)</button></form>')
  h.append('<form method="post" action="/prometheus"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="app_id" value="'+e(aid)+'"><input type="hidden" name="action" value="review"><button>Run five specialist reviews</button></form><p><a href="/prometheus/manifest?app='+e(aid)+'">Download deployment preparation manifest</a></p></div>')
  reviews=c.execute('SELECT report_json FROM v14_reviews WHERE user_id=? AND app_id=? ORDER BY created DESC LIMIT 1',(u,aid)).fetchone()
  if reviews:
   report=json.loads(reviews[0]);h.append('<div class="panel"><h3>Latest specialist review</h3><ul>'+''.join('<li>'+('✓ ' if x['pass'] else '✗ ')+e(x['name'])+'</li>' for x in report['checks'])+'</ul><small>'+e(report['notice'])+'</small></div>')
  versions=c.execute('SELECT id,note,created FROM v14_versions WHERE user_id=? AND app_id=? ORDER BY created DESC LIMIT 30',(u,aid)).fetchall()
  if versions:
   h.append('<div class="panel"><h3>Version history</h3>')
   for vid,note,ts in versions:
    h.append('<form method="post" action="/prometheus"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="app_id" value="'+e(aid)+'"><input type="hidden" name="version_id" value="'+e(vid)+'"><input type="hidden" name="action" value="restore"><span>'+e(note)+' · '+e(time.strftime('%Y-%m-%d %H:%M',time.gmtime(ts)))+' UTC </span>'+('<button>Restore draft</button>' if draft else '<small>Published: restore disabled</small>')+'</form>')
   h.append('</div>')
 h.append('</div>');return ''.join(h)
