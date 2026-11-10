"""VELXTRIA V10: bounded no-code mini-apps, local collaboration boards, spatial navigation."""
import html,json,secrets,time,re

def e(v):return html.escape(str(v),quote=True)
def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS vx10_apps(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL,schema_json TEXT NOT NULL,created_at INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS vx10_records(id TEXT PRIMARY KEY,app_id TEXT NOT NULL,user_id INTEGER NOT NULL,data_json TEXT NOT NULL,created_at INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS vx10_record_scope ON vx10_records(user_id,app_id)')
 c.execute('CREATE TABLE IF NOT EXISTS vx10_nexus(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,title TEXT NOT NULL,partner TEXT NOT NULL,details TEXT NOT NULL,status TEXT NOT NULL,created_at INTEGER NOT NULL)')

def app_create(c,uid,name,description,fields):
 name=name.strip()[:80]; description=description.strip()[:500]
 if not name:raise ValueError('Application name required')
 raw=[x.strip() for x in fields.split(',') if x.strip()]
 if not 1<=len(raw)<=12:raise ValueError('Provide 1–12 comma-separated field names')
 if any(len(x)>40 or not re.fullmatch(r'[\w \-]+',x) for x in raw) or len(set(x.lower() for x in raw))!=len(raw):raise ValueError('Field names must be unique, 40 characters or fewer, and contain only letters, numbers, spaces, hyphens or underscores')
 ident=secrets.token_hex(12)
 c.execute('INSERT INTO vx10_apps VALUES(?,?,?,?,?,?)',(ident,uid,name,description,json.dumps(raw),int(time.time())))
 return ident

def record_create(c,uid,app_id,fields):
 row=c.execute('SELECT schema_json FROM vx10_apps WHERE id=? AND user_id=?',(app_id,uid)).fetchone()
 if not row:raise ValueError('App not found')
 schema=json.loads(row[0]); values={k:fields.get('field_'+str(i),'').strip()[:500] for i,k in enumerate(schema)}
 if not any(values.values()):raise ValueError('Enter at least one value')
 c.execute('INSERT INTO vx10_records VALUES(?,?,?,?,?)',(secrets.token_hex(12),app_id,uid,json.dumps(values),int(time.time())))

def record_delete(c,uid,app_id,record_id):
 c.execute('DELETE FROM vx10_records WHERE id=? AND app_id=? AND user_id=?',(record_id,app_id,uid))

def nexus_create(c,uid,title,partner,details):
 title=title.strip()[:100];partner=partner.strip()[:100];details=details.strip()[:1200]
 if not title or not details:raise ValueError('Title and proposal details are required')
 c.execute('INSERT INTO vx10_nexus VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),uid,title,partner,details,'draft',int(time.time())))

def nexus_status(c,uid,ident,status):
 if status not in ('draft','ready','archived'):raise ValueError('Invalid status')
 c.execute('UPDATE vx10_nexus SET status=? WHERE id=? AND user_id=?',(status,ident,uid))

def form(csrf,action,extra=''):
 return '<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="action" value="'+e(action)+'">'+extra

def render(c,uid,csrf,tab='genesis',app_id=''):
 if tab not in ('genesis','nexus','aether'):tab='genesis'
 out=['<section class="hero vx10hero"><p class="eyebrow">VELXTRIA V10 / THREE WORLDS · ONE PLATFORM</p><h1>PROJECT <em>TRINITY.</em></h1><p>GENESIS builds useful internal apps. NEXUS organizes collaboration proposals. AETHER lets you explore your workspace spatially. All three are local-first and account-scoped.</p></section>', '<div class="vx10tabs"><a href="/trinity?tab=genesis">◈ GENESIS / CREATE</a><a href="/trinity?tab=nexus">◇ NEXUS / CONNECT</a><a href="/trinity?tab=aether">✧ AETHER / EXPLORE</a></div>']
 if tab=='genesis':
  out.append('<section class="panel"><p class="eyebrow">01 / GENESIS SOFTWARE STUDIO</p><h2>Create a working mini-application</h2><p>Define a custom data collection tool. VELXTRIA creates a private app with working forms, storage, and a record viewer—no generated Python execution.</p><form method="post" action="/trinity">'+form(csrf,'create_app')+'<label>Application name<input name="name" maxlength="80" required placeholder="Appointment tracker"></label><label>Description<input name="description" maxlength="500" placeholder="Manage bookings for a small business"></label><label>Fields (comma-separated)<input name="fields" required placeholder="Customer, Service, Date, Status"></label><button>Create application</button></form></section>')
  apps=c.execute('SELECT id,name,description,schema_json FROM vx10_apps WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
  out.append('<section class="panel"><h2>Your generated applications</h2>')
  if not apps:out.append('<p>No applications yet. Create one above.</p>')
  for ident,name,description,schema in apps:
   out.append('<a class="vx10app" href="/trinity?tab=genesis&amp;app='+e(ident)+'"><strong>'+e(name)+'</strong><small>'+e(description or 'Custom internal app')+'</small></a>')
  out.append('</section>')
  chosen=next((a for a in apps if a[0]==app_id),None)
  if chosen:
   ident,name,description,schema=chosen;fields=json.loads(schema)
   out.append('<section class="panel"><p class="eyebrow">LIVE APPLICATION</p><h2>'+e(name)+'</h2><form method="post" action="/trinity">'+form(csrf,'add_record','<input type="hidden" name="app_id" value="'+e(ident)+'">'))
   for i,field in enumerate(fields):out.append('<label>'+e(field)+'<input name="field_'+str(i)+'" maxlength="500" placeholder="'+e(field)+'"></label>')
   out.append('<button>Save record</button></form><h3>Stored records</h3><div class="scroll"><table><thead><tr>'+''.join('<th>'+e(f)+'</th>' for f in fields)+'<th>Action</th></tr></thead><tbody>')
   rows=c.execute('SELECT id,data_json FROM vx10_records WHERE app_id=? AND user_id=? ORDER BY created_at DESC LIMIT 100',(ident,uid)).fetchall()
   for rid,raw in rows:
    data=json.loads(raw)
    out.append('<tr>'+''.join('<td>'+e(data.get(f,''))+'</td>' for f in fields)+'<td><form method="post" action="/trinity">'+form(csrf,'delete_record','<input type="hidden" name="app_id" value="'+e(ident)+'"><input type="hidden" name="record_id" value="'+e(rid)+'">')+'<button type="submit">Delete</button></form></td></tr>')
   out.append('</tbody></table></div><p>Showing up to 100 recent records. Changes are stored in your existing VELXTRIA database.</p></section>')
 elif tab=='nexus':
  out.append('<section class="panel"><p class="eyebrow">02 / NEXUS COLLABORATION DESK</p><h2>Build a partnership pipeline</h2><p>Prepare internal collaboration proposals, track readiness, and archive decisions. Nothing is shared with outside businesses automatically.</p><form method="post" action="/trinity">'+form(csrf,'create_nexus')+'<label>Collaboration title<input name="title" required maxlength="100" placeholder="Supplier partnership"></label><label>Potential partner<input name="partner" maxlength="100" placeholder="Business or team"></label><label>Proposal<textarea name="details" required maxlength="1200" rows="4"></textarea></label><button>Create proposal</button></form></section><section class="panel"><h2>Collaboration board</h2>')
  rows=c.execute('SELECT id,title,partner,details,status FROM vx10_nexus WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(uid,)).fetchall()
  if not rows:out.append('<p>No proposals yet.</p>')
  for ident,title,partner,details,status in rows:
   out.append('<article class="vx10proposal"><span class="eyebrow">'+e(status.upper())+'</span><h3>'+e(title)+'</h3><p>Potential partner: '+e(partner or 'Not assigned')+'</p><p>'+e(details)+'</p><form method="post" action="/trinity">'+form(csrf,'nexus_status','<input type="hidden" name="proposal_id" value="'+e(ident)+'">')+'<label>Internal status<select name="status">'+''.join('<option value="'+v+'"'+(' selected' if status==v else '')+'>'+v.title()+'</option>' for v in ('draft','ready','archived'))+'</select></label><button>Update status</button></form></article>')
  out.append('</section>')
 else:
  apps=c.execute('SELECT count(*) FROM vx10_apps WHERE user_id=?',(uid,)).fetchone()[0]
  proposals=c.execute('SELECT count(*) FROM vx10_nexus WHERE user_id=?',(uid,)).fetchone()[0]
  missions=c.execute('SELECT count(*) FROM vx52_missions WHERE user_id=?',(uid,)).fetchone()[0]
  dossiers=c.execute('SELECT count(*) FROM vx9_dossiers WHERE user_id=?',(uid,)).fetchone()[0]
  out.append('<section class="panel"><p class="eyebrow">03 / AETHER SPATIAL WORKSPACE</p><h2>Your business universe</h2><p>A navigable, perspective-styled workspace. Select a world to open the real underlying module.</p><div class="vx10space"><a class="vx10planet" href="/trinity?tab=genesis"><b>◈</b><strong>GENESIS</strong><span>'+str(apps)+' apps</span></a><a class="vx10planet" href="/trinity?tab=nexus"><b>◇</b><strong>NEXUS</strong><span>'+str(proposals)+' proposals</span></a><a class="vx10planet" href="/missions"><b>✦</b><strong>MISSIONS</strong><span>'+str(missions)+' missions</span></a><a class="vx10planet" href="/constellation"><b>✧</b><strong>CONSTELLATION</strong><span>'+str(dossiers)+' dossiers</span></a></div><p>This is an interactive spatial navigation interface, not a full 3D simulation.</p></section>')
 return ''.join(out)
CSS="""
.vx10hero{background:radial-gradient(circle at 78% 25%,#533084 0%,#20132d 43%,#100d1d 100%);border:1px solid #8053b8}.vx10hero em{color:#d9b5ff}.vx10tabs{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}.vx10tabs a,.vx10app{display:block;border:1px solid #8254ad;border-radius:14px;padding:14px;color:#e7d3ff;text-decoration:none;background:#1d1530}.vx10app{margin:10px 0}.vx10app small{display:block;color:#bca8ce}.vx10proposal{padding:18px;margin:12px 0;border:1px solid #6d4c96;border-radius:16px;background:#1b1529}.vx10space{min-height:370px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;align-items:center;padding:35px;perspective:900px;background:radial-gradient(ellipse,#2b1a4e,#100e1c 72%);border:1px solid #7653a0;border-radius:20px}.vx10planet{transform:rotateX(8deg) rotateY(-8deg);transition:transform .2s,box-shadow .2s;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:130px;gap:6px;border:1px solid #9c6be0;border-radius:24px;background:linear-gradient(135deg,#4c2a78,#171229);box-shadow:0 15px 45px #090512;color:#f3e8ff;text-decoration:none}.vx10planet:hover,.vx10planet:focus{transform:rotateX(0) rotateY(0) scale(1.04);box-shadow:0 10px 38px #7447ae}.vx10planet b{font-size:28px}.vx10planet span{color:#d1b4ed;font-size:13px}@media(max-width:550px){.vx10space{gap:10px;padding:14px}.vx10planet{min-height:120px}}
"""
