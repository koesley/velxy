"""V32 Horizon: local pilot improvement plans and measurable, human-entered outcomes."""
import html, secrets, time
import empire_v19

def esc(x): return html.escape(str(x),quote=True)
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS horizon_plans(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,issue_id TEXT NOT NULL,created_by INTEGER NOT NULL,priority TEXT NOT NULL CHECK(priority IN ('low','medium','high','critical')),status TEXT NOT NULL CHECK(status IN ('planned','in_progress','verified')),owner_note TEXT NOT NULL,success_metric TEXT NOT NULL,baseline REAL,target REAL,result REAL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
 c.execute('CREATE INDEX IF NOT EXISTS horizon_workspace ON horizon_plans(workspace_id,created)')
def access(c,uid,wid,write=False):
 role=empire_v19.role(c,uid,wid)
 if not role or (write and role not in ('owner','editor')):raise ValueError('Workspace unavailable or insufficient permission')
 return role
def issue(c,wid,iid):
 if not c.execute('SELECT 1 FROM first_contact_issues WHERE id=? AND workspace_id=?',(iid,wid)).fetchone():raise ValueError('Pilot issue unavailable')
def numeric(v):
 if v is None or str(v).strip()=='':return None
 import math
 try: n=float(v)
 except (ValueError,TypeError):raise ValueError('Metric values must be numbers')
 if not math.isfinite(n) or abs(n)>1e12:raise ValueError('Metric value outside supported range')
 return n
def create(c,uid,wid,iid,priority,note,metric,baseline='',target=''):
 access(c,uid,wid,True);issue(c,wid,iid)
 note=note.strip();metric=metric.strip()
 if priority not in ('low','medium','high','critical'):raise ValueError('Invalid priority')
 if not 10<=len(note)<=2000 or not 5<=len(metric)<=120:raise ValueError('Plan 10–2000 and metric 5–120 characters required')
 base=numeric(baseline);goal=numeric(target)
 if (base is None)!=(goal is None):raise ValueError('Provide both baseline and target, or neither')
 if c.execute('SELECT 1 FROM horizon_plans WHERE workspace_id=? AND issue_id=?',(wid,iid)).fetchone():raise ValueError('An improvement plan already exists for this issue')
 pid=secrets.token_hex(12);now=int(time.time())
 c.execute('INSERT INTO horizon_plans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,wid,iid,uid,priority,'planned',note,metric,base,goal,None,now,now))
 return pid
def update(c,uid,wid,pid,status,result=''):
 access(c,uid,wid,True)
 if status not in ('planned','in_progress','verified'):raise ValueError('Invalid status')
 row=c.execute('SELECT baseline,target FROM horizon_plans WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
 if not row:raise ValueError('Plan unavailable')
 value=numeric(result)
 if status=='verified' and (row[0] is None or row[1] is None or value is None):raise ValueError('Verification requires baseline, target, and measured result')
 c.execute('UPDATE horizon_plans SET status=?,result=?,updated=? WHERE id=? AND workspace_id=?',(status,value,int(time.time()),pid,wid))
def render(c,uid,csrf,wid='',message=''):
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<section class="panel"><h1>Horizon V32</h1><p>Create a workspace in Empire first.</p></section>'
 if not wid:wid=ws[0][0]
 role=access(c,uid,wid)
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
 issues=c.execute('SELECT id,title,severity,status FROM first_contact_issues WHERE workspace_id=? ORDER BY created DESC LIMIT 200',(wid,)).fetchall()
 plans=c.execute("""SELECT p.id,i.title,p.priority,p.status,p.owner_note,p.success_metric,p.baseline,p.target,p.result FROM horizon_plans p JOIN first_contact_issues i ON i.id=p.issue_id AND i.workspace_id=p.workspace_id WHERE p.workspace_id=? ORDER BY CASE p.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,p.created DESC LIMIT 200""",(wid,)).fetchall()
 out=['<section class="hero"><p class="eyebrow">VELXTRIA V32 · PROJECT HORIZON</p><h1>Turn pilot problems into measurable improvements.</h1><p>Prioritize fixes, document success criteria, and track human-verified outcomes. No automated deployment or claimed causal impact.</p></section>', '<section class="panel"><form method="get" action="/horizon"><label>Workspace<select name="w">'+options+'</select></label><button>Switch</button></form></section>', '<section class="panel"><h2>Improvement overview</h2><p>'+str(len(plans))+' plans · '+str(sum(p[3]!='verified' for p in plans))+' pending · '+str(sum(p[3]=='verified' for p in plans))+' verified</p><p><a href="/first-contact?w='+esc(wid)+'">Pilot issues</a> · <a href="/launchpad?w='+esc(wid)+'">Pilot feedback</a></p></section>']
 if message:out.append('<section class="panel"><p>'+esc(message)+'</p></section>')
 planned={r[0] for r in c.execute('SELECT issue_id FROM horizon_plans WHERE workspace_id=?',(wid,)).fetchall()}
 available=[i for i in issues if i[0] not in planned]
 if role in ('owner','editor') and available:
  issueopts=''.join('<option value="'+esc(i[0])+'">'+esc(i[1])+' ('+esc(i[2])+')</option>' for i in available)
  out.append('<section class="panel"><h2>Plan an improvement</h2><form method="post" action="/horizon"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="create"><label>Pilot issue<select name="issue">'+issueopts+'</select></label><label>Priority<select name="priority"><option>low</option><option>medium</option><option selected>high</option><option>critical</option></select></label><label>Proposed fix<textarea name="note" minlength="10" maxlength="2000" required></textarea></label><label>Success metric<input name="metric" minlength="5" maxlength="120" placeholder="e.g. errors per 100 runs" required></label><label>Baseline (optional)<input name="baseline" type="number" step="any"></label><label>Target (optional)<input name="target" type="number" step="any"></label><button>Create improvement plan</button></form></section>')
 for pid,title,priority,status,note,metric,base,target,result in plans:
  out.append('<section class="panel"><h3>'+esc(title)+'</h3><p>Priority: '+esc(priority)+' · Status: '+esc(status)+'</p><p>'+esc(note)+'</p><p>Metric: '+esc(metric)+' · Baseline: '+esc(base if base is not None else 'not set')+' · Target: '+esc(target if target is not None else 'not set')+' · Result: '+esc(result if result is not None else 'not measured')+'</p>')
  if role in ('owner','editor'):
   out.append('<form method="post" action="/horizon"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="plan" value="'+esc(pid)+'"><input type="hidden" name="action" value="update"><label>Status<select name="status">'+''.join('<option value="'+s+'"'+(' selected' if s==status else '')+'>'+s.replace('_',' ')+'</option>' for s in ('planned','in_progress','verified'))+'</select></label><label>Measured result (required to verify)<input name="result" type="number" step="any" value="'+esc(result if result is not None else '')+'"></label><button>Update status</button></form>')
  out.append('</section>')
 if not issues:out.append('<section class="panel"><p>Record a pilot issue in First Contact to begin.</p></section>')
 out.append('<section class="panel"><h2>Measurement limitations</h2><p>Metrics and results are manually entered, not independently validated. A verified status records a reviewer decision, not proof the fix caused an improvement. Local studio only.</p></section>')
 return ''.join(out)
