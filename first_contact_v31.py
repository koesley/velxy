"""V31 First Contact: workspace-scoped local pilot issue tracker."""
import html, secrets, time
import empire_v19

def esc(v):return html.escape(str(v),quote=True)
def setup(c):
 c.execute("CREATE TABLE IF NOT EXISTS first_contact_issues(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,pilot_id TEXT NOT NULL,created_by INTEGER NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,severity TEXT NOT NULL CHECK(severity IN ('low','medium','high')),status TEXT NOT NULL CHECK(status IN ('open','resolved')),created INTEGER NOT NULL,updated INTEGER NOT NULL)")
 c.execute('CREATE INDEX IF NOT EXISTS first_contact_workspace ON first_contact_issues(workspace_id,pilot_id,created)')
def access(c,uid,wid,write=False):
 role=empire_v19.role(c,uid,wid)
 if not role or (write and role not in ('owner','editor')):raise ValueError('Workspace unavailable or insufficient permission')
 return role
def pilot(c,wid,pid):
 if not c.execute('SELECT 1 FROM launchpad_pilots WHERE workspace_id=? AND id=?',(wid,pid)).fetchone():raise ValueError('Pilot unavailable')
def create(c,uid,wid,pid,title,description,severity):
 access(c,uid,wid,True);pilot(c,wid,pid)
 title=title.strip();description=description.strip()
 if not 5<=len(title)<=120 or not 10<=len(description)<=2000:raise ValueError('Title 5–120 and description 10–2000 characters required')
 if severity not in ('low','medium','high'):raise ValueError('Invalid severity')
 iid=secrets.token_hex(12);now=int(time.time())
 c.execute('INSERT INTO first_contact_issues VALUES(?,?,?,?,?,?,?,?,?,?)',(iid,wid,pid,uid,title,description,severity,'open',now,now))
 return iid
def resolve(c,uid,wid,iid):
 access(c,uid,wid,True)
 result=c.execute("UPDATE first_contact_issues SET status='resolved',updated=? WHERE id=? AND workspace_id=? AND status='open'",(int(time.time()),iid,wid))
 if result.rowcount!=1:raise ValueError('Open issue unavailable')
def render(c,uid,csrf,wid='',message=''):
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<section class="panel"><h1>First Contact V31</h1><p>Create a workspace first.</p><a href="/empire">Open Empire</a></section>'
 if not wid:wid=ws[0][0]
 role=access(c,uid,wid)
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
 pilots=c.execute('SELECT id,name,status FROM launchpad_pilots WHERE workspace_id=? ORDER BY created DESC LIMIT 50',(wid,)).fetchall()
 issues=c.execute('SELECT id,pilot_id,title,description,severity,status FROM first_contact_issues WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()
 opened=sum(i[5]=='open' for i in issues)
 parts=['<section class="hero"><p class="eyebrow">VELXTRIA V31 · PROJECT FIRST CONTACT</p><h1>Customer validation, grounded in evidence.</h1><p>Track local pilot issues and feedback. This is not a remote customer invitation service.</p></section>', '<section class="panel"><form method="get" action="/first-contact"><label>Workspace<select name="w">'+options+'</select></label><button>Switch</button></form></section>', '<section class="panel"><h2>Pilot issue overview</h2><p>'+str(len(pilots))+' pilots · '+str(len(issues))+' recent issues · '+str(opened)+' open</p><p><a href="/launchpad?w='+esc(wid)+'">Manage pilots and feedback</a> · <a href="/integration?w='+esc(wid)+'">Customer journey</a></p></section>']
 if message:parts.append('<section class="panel"><p>'+esc(message)+'</p></section>')
 if role in ('owner','editor') and pilots:
  opts=''.join('<option value="'+esc(p[0])+'">'+esc(p[1])+' ('+esc(p[2])+')</option>' for p in pilots)
  parts.append('<section class="panel"><h2>Report pilot issue</h2><form method="post" action="/first-contact"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="create"><label>Pilot<select name="pilot">'+opts+'</select></label><label>Issue title<input name="title" minlength="5" maxlength="120" required></label><label>Description<textarea name="description" minlength="10" maxlength="2000" required></textarea></label><label>Severity<select name="severity"><option>low</option><option selected>medium</option><option>high</option></select></label><button>Record issue</button></form></section>')
 names={p[0]:p[1] for p in pilots}
 for iid,pid,title,desc,severity,status in issues:
  parts.append('<section class="panel"><h3>'+esc(title)+'</h3><p>'+esc(names.get(pid,'Pilot'))+' · '+esc(severity)+' · '+esc(status)+'</p><p>'+esc(desc)+'</p>')
  if status=='open' and role in ('owner','editor'):parts.append('<form method="post" action="/first-contact"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="issue" value="'+esc(iid)+'"><input type="hidden" name="action" value="resolve"><button>Mark resolved</button></form>')
  parts.append('</section>')
 if not pilots:parts.append('<section class="panel"><p>No pilot exists yet. Create one in Launchpad.</p></section>')
 parts.append('<section class="panel"><h2>Release boundary</h2><p>Local-only pilot issue tracker. No external invitations, automated customer access, production security certification, or live browser test evidence.</p></section>')
 return ''.join(parts)
