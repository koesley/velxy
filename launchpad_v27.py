"""V27 Launchpad: local-only, tenant-scoped pilot onboarding and feedback."""
import html, secrets, time
import empire_v19

def esc(v): return html.escape(str(v),quote=True)

def setup(c):
 c.execute("CREATE TABLE IF NOT EXISTS launchpad_pilots(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,created_by INTEGER NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','completed')),created INTEGER NOT NULL,completed INTEGER)")
 c.execute("CREATE INDEX IF NOT EXISTS launchpad_pilot_workspace ON launchpad_pilots(workspace_id,created)")
 c.execute("CREATE TABLE IF NOT EXISTS launchpad_feedback(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,pilot_id TEXT NOT NULL,user_id INTEGER NOT NULL,rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),comment TEXT NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE INDEX IF NOT EXISTS launchpad_feedback_pilot ON launchpad_feedback(workspace_id,pilot_id,created)")

def membership(c,uid,wid,write=False):
 r=empire_v19.role(c,uid,wid)
 if r is None or (write and r not in ('owner','editor')):raise ValueError('Workspace unavailable or insufficient permission')
 return r

def create(c,uid,wid,name):
 membership(c,uid,wid,True);name=name.strip()
 if not 3<=len(name)<=90:raise ValueError('Pilot name must contain 3–90 characters')
 pid=secrets.token_hex(12)
 c.execute('INSERT INTO launchpad_pilots VALUES(?,?,?,?,?,?,?)',(pid,wid,uid,name,'active',int(time.time()),None))
 return pid

def evidence(c,wid):
 def count(sql):return c.execute(sql,(wid,)).fetchone()[0]
 apps=count("SELECT COUNT(*) FROM prime_apps WHERE workspace_id=? AND status='published'")
 records=count('SELECT COUNT(*) FROM prime_records WHERE workspace_id=?')
 goals=count('SELECT COUNT(*) FROM nexus_goals WHERE workspace_id=?')
 return [('Published business application',apps>0,'/genesis-prime'),('At least one application record',records>0,'/genesis-prime'),('Measurable business goal',goals>0,'/nexus-intelligence')]

def finish(c,uid,wid,pid):
 if membership(c,uid,wid)!='owner':raise ValueError('Only owners can complete pilots')
 row=c.execute('SELECT status FROM launchpad_pilots WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
 if not row:raise ValueError('Pilot unavailable')
 if row[0]!='active':raise ValueError('Pilot already completed')
 if not all(ok for _,ok,_ in evidence(c,wid)):raise ValueError('Complete all evidence-based steps before closing the pilot')
 if not c.execute('SELECT 1 FROM launchpad_feedback WHERE workspace_id=? AND pilot_id=?',(wid,pid)).fetchone():raise ValueError('Collect pilot feedback before completion')
 c.execute("UPDATE launchpad_pilots SET status='completed',completed=? WHERE id=? AND workspace_id=?",(int(time.time()),pid,wid))

def feedback(c,uid,wid,pid,rating,comment):
 membership(c,uid,wid,True)
 if not c.execute("SELECT 1 FROM launchpad_pilots WHERE id=? AND workspace_id=? AND status='active'",(pid,wid)).fetchone():raise ValueError('Active pilot unavailable')
 try:r=int(rating)
 except (TypeError,ValueError):raise ValueError('Rating must be between 1 and 5')
 comment=comment.strip()
 if r not in range(1,6) or not 5<=len(comment)<=1500:raise ValueError('Rating 1–5 and feedback 5–1500 characters required')
 fid=secrets.token_hex(12)
 c.execute('INSERT INTO launchpad_feedback VALUES(?,?,?,?,?,?,?)',(fid,wid,pid,uid,r,comment,int(time.time())))
 return fid

def render(c,uid,csrf,wid='',message=''):
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<section class="panel"><h1>Launchpad V27</h1><p>Create an Empire workspace to begin.</p><a href="/empire">Open Empire</a></section>'
 if not wid:wid=ws[0][0]
 role=membership(c,uid,wid)
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
 parts=['<section class="hero"><p class="eyebrow">VELXTRIA V27 · PROJECT LAUNCHPAD</p><h1>Customer Pilot Launchpad</h1><p>Guide a real trial from setup to feedback. Checklist items reflect saved workspace data, not self-reported completion.</p></section>', '<section class="panel"><form method="get" action="/launchpad"><label>Workspace<select name="w">'+options+'</select></label><button>Switch</button></form></section>']
 if message:parts.append('<section class="panel"><p>'+esc(message)+'</p></section>')
 checks=evidence(c,wid)
 parts.append('<section class="panel"><h2>Readiness checklist</h2><ul>'+''.join('<li>'+('✓ ' if ok else '○ ')+esc(label)+' · <a href="'+url+'?w='+esc(wid)+'">Open tool</a></li>' for label,ok,url in checks)+'</ul><p>Use test data for initial pilots. Completion requires all three steps and written feedback.</p></section>')
 if role in ('owner','editor'):
  parts.append('<section class="panel"><h2>Start a pilot</h2><form method="post" action="/launchpad"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="create"><label>Pilot name<input name="name" minlength="3" maxlength="90" required placeholder="e.g. Inventory trial"></label><button>Create pilot</button></form></section>')
 pilots=c.execute('SELECT id,name,status,created FROM launchpad_pilots WHERE workspace_id=? ORDER BY created DESC LIMIT 40',(wid,)).fetchall()
 for pid,name,status,created in pilots:
  feedback_rows=c.execute('SELECT rating,comment,created FROM launchpad_feedback WHERE workspace_id=? AND pilot_id=? ORDER BY created DESC LIMIT 30',(wid,pid)).fetchall()
  parts.append('<section class="panel"><h2>'+esc(name)+'</h2><p>Status: '+esc(status)+' · Feedback entries: '+str(len(feedback_rows))+'</p>')
  if status=='active' and role in ('owner','editor'):
   parts.append('<form method="post" action="/launchpad"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="pilot" value="'+esc(pid)+'"><input type="hidden" name="action" value="feedback"><label>Trial rating (1–5)<select name="rating">'+''.join('<option>'+str(i)+'</option>' for i in range(1,6))+'</select></label><label>What worked, what failed?<textarea name="comment" minlength="5" maxlength="1500" required></textarea></label><button>Save feedback</button></form>')
  if status=='active' and role=='owner':
   parts.append('<form method="post" action="/launchpad"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="pilot" value="'+esc(pid)+'"><input type="hidden" name="action" value="finish"><button>Complete pilot (requires checklist + feedback)</button></form>')
  parts.append('<ul>'+''.join('<li>Rating '+str(r)+' / 5 — '+esc(comment)+'</li>' for r,comment,_ in feedback_rows)+'</ul></section>')
 if not pilots:parts.append('<section class="panel"><p>No pilot runs yet.</p></section>')
 parts.append('<section class="panel"><h2>Release boundaries</h2><p>Local SQLite pilot only. No automatic customer invitations, email delivery, payments, remote access, or security certification. Older modules have not undergone a full tenant-isolation audit.</p></section>')
 return ''.join(parts)
