"""V57.3 Investigation Council: deterministic, evidence-limited human-reviewed investigations."""
import html,json,secrets,time
import sovereign_v56 as core
import sovereign_business_graph_v57 as graph
ROLES=('finance','operations','growth','risk')
QUESTIONS={'finance':'What financial exposure could affect this entity?','operations':'Which dependencies could interrupt operations?','growth':'What customer or channel assumptions require validation?','risk':'What unverified assumptions could make this decision unsafe?'}
def init(c):
 graph.init(c)
 c.execute('CREATE TABLE IF NOT EXISTS ov57_investigations(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,node_id TEXT NOT NULL,question TEXT NOT NULL,status TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,reviewed_by INTEGER,review_note TEXT NOT NULL DEFAULT "")')
 c.execute('CREATE INDEX IF NOT EXISTS ov57_investigations_scope ON ov57_investigations(workspace_id,created)')
 c.execute('CREATE TABLE IF NOT EXISTS ov57_investigation_notes(id TEXT PRIMARY KEY,investigation_id TEXT NOT NULL,workspace_id TEXT NOT NULL,role TEXT NOT NULL,position TEXT NOT NULL,statement TEXT NOT NULL,evidence TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS ov57_investigation_notes_scope ON ov57_investigation_notes(workspace_id,investigation_id)')
def valid(s,n=500):
 if not isinstance(s,str) or not s.strip() or len(s.strip())>n or any(ord(x)<32 and x not in '\n\t' for x in s):raise ValueError('Invalid text')
 return s.strip()
def create(c,uid,wid,node_id,question):
 core.access(c,uid,wid,write=True);init(c);question=valid(question,400)
 n=c.execute('SELECT id FROM ov57_graph_nodes WHERE workspace_id=? AND id=? AND archived=0',(wid,node_id)).fetchone()
 if not n:raise ValueError('Entity not found in workspace')
 iid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO ov57_investigations(id,workspace_id,node_id,question,status,created_by,created) VALUES(?,?,?,?,?,?,?)',(iid,wid,node_id,question,'open',uid,int(time.time())))
  core.audit(c,uid,wid,'investigation_created',iid)
 return iid
def note(c,uid,wid,iid,role,position,statement,evidence):
 core.access(c,uid,wid,write=True);init(c)
 if role not in ROLES or position not in ('hypothesis','challenge','evidence','recommendation'):raise ValueError('Invalid council classification')
 statement=valid(statement,800);evidence=valid(evidence,500)
 with c:
  row=c.execute('SELECT status FROM ov57_investigations WHERE id=? AND workspace_id=?',(iid,wid)).fetchone()
  if not row or row[0]!='open':raise ValueError('Investigation not open')
  nid=secrets.token_hex(12)
  c.execute('INSERT INTO ov57_investigation_notes VALUES(?,?,?,?,?,?,?,?,?)',(nid,iid,wid,role,position,statement,evidence,uid,int(time.time())))
  core.audit(c,uid,wid,'investigation_note_added',iid)
 return nid
def review(c,uid,wid,iid,decision,reason):
 core.access(c,uid,wid,write=True,owner=True);init(c)
 if decision not in ('accepted','needs_evidence','closed'):raise ValueError('Invalid decision')
 reason=valid(reason,800)
 with c:
  row=c.execute('SELECT status FROM ov57_investigations WHERE id=? AND workspace_id=?',(iid,wid)).fetchone()
  if not row or row[0]!='open':raise ValueError('Investigation not open')
  c.execute('UPDATE ov57_investigations SET status=?,reviewed_by=?,review_note=? WHERE id=? AND workspace_id=?',(decision,uid,reason,iid,wid))
  core.audit(c,uid,wid,'investigation_reviewed',iid)
