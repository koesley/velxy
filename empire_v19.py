"""Empire V19.1 — isolated business workspace pilot. SQLite local only."""
import html, secrets, hashlib, time

def setup(c):
 c.execute("CREATE TABLE IF NOT EXISTS empire_workspaces(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE TABLE IF NOT EXISTS empire_members(workspace_id TEXT NOT NULL,user_id INTEGER NOT NULL,role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')),PRIMARY KEY(workspace_id,user_id))")
 c.execute("CREATE TABLE IF NOT EXISTS empire_invites(code_hash TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('editor','viewer')),created_by INTEGER NOT NULL,expires INTEGER NOT NULL,used_by INTEGER,used_at INTEGER)")
 c.execute("CREATE TABLE IF NOT EXISTS empire_records(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,title TEXT NOT NULL,detail TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE INDEX IF NOT EXISTS empire_records_workspace ON empire_records(workspace_id,created)")

def role(c,uid,wid):
 row=c.execute('SELECT role FROM empire_members WHERE user_id=? AND workspace_id=?',(uid,wid)).fetchone()
 return row[0] if row else None

def create(c,uid,name):
 name=name.strip()
 if not 2<=len(name)<=90:raise ValueError('Business name must be 2–90 characters')
 wid=secrets.token_hex(12)
 c.execute('INSERT INTO empire_workspaces VALUES(?,?,?,?)',(wid,name,uid,int(time.time())))
 c.execute('INSERT INTO empire_members VALUES(?,?,?)',(wid,uid,'owner'))
 return wid

def invite(c,uid,wid,member_role):
 if role(c,uid,wid)!='owner':raise ValueError('Only owners can invite members')
 if member_role not in ('editor','viewer'):raise ValueError('Invalid member role')
 code=secrets.token_urlsafe(24)
 c.execute('INSERT INTO empire_invites(code_hash,workspace_id,role,created_by,expires) VALUES(?,?,?,?,?)',(hashlib.sha256(code.encode()).hexdigest(),wid,member_role,uid,int(time.time())+86400))
 return code

def accept(c,uid,code):
 if not 20<=len(code)<=100:raise ValueError('Invalid invitation code')
 key=hashlib.sha256(code.encode()).hexdigest()
 row=c.execute('SELECT workspace_id,role,expires,used_by FROM empire_invites WHERE code_hash=?',(key,)).fetchone()
 if not row or row[2]<int(time.time()) or row[3] is not None:raise ValueError('Invitation invalid, expired, or already used')
 wid,member_role=row[0],row[1]
 if role(c,uid,wid):raise ValueError('Already a member')
 changed=c.execute('UPDATE empire_invites SET used_by=?,used_at=? WHERE code_hash=? AND used_by IS NULL AND expires>=?',(uid,int(time.time()),key,int(time.time()))).rowcount
 if changed!=1:raise ValueError('Invitation already used')
 c.execute('INSERT INTO empire_members VALUES(?,?,?)',(wid,uid,member_role))
 return wid

def add_record(c,uid,wid,title,detail):
 if role(c,uid,wid) not in ('owner','editor'):raise ValueError('Editing requires owner or editor role')
 title=title.strip();detail=detail.strip()
 if not 1<=len(title)<=120 or len(detail)>3000:raise ValueError('Invalid record length')
 rid=secrets.token_hex(12)
 c.execute('INSERT INTO empire_records VALUES(?,?,?,?,?,?)',(rid,wid,title,detail,uid,int(time.time())))
 return rid

def delete_record(c,uid,wid,rid):
 if role(c,uid,wid) not in ('owner','editor'):raise ValueError('Editing requires owner or editor role')
 return c.execute('DELETE FROM empire_records WHERE workspace_id=? AND id=?',(wid,rid)).rowcount

def render(c,uid,csrf,wid='',message='',invite_code=''):
 esc=lambda s:html.escape(str(s),quote=True)
 workspaces=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if wid and not role(c,uid,wid):raise ValueError('Workspace not found')
 if not wid and workspaces:wid=workspaces[0][0]
 h=['<div class="v19"><section class="panel"><h1>♛ EMPIRE V19 — Business Workspaces</h1><p>Private workspace pilot: member roles, expiring invite codes and isolated workspace records. Older portal modules remain account-scoped and are NOT shared or isolated by these workspace roles.</p>']
 if message:h.append('<p><strong>'+esc(message)+'</strong></p>')
 if invite_code:h.append('<p>Copy this one-time invitation code now; it will not be displayed again: <code>'+esc(invite_code)+'</code></p>')
 h.append('<form method="post" action="/empire"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="create"><label>New business name<input name="name" maxlength="90" required></label><button>Create workspace</button></form>')
 h.append('<form method="post" action="/empire"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="accept"><label>Invitation code<input name="code" maxlength="100" required></label><button>Join workspace</button></form></section>')
 if workspaces:
  h.append('<section class="panel"><h2>Your workspaces</h2>')
  for w,name,r in workspaces:h.append('<a style="margin-right:14px" href="/empire?w='+esc(w)+'">'+esc(name)+' ('+esc(r)+')</a>')
  h.append('</section>')
 if wid:
  current=next((w for w in workspaces if w[0]==wid),None)
  if current:
   r=current[2]
   h.append('<section class="panel"><h2>'+esc(current[1])+'</h2><p>Your role: '+esc(r)+'</p>')
   members=c.execute('SELECT u.email,m.role FROM empire_members m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=? ORDER BY m.role,u.email',(wid,)).fetchall()
   h.append('<h3>Members</h3><ul>')
   for email,mrole in members:h.append('<li>'+esc(email)+' — '+esc(mrole)+'</li>')
   h.append('</ul>')
   if r=='owner':
    h.append('<form method="post" action="/empire"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="invite"><input type="hidden" name="workspace" value="'+esc(wid)+'"><label>Invite role<select name="role"><option value="viewer">Viewer</option><option value="editor">Editor</option></select></label><button>Create 24-hour one-time invitation</button></form>')
   if r in ('owner','editor'):
    h.append('<h3>Add workspace record</h3><form method="post" action="/empire"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="add"><input type="hidden" name="workspace" value="'+esc(wid)+'"><label>Title<input name="title" maxlength="120" required></label><label>Details<textarea name="detail" maxlength="3000"></textarea></label><button>Save record</button></form>')
   h.append('<h3>Workspace records</h3>')
   rows=c.execute('SELECT id,title,detail FROM empire_records WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()
   for rid,title,detail in rows:
    h.append('<div style="border-top:1px solid #655777;padding:12px 0"><strong>'+esc(title)+'</strong><p>'+esc(detail)+'</p>')
    if r in ('owner','editor'):h.append('<form method="post" action="/empire"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action" value="delete"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="record" value="'+esc(rid)+'"><button>Delete record</button></form>')
    h.append('</div>')
   if not rows:h.append('<p>No records in this workspace yet.</p>')
   h.append('</section>')
 return ''.join(h)+'</div>'
