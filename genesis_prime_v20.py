"""Genesis Prime V20.1: tenant-scoped, schema-driven business apps. Local SQLite pilot."""
import html,json,secrets,time
import empire_v19
TEMPLATES={
 'inventory':[{'name':'Item','type':'text','required':True},{'name':'Quantity','type':'number','required':True}],
 'appointments':[{'name':'Customer','type':'text','required':True},{'name':'Date','type':'date','required':True}],
 'crm':[{'name':'Contact','type':'text','required':True},{'name':'Status','type':'text','required':False}],
 'projects':[{'name':'Task','type':'text','required':True},{'name':'Owner','type':'text','required':False}],
}
ALLOWED={'text','number','date','checkbox'}
def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS prime_apps(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,name TEXT NOT NULL,schema_json TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN (\'draft\',\'published\')),version INTEGER NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS prime_apps_workspace ON prime_apps(workspace_id,created)')
 c.execute('CREATE TABLE IF NOT EXISTS prime_records(id TEXT PRIMARY KEY,app_id TEXT NOT NULL,workspace_id TEXT NOT NULL,data_json TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS prime_records_tenant ON prime_records(workspace_id,app_id)')
 c.execute('CREATE TABLE IF NOT EXISTS prime_versions(app_id TEXT NOT NULL,version INTEGER NOT NULL,schema_json TEXT NOT NULL,status TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(app_id,version))')
def permission(c,uid,wid,edit=False):
 r=empire_v19.role(c,uid,wid)
 if not r or (edit and r=='viewer'):raise ValueError('Workspace unavailable or insufficient permissions')
 return r
def app(c,uid,wid,aid,edit=False):
 permission(c,uid,wid,edit)
 row=c.execute('SELECT id,name,schema_json,status,version FROM prime_apps WHERE id=? AND workspace_id=?',(aid,wid)).fetchone()
 if not row:raise ValueError('Application not found in this workspace')
 return row
def schema_check(fields):
 if not isinstance(fields,list) or not 1<=len(fields)<=20:raise ValueError('Use 1–20 fields')
 seen=set();out=[]
 for f in fields:
  if not isinstance(f,dict):raise ValueError('Invalid field')
  name=f.get('name','');typ=f.get('type','text');required=f.get('required',False)
  if not isinstance(name,str) or not 1<=len(name.strip())<=50 or typ not in ALLOWED or not isinstance(required,bool):raise ValueError('Invalid field name, type, or required flag')
  name=name.strip();key=name.casefold()
  if key in seen:raise ValueError('Field names must be unique')
  seen.add(key);out.append({'name':name,'type':typ,'required':required})
 return out
def create(c,uid,wid,name,template):
 permission(c,uid,wid,True)
 name=name.strip()
 if not 2<=len(name)<=100 or template not in TEMPLATES:raise ValueError('Invalid application name or template')
 aid=secrets.token_hex(12);schema=json.dumps(TEMPLATES[template],sort_keys=True)
 c.execute('INSERT INTO prime_apps VALUES(?,?,?,?,?,?,?,?)',(aid,wid,name,schema,'draft',1,uid,int(time.time())))
 c.execute('INSERT INTO prime_versions VALUES(?,?,?,?,?,?)',(aid,1,schema,'draft',uid,int(time.time())))
 return aid
def add_field(c,uid,wid,aid,name,typ,required):
 row=app(c,uid,wid,aid,True)
 if row[3]!='draft':raise ValueError('Published schema is locked; make a new application for changes')
 fields=json.loads(row[2]);fields.append({'name':name,'type':typ,'required':required})
 fields=schema_check(fields);schema=json.dumps(fields,sort_keys=True);ver=row[4]+1
 c.execute('UPDATE prime_apps SET schema_json=?,version=? WHERE id=? AND workspace_id=?',(schema,ver,aid,wid))
 c.execute('INSERT INTO prime_versions VALUES(?,?,?,?,?,?)',(aid,ver,schema,'draft',uid,int(time.time())))
def publish(c,uid,wid,aid):
 row=app(c,uid,wid,aid,True)
 if empire_v19.role(c,uid,wid)!='owner':raise ValueError('Only workspace owners may publish')
 schema_check(json.loads(row[2]))
 if row[3]=='published':raise ValueError('Already published')
 ver=row[4]+1
 c.execute('UPDATE prime_apps SET status=?,version=? WHERE id=? AND workspace_id=?',('published',ver,aid,wid))
 c.execute('INSERT INTO prime_versions VALUES(?,?,?,?,?,?)',(aid,ver,row[2],'published',uid,int(time.time())))
def add_record(c,uid,wid,aid,data):
 row=app(c,uid,wid,aid,True)
 if row[3]!='published':raise ValueError('Publish the application first')
 fields=json.loads(row[2]);expected={f['name'] for f in fields}
 if not isinstance(data,dict) or set(data)!=expected:raise ValueError('Record fields do not match application schema')
 clean={}
 for f in fields:
  name=f['name'];v=data[name]
  if f['type']=='checkbox':
   if not isinstance(v,bool):raise ValueError('Invalid checkbox value')
  else:
   if not isinstance(v,str) or len(v)>1000:raise ValueError('Invalid record value')
   if f['required'] and not v.strip():raise ValueError('Required field: '+name)
   if f['type']=='number' and v.strip():
    try:float(v)
    except ValueError:raise ValueError('Invalid number: '+name)
   if f['type']=='date' and v.strip():
    import datetime
    try:datetime.date.fromisoformat(v)
    except ValueError:raise ValueError('Invalid date: '+name)
  clean[name]=v
 rid=secrets.token_hex(12)
 c.execute('INSERT INTO prime_records VALUES(?,?,?,?,?,?)',(rid,aid,wid,json.dumps(clean,sort_keys=True),uid,int(time.time())))
 return rid
def delete_record(c,uid,wid,aid,rid):
 app(c,uid,wid,aid,True)
 if c.execute('DELETE FROM prime_records WHERE id=? AND app_id=? AND workspace_id=?',(rid,aid,wid)).rowcount!=1:raise ValueError('Record not found')
def render(c,uid,csrf,wid='',aid='',message=''):
 esc=lambda x:html.escape(str(x),quote=True)
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not wid and ws:wid=ws[0][0]
 if wid:permission(c,uid,wid)
 h=['<section class="panel"><h1>✦ GENESIS PRIME V20.1</h1><p>Private schema-driven business applications. Local SQLite pilot. No automatic AI generation, external deployment, or payment integration.</p><p><a href="/empire">Manage business workspaces</a></p>']
 if message:h.append('<p><strong>'+esc(message)+'</strong></p>')
 h.append('<p>Choose workspace: '+''.join('<a style="margin-right:12px" href="/genesis-prime?w='+esc(w)+'">'+esc(n)+'</a>' for w,n,_ in ws)+'</p></section>')
 if not wid:return ''.join(h)
 r=permission(c,uid,wid)
 if r in ('owner','editor'):
  h.append('<section class="panel"><h2>Create application</h2><form method="post" action="/genesis-prime"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="create"><label>Name<input name="name" maxlength="100" required></label><label>Template<select name="template">'+''.join('<option value="'+t+'">'+t.title()+'</option>' for t in TEMPLATES)+'</select></label><button>Create draft</button></form></section>')
 apps=c.execute('SELECT id,name,status FROM prime_apps WHERE workspace_id=? ORDER BY created DESC',(wid,)).fetchall()
 h.append('<section class="panel"><h2>Workspace applications</h2>'+''.join('<p><a href="/genesis-prime?w='+esc(wid)+'&app='+esc(i)+'">'+esc(n)+'</a> — '+esc(s)+'</p>' for i,n,s in apps)+'</section>')
 if aid:
  row=app(c,uid,wid,aid);fields=json.loads(row[2]);h.append('<section class="panel"><h2>'+esc(row[1])+'</h2><p>Status: '+esc(row[3])+' · version '+str(row[4])+'</p><h3>Fields</h3><ul>'+''.join('<li>'+esc(f['name'])+' ('+esc(f['type'])+')'+(' required' if f['required'] else '')+'</li>' for f in fields)+'</ul>')
  if row[3]=='draft' and r in ('owner','editor'):
   h.append('<form method="post" action="/genesis-prime"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="app" value="'+esc(aid)+'"><input type="hidden" name="action" value="field"><label>New field<input name="name" maxlength="50" required></label><label>Type<select name="type">'+''.join('<option>'+t+'</option>' for t in sorted(ALLOWED))+'</select></label><label><input type="checkbox" name="required" value="yes"> Required</label><button>Add field</button></form>')
   if r=='owner':h.append('<form method="post" action="/genesis-prime"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="app" value="'+esc(aid)+'"><input type="hidden" name="action" value="publish"><button>Approve and publish</button></form>')
  if row[3]=='published':
   if r in ('owner','editor'):
    h.append('<h3>Add record</h3><form method="post" action="/genesis-prime"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="app" value="'+esc(aid)+'"><input type="hidden" name="action" value="record">')
    for i,f in enumerate(fields):
     typ=f['type'];htmltyp={'number':'number','date':'date','text':'text','checkbox':'checkbox'}[typ]
     h.append('<label>'+esc(f['name'])+'<input name="f'+str(i)+'" type="'+htmltyp+'" '+('required ' if f['required'] and typ!='checkbox' else '')+('step="any" ' if typ=='number' else '')+'></label>')
    h.append('<button>Save record</button></form>')
   rows=c.execute('SELECT id,data_json FROM prime_records WHERE workspace_id=? AND app_id=? ORDER BY created DESC LIMIT 100',(wid,aid)).fetchall()
   h.append('<h3>Records</h3>')
   for rid,data in rows:
    d=json.loads(data);h.append('<div style="border-top:1px solid #655777;padding:10px"><p>'+esc(' · '.join(f['name']+': '+str(d.get(f['name'],'')) for f in fields))+'</p>')
    if r in ('owner','editor'):h.append('<form method="post" action="/genesis-prime"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="app" value="'+esc(aid)+'"><input type="hidden" name="record" value="'+esc(rid)+'"><input type="hidden" name="action" value="delete"><button>Delete</button></form>')
    h.append('</div>')
  h.append('</section>')
 return ''.join(h)