def generate(c,uid,wid,iid):
 """Deterministic prompts, never pretend an AI agent or verification ran."""
 core.access(c,uid,wid,write=True);init(c)
 row=c.execute('SELECT i.node_id,i.status,n.name,n.confidence,n.source FROM ov57_investigations i JOIN ov57_graph_nodes n ON n.id=i.node_id AND n.workspace_id=i.workspace_id WHERE i.id=? AND i.workspace_id=? AND n.archived=0',(iid,wid)).fetchone()
 if not row or row[1]!='open':raise ValueError('Investigation unavailable')
 edges=c.execute('SELECT relation FROM ov57_graph_edges WHERE workspace_id=? AND archived=0 AND (source_id=? OR target_id=?)',(wid,row[0],row[0])).fetchall()
 statements=[('finance','hypothesis','Check whether this entity has measurable cost, revenue, or cash-flow exposure.'),('operations','challenge','Review dependency resilience; '+str(len(edges))+' manually recorded relationship(s) are visible.'),('growth','hypothesis','Test whether customer demand or channel performance supports expansion.'),('risk','challenge','Evidence status is '+row[3]+'; source reference: '+row[4]+'. Independent verification is required.')]
 with c:
  for role,pos,stmt in statements:
   exists=c.execute('SELECT 1 FROM ov57_investigation_notes WHERE workspace_id=? AND investigation_id=? AND role=? AND position=? AND created_by=0',(wid,iid,role,pos)).fetchone()
   if not exists:c.execute('INSERT INTO ov57_investigation_notes VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(12),iid,wid,role,pos,stmt,'System-generated question; not a verified finding',0,int(time.time())))
  core.audit(c,uid,wid,'investigation_prompts_generated',iid)
def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 nodes=c.execute('SELECT id,name,confidence FROM ov57_graph_nodes WHERE workspace_id=? AND archived=0 ORDER BY created DESC LIMIT 250',(wid,)).fetchall()
 cases=[dict(zip(('id','node_id','question','status','created','review_note'),r)) for r in c.execute('SELECT id,node_id,question,status,created,review_note FROM ov57_investigations WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 for case in cases:
  case['notes']=[dict(zip(('role','position','statement','evidence'),r)) for r in c.execute('SELECT role,position,statement,evidence FROM ov57_investigation_notes WHERE workspace_id=? AND investigation_id=? ORDER BY created,id LIMIT 100',(wid,case['id']))]
  case['evidence_gaps']=['No source-backed measurements recorded'] if not any(n['position']=='evidence' for n in case['notes']) else []
 return {'workspace_id':wid,'role':role,'nodes':[{'id':x[0],'name':x[1],'confidence':x[2]} for x in nodes],'investigations':cases,'counts':{'total':len(cases),'open':sum(x['status']=='open' for x in cases),'needs_evidence':sum(x['status']=='needs_evidence' for x in cases)},'limitations':['Generated council prompts are deterministic questions, not AI agent findings.','Manual evidence entries are not independently validated.','Review does not execute any business action.']}
def render(c,uid,wid,csrf):
 d=overview(c,uid,wid);h=lambda s:html.escape(str(s),quote=True);url='/sovereign-council-v57';hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
 options=''.join('<option value="'+h(n['id'])+'">'+h(n['name'])+' · '+h(n['confidence'])+'</option>' for n in d['nodes'])
 out=['<section class="ov-hero"><span>PROJECT OMNIVERSE · INTELLIGENCE COUNCIL</span><h1>Investigate before you act.</h1><p>Challenge assumptions, document competing explanations, and require owner review before treating an investigation as accepted.</p><a href="/sovereign-business-graph-v57?w='+h(wid)+'">Business Graph</a></section>']
 out.append('<section class="ov-metrics">'+''.join('<article class="ov-card"><strong>'+h(k.replace('_',' ').title())+'</strong><span>'+str(v)+'</span></article>' for k,v in d['counts'].items())+'</section>')
 if d['role'] in ('owner','editor'):
  out.append('<section class="ov-panel"><h2>Start an investigation</h2><form method="post" action="'+url+'">'+hidden+'<label>Business entity<select name="node_id">'+options+'</select></label><label>Question<input name="question" maxlength="400" required placeholder="What assumption should we investigate?"></label><button name="action" value="create">Create investigation</button></form></section>')
 for x in d['investigations']:
  out.append('<section class="ov-panel" style="margin-top:18px"><h2>'+h(x['question'])+'</h2><p>Status: <strong>'+h(x['status'])+'</strong></p>')
  for n in x['notes']:out.append('<article class="ov-job"><strong>'+h(n['role'].title())+' · '+h(n['position'])+'</strong><p>'+h(n['statement'])+'</p><small>'+h(n['evidence'])+'</small></article>')
  if x['evidence_gaps']:out.append('<p>Evidence gap: '+h(', '.join(x['evidence_gaps']))+'</p>')
  if x['status']=='open' and d['role'] in ('owner','editor'):
   out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="case" value="'+h(x['id'])+'"><button name="action" value="generate">Generate council questions</button></form>')
   out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="case" value="'+h(x['id'])+'"><label>Perspective<select name="role">'+''.join('<option>'+r+'</option>' for r in ROLES)+'</select></label><label>Entry type<select name="position"><option>hypothesis</option><option>challenge</option><option>evidence</option><option>recommendation</option></select></label><label>Statement<input name="statement" maxlength="800" required></label><label>Evidence reference / limitations<input name="evidence" maxlength="500" required></label><button name="action" value="note">Add council entry</button></form>')
  if x['status']=='open' and d['role']=='owner':
   out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="case" value="'+h(x['id'])+'"><label>Owner decision<select name="decision"><option>needs_evidence</option><option>accepted</option><option>closed</option></select></label><label>Reason<input name="reason" maxlength="800" required></label><button name="action" value="review">Record decision</button></form>')
  if x['review_note']:out.append('<p>Owner review: '+h(x['review_note'])+'</p>')
  out.append('</section>')
 out.append('<section class="ov-panel"><p>Deterministic investigation prompts only. No external actions, automatic business changes, or verified financial conclusions.</p></section>')
 return ''.join(out)
