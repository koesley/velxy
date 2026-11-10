"""V33 Evolutionary Core: human-reviewed local release gates tied to Horizon plans.
No code execution, automatic deployments, or file uploads are performed here.
"""
import html, secrets, time
import empire_v19

def esc(value): return html.escape(str(value), quote=True)
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS evolution_releases(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,plan_id TEXT NOT NULL,created_by INTEGER NOT NULL,title TEXT NOT NULL,version_label TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('draft','testing','approved','rejected')),test_notes TEXT NOT NULL DEFAULT '',test_result TEXT NOT NULL DEFAULT 'not_run' CHECK(test_result IN ('not_run','passed','failed')),review_note TEXT NOT NULL DEFAULT '',reviewed_by INTEGER,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
 c.execute('CREATE INDEX IF NOT EXISTS evolution_release_workspace ON evolution_releases(workspace_id,created)')
def access(c,uid,wid,write=False,owner=False):
 role=empire_v19.role(c,uid,wid)
 if not role or (write and role not in ('owner','editor')) or (owner and role!='owner'):raise ValueError('Workspace unavailable or insufficient permission')
 return role
def plan(c,wid,pid):
 r=c.execute('SELECT status,success_metric,baseline,target,result FROM horizon_plans WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
 if not r:raise ValueError('Improvement plan unavailable')
 return r
def create(c,uid,wid,pid,title,version):
 access(c,uid,wid,write=True);plan(c,wid,pid)
 title=title.strip();version=version.strip()
 if not 5<=len(title)<=120 or not 1<=len(version)<=60:raise ValueError('Release title must be 5–120 characters and version 1–60')
 rid=secrets.token_hex(12);ts=int(time.time())
 c.execute('INSERT INTO evolution_releases(id,workspace_id,plan_id,created_by,title,version_label,status,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(rid,wid,pid,uid,title,version,'draft',ts,ts))
 return rid
def record_test(c,uid,wid,rid,result,notes):
 access(c,uid,wid,write=True)
 if result not in ('passed','failed'):raise ValueError('Test result must be passed or failed')
 notes=notes.strip()
 if not 10<=len(notes)<=3000:raise ValueError('Test evidence must contain 10–3000 characters')
 row=c.execute('SELECT status FROM evolution_releases WHERE id=? AND workspace_id=?',(rid,wid)).fetchone()
 if not row:raise ValueError('Release unavailable')
 if row[0] in ('approved','rejected'):raise ValueError('Reviewed releases are immutable; create a new release')
 c.execute('UPDATE evolution_releases SET status=?,test_result=?,test_notes=?,updated=? WHERE id=? AND workspace_id=?',('testing',result,notes,int(time.time()),rid,wid))
def review(c,uid,wid,rid,decision,note,data_root=None):
 access(c,uid,wid,owner=True)
 if decision not in ('approved','rejected'):raise ValueError('Invalid review decision')
 note=note.strip()
 if not 10<=len(note)<=2000:raise ValueError('Review note must contain 10–2000 characters')
 row=c.execute('SELECT plan_id,status,test_result,test_notes FROM evolution_releases WHERE id=? AND workspace_id=?',(rid,wid)).fetchone()
 if not row:raise ValueError('Release unavailable')
 if row[1] in ('approved','rejected'):raise ValueError('Release already reviewed')
 if decision=='approved':
  if row[1]!='testing' or row[2]!='passed' or not row[3]:raise ValueError('Approval requires recorded passing test evidence')
  if plan(c,wid,row[0])[0]!='verified':raise ValueError('Approval requires a verified Horizon improvement plan')
  if data_root is not None:
   import sovereign_gate_v35
   sovereign_gate_v35.verify_gate(c,wid,rid,data_root)
 c.execute('UPDATE evolution_releases SET status=?,review_note=?,reviewed_by=?,updated=? WHERE id=? AND workspace_id=?',(decision,note,uid,int(time.time()),rid,wid))
 if data_root is not None:
  import sovereign_gate_v35
  sovereign_gate_v35.audit(c,wid,rid,uid,'owner_'+decision,note)
def render(c,uid,csrf,wid='',message=''):
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<section class="panel"><h1>Evolutionary Core V33</h1><p>Create a workspace in Empire first.</p></section>'
 if not wid:wid=ws[0][0]
 role=access(c,uid,wid)
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
 plans=c.execute('SELECT p.id,i.title,p.status FROM horizon_plans p JOIN first_contact_issues i ON i.id=p.issue_id AND i.workspace_id=p.workspace_id WHERE p.workspace_id=? ORDER BY p.created DESC LIMIT 200',(wid,)).fetchall()
 releases=c.execute('SELECT r.id,r.title,r.version_label,r.status,r.test_result,r.test_notes,r.review_note,i.title,p.status FROM evolution_releases r JOIN horizon_plans p ON p.id=r.plan_id AND p.workspace_id=r.workspace_id JOIN first_contact_issues i ON i.id=p.issue_id AND i.workspace_id=p.workspace_id WHERE r.workspace_id=? ORDER BY r.created DESC LIMIT 100',(wid,)).fetchall()
 out=['<section class="hero"><p class="eyebrow">VELXTRIA V33 · PROJECT EVOLUTIONARY CORE</p><h1>Test fixes before approving releases.</h1><p>Connect Horizon improvements to human-recorded test evidence and owner-controlled release reviews. Approval is not deployment.</p></section>', '<section class="panel"><form method="get" action="/evolutionary-core"><label>Workspace<select name="w">'+options+'</select></label><button>Switch</button></form></section>', '<section class="panel"><h2>Release overview</h2><p>'+str(len(releases))+' recent releases · '+str(sum(r[3]=='approved' for r in releases))+' approved · '+str(sum(r[3] not in ('approved','rejected') for r in releases))+' awaiting review</p><p><a href="/horizon?w='+esc(wid)+'">Horizon improvements</a> · <a href="/sovereign-core?w='+esc(wid)+'">Readiness checks</a></p></section>']
 if message:out.append('<section class="panel"><p>'+esc(message)+'</p></section>')
 if role in ('owner','editor') and plans:
  p_opts=''.join('<option value="'+esc(p[0])+'">'+esc(p[1])+' ('+esc(p[2])+')</option>' for p in plans)
  out.append('<section class="panel"><h2>Create a release candidate</h2><form method="post" action="/evolutionary-core"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="create"><label>Improvement plan<select name="plan">'+p_opts+'</select></label><label>Release title<input name="title" minlength="5" maxlength="120" required></label><label>Version identifier<input name="version" maxlength="60" required placeholder="e.g. 33.0-rc1"></label><button>Create candidate</button></form></section>')
 for rid,title,version,status,result,notes,review_note,issue_title,plan_status in releases:
  out.append('<section class="panel"><h3>'+esc(title)+'</h3><p>Version: '+esc(version)+' · Status: '+esc(status)+' · Test: '+esc(result)+'</p><p>Linked issue: '+esc(issue_title)+' · Horizon: '+esc(plan_status)+'</p>')
  if notes:out.append('<p>Test evidence: '+esc(notes)+'</p>')
  if review_note:out.append('<p>Owner decision: '+esc(review_note)+'</p>')
  if status not in ('approved','rejected') and role in ('owner','editor'):
   out.append('<form method="post" action="/evolutionary-core"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="release" value="'+esc(rid)+'"><input type="hidden" name="action" value="test"><label>Test outcome<select name="result"><option value="passed">Passed</option><option value="failed">Failed</option></select></label><label>Test evidence<textarea name="notes" minlength="10" maxlength="3000" required></textarea></label><button>Record test evidence</button></form>')
  if status not in ('approved','rejected') and role=='owner':
   out.append('<form method="post" action="/evolutionary-core"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="release" value="'+esc(rid)+'"><input type="hidden" name="action" value="review"><label>Decision<select name="decision"><option value="approved">Approve</option><option value="rejected">Reject</option></select></label><label>Review rationale<textarea name="note" minlength="10" maxlength="2000" required></textarea></label><button>Submit owner review</button></form>')
  out.append('</section>')
 if not plans:out.append('<section class="panel"><p>Create a Horizon improvement plan to start release review.</p></section>')
 out.append('<section class="panel"><h2>Important limitations</h2><p>Test results are human-entered, not independently verified by this page. Approval does not deploy, run code, or certify production security. Use V30 readiness checks and independent testing before customer releases.</p></section>')
 return ''.join(out)
