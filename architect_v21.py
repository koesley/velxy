"""V21 Architect: tenant-scoped, review-first Ollama schema proposals."""
import html,json,os,re,secrets,time,urllib.request
import empire_v19,genesis_prime_v20 as prime

def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS architect_proposals(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, app_id TEXT, prompt TEXT NOT NULL, app_name TEXT NOT NULL, schema_json TEXT NOT NULL, status TEXT NOT NULL, actor INTEGER NOT NULL, created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS architect_tenant ON architect_proposals(workspace_id,created)')

def suggest(prompt,existing=None):
 if not isinstance(prompt,str) or not 12<=len(prompt.strip())<=2000:raise ValueError('Describe the application in 12–2000 characters')
 model=os.getenv('VELXTRIA_OLLAMA_MODEL','llama3.2')
 host=os.getenv('VELXTRIA_OLLAMA_URL','http://127.0.0.1:11434')
 if not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost)(?::\d{2,5})?',host):raise ValueError('Ollama URL must be loopback HTTP')
 instructions='Return ONLY one JSON object: {"name":"App name","fields":[{"name":"Field","type":"text|number|date|checkbox","required":true}]}. 1-20 unique fields, no executable code. Interpret the request as a business data form.'
 if existing:instructions+=' Existing schema: '+json.dumps(existing,ensure_ascii=True)+'. Apply requested changes while preserving fields unless explicitly asked to remove them.'
 payload=json.dumps({'model':model,'stream':False,'format':'json','prompt':instructions+'\nCustomer request: '+prompt,'options':{'temperature':0.1}}).encode()
 req=urllib.request.Request(host+'/api/generate',data=payload,headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=35) as response:raw=response.read(80000)
  data=json.loads(json.loads(raw)['response'])
 except (OSError,ValueError,KeyError,TypeError) as exc:raise ValueError('Local Ollama generation failed. Start Ollama and pull the configured model. '+str(exc)[:150])
 if not isinstance(data,dict):raise ValueError('AI response must be a JSON object')
 name=data.get('name','');fields=prime.schema_check(data.get('fields'))
 if not isinstance(name,str) or not 2<=len(name.strip())<=100:raise ValueError('AI returned an invalid app name')
 return name.strip(),fields

def propose(c,uid,wid,prompt,aid=''):
 prime.permission(c,uid,wid,True)
 old=None
 if aid:
  row=prime.app(c,uid,wid,aid,True)
  if row[3]!='draft':raise ValueError('Published applications cannot be modified by Architect')
  old=json.loads(row[2])
 name,fields=suggest(prompt,old)
 pid=secrets.token_hex(12)
 c.execute('INSERT INTO architect_proposals VALUES(?,?,?,?,?,?,?,?,?)',(pid,wid,aid or None,prompt,name,json.dumps(fields,sort_keys=True),'pending',uid,int(time.time())))
 return pid

def approve(c,uid,wid,pid):
 if empire_v19.role(c,uid,wid)!='owner':raise ValueError('Only workspace owners can approve AI proposals')
 p=c.execute('SELECT app_id,app_name,schema_json,status FROM architect_proposals WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
 if not p or p[3]!='pending':raise ValueError('Pending proposal not found')
 fields=prime.schema_check(json.loads(p[2]));schema=json.dumps(fields,sort_keys=True)
 if p[0]:
  row=prime.app(c,uid,wid,p[0],True)
  if row[3]!='draft':raise ValueError('Application is no longer a draft')
  version=row[4]+1
  c.execute('UPDATE prime_apps SET schema_json=?,version=? WHERE id=? AND workspace_id=? AND status=?',(schema,version,p[0],wid,'draft'))
  c.execute('INSERT INTO prime_versions VALUES(?,?,?,?,?,?)',(p[0],version,schema,'draft',uid,int(time.time())))
  aid=p[0]
 else:
  aid=secrets.token_hex(12)
  c.execute('INSERT INTO prime_apps VALUES(?,?,?,?,?,?,?,?)',(aid,wid,p[1],schema,'draft',1,uid,int(time.time())))
  c.execute('INSERT INTO prime_versions VALUES(?,?,?,?,?,?)',(aid,1,schema,'draft',uid,int(time.time())))
 c.execute('UPDATE architect_proposals SET status=? WHERE id=? AND workspace_id=?',('approved',pid,wid))
 return aid

def reject(c,uid,wid,pid):
 if empire_v19.role(c,uid,wid)!='owner':raise ValueError('Only workspace owners can reject proposals')
 if c.execute('UPDATE architect_proposals SET status=? WHERE id=? AND workspace_id=? AND status=?',('rejected',pid,wid,'pending')).rowcount!=1:raise ValueError('Pending proposal not found')

def render(c,uid,csrf,wid='',message=''):
 e=lambda x:html.escape(str(x),quote=True)
 ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not wid and ws:wid=ws[0][0]
 h=['<section class="panel"><h1>✦ ARCHITECT V21</h1><p>Local Ollama proposes app designs. Nothing changes until a workspace owner approves. Only draft apps can be revised.</p><p><a href="/genesis-prime">Open Genesis Prime</a></p>']
 if message:h.append('<p><strong>'+e(message)+'</strong></p>')
 h.append('<p>Workspaces: '+''.join('<a style="margin-right:12px" href="/architect?w='+e(w)+'">'+e(n)+'</a>' for w,n in ws)+'</p></section>')
 if not wid:return ''.join(h)
 role=prime.permission(c,uid,wid)
 if role in ('owner','editor'):
  apps=c.execute("SELECT id,name FROM prime_apps WHERE workspace_id=? AND status='draft' ORDER BY created DESC",(wid,)).fetchall()
  h.append('<section class="panel"><h2>Describe your application</h2><form method="post" action="/architect"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="propose"><label>New application or existing draft<select name="app"><option value="">Create new draft</option>'+''.join('<option value="'+e(i)+'">Edit: '+e(n)+'</option>' for i,n in apps)+'</select></label><label>What should it do?<textarea name="prompt" maxlength="2000" rows="5" required placeholder="Build a customer booking system with customer name, date, and service"></textarea></label><button>Generate proposal with Ollama</button></form></section>')
 proposals=c.execute('SELECT id,app_name,schema_json,status,prompt FROM architect_proposals WHERE workspace_id=? ORDER BY created DESC LIMIT 25',(wid,)).fetchall()
 h.append('<section class="panel"><h2>Proposals</h2>')
 for pid,name,schema,status,prompt in proposals:
  h.append('<div style="border-top:1px solid #655777;padding:12px"><h3>'+e(name)+' — '+e(status)+'</h3><p>'+e(prompt)+'</p><ul>'+''.join('<li>'+e(f['name'])+' ('+e(f['type'])+')'+(' required' if f['required'] else '')+'</li>' for f in json.loads(schema))+'</ul>')
  if status=='pending' and role=='owner':
   for action in ('approve','reject'):
    h.append('<form class="inline" method="post" action="/architect"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="proposal" value="'+e(pid)+'"><input type="hidden" name="action" value="'+action+'"><button>'+action.title()+'</button></form>')
  h.append('</div>')
 h.append('</section>')
 return ''.join(h)
