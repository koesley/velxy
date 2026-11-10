"""Omniverse local foundation: durable internal job ledger, events, capability catalog.
No background daemon, arbitrary code execution, external side effects, or automatic spending.
"""
import html,json,secrets,time,datetime,sqlite3,urllib.parse
import sovereign_v56 as core
KINDS={"workspace_health":"Check the workspace data footprint","workflow_readiness":"Inspect approved workflow readiness","guardian_summary":"Summarize Guardian alert counts","graph_readiness":"Inspect Living Business Graph evidence and relationships"}
MAX_ATTEMPTS=3

def init(c):
 core.setup(c)
 c.execute("CREATE TABLE IF NOT EXISTS ov57_events(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,kind TEXT NOT NULL,object_id TEXT NOT NULL,payload TEXT NOT NULL,created INTEGER NOT NULL)")
 c.execute("CREATE INDEX IF NOT EXISTS ov57_events_scope ON ov57_events(workspace_id,created)")
 c.execute("CREATE TABLE IF NOT EXISTS ov57_jobs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('queued','running','done','failed','cancelled')),scheduled_at INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,lease_until INTEGER NOT NULL DEFAULT 0,idempotency_key TEXT NOT NULL,result TEXT NOT NULL DEFAULT '',last_error TEXT NOT NULL DEFAULT '',created_by INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(workspace_id,idempotency_key))")
 c.execute("CREATE INDEX IF NOT EXISTS ov57_jobs_due ON ov57_jobs(workspace_id,status,scheduled_at)")

def emit(c,wid,kind,oid,payload=None):
 c.execute('INSERT INTO ov57_events VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wid,kind,oid,json.dumps(payload or {},sort_keys=True),int(time.time())))

def enqueue(c,uid,wid,kind,key,scheduled_at=None):
 core.access(c,uid,wid,write=True);init(c)
 if kind not in KINDS:raise ValueError('Unsupported job capability')
 if not isinstance(key,str) or not 8<=len(key)<=100 or any(ord(ch)<32 for ch in key):raise ValueError('Provide an idempotency key (8–100 characters)')
 now=int(time.time());scheduled_at=now if scheduled_at is None else int(scheduled_at)
 if scheduled_at<now-60 or scheduled_at>now+366*86400:raise ValueError('Schedule must be within the next year')
 with c:
  row=c.execute('SELECT id,kind FROM ov57_jobs WHERE workspace_id=? AND idempotency_key=?',(wid,key)).fetchone()
  if row:
   if row[1]!=kind:raise ValueError('Idempotency key already used for a different capability')
   return row[0]
  jid=secrets.token_hex(12)
  c.execute('INSERT INTO ov57_jobs(id,workspace_id,kind,status,scheduled_at,idempotency_key,created_by,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(jid,wid,kind,'queued',scheduled_at,key,uid,now,now))
  emit(c,wid,'job_queued',jid,{'kind':kind});core.audit(c,uid,wid,'omni_job_queued',jid)
  return jid

def cancel(c,uid,wid,jid):
 core.access(c,uid,wid,write=True);init(c)
 with c:
  r=c.execute("UPDATE ov57_jobs SET status='cancelled',updated=? WHERE id=? AND workspace_id=? AND status='queued'",(int(time.time()),jid,wid))
  if r.rowcount!=1:raise ValueError('Only queued jobs can be cancelled')
  emit(c,wid,'job_cancelled',jid);core.audit(c,uid,wid,'omni_job_cancelled',jid)

def _internal_result(c,wid,kind):
 if kind=='workspace_health':
  return {'metric_periods':c.execute('SELECT COUNT(*) FROM sv56_metrics WHERE workspace_id=?',(wid,)).fetchone()[0],'imports':c.execute('SELECT COUNT(*) FROM sv56_imports WHERE workspace_id=?',(wid,)).fetchone()[0]}
 if kind=='workflow_readiness':
  import sovereign_workflows_v56 as wf
  wf.init(c)
  return {'approved_workflows':c.execute("SELECT COUNT(*) FROM sv56_workflows WHERE workspace_id=? AND status='approved'",(wid,)).fetchone()[0]}
 if kind=='graph_readiness':
  import sovereign_business_graph_v57 as graph
  graph.init(c)
  return {'entities':c.execute('SELECT COUNT(*) FROM ov57_graph_nodes WHERE workspace_id=? AND archived=0',(wid,)).fetchone()[0],'relationships':c.execute('SELECT COUNT(*) FROM ov57_graph_edges WHERE workspace_id=? AND archived=0',(wid,)).fetchone()[0],'hypotheses':c.execute("SELECT COUNT(*) FROM ov57_graph_nodes WHERE workspace_id=? AND archived=0 AND confidence='hypothesis'",(wid,)).fetchone()[0]}
 if kind=='guardian_summary':
  import sovereign_guardian_v56 as guardian
  guardian.setup(c)
  return {'alerts':c.execute('SELECT COUNT(*) FROM sv56_guardian_alerts WHERE workspace_id=?',(wid,)).fetchone()[0]}
 raise ValueError('Unknown internal capability')

def run_one(c,uid,wid,jid,now=None):
 """Explicitly user-invoked dispatch. No automatic external side effects."""
 core.access(c,uid,wid,write=True);init(c);now=int(time.time()) if now is None else int(now)
 with c:
  r=c.execute('SELECT kind,status,scheduled_at,attempts FROM ov57_jobs WHERE workspace_id=? AND id=?',(wid,jid)).fetchone()
  if not r:raise ValueError('Job not found')
  kind,status,due,attempts=r
  if status!='queued' or due>now:raise ValueError('Job is not queued and due')
  if attempts>=MAX_ATTEMPTS:raise ValueError('Retry limit reached')
  updated=c.execute("UPDATE ov57_jobs SET status='running',attempts=attempts+1,lease_until=?,updated=? WHERE id=? AND workspace_id=? AND status='queued'",(now+120,now,jid,wid))
  if updated.rowcount!=1:raise ValueError('Job already claimed')
  emit(c,wid,'job_started',jid,{'attempt':attempts+1})
 try:
  result=_internal_result(c,wid,kind)
 except Exception as exc:
  with c:
   c.execute("UPDATE ov57_jobs SET status='failed',last_error=?,lease_until=0,updated=? WHERE id=? AND workspace_id=?",(type(exc).__name__,now,jid,wid))
   emit(c,wid,'job_failed',jid,{'error_type':type(exc).__name__})
  raise ValueError('Internal job failed') from exc
 with c:
  c.execute("UPDATE ov57_jobs SET status='done',result=?,lease_until=0,updated=? WHERE id=? AND workspace_id=?",(json.dumps(result,sort_keys=True),now,jid,wid))
  emit(c,wid,'job_completed',jid);core.audit(c,uid,wid,'omni_job_completed',jid)
 return result

def recover(c,uid,wid,jid,now=None):
 core.access(c,uid,wid,owner=True);init(c);now=int(time.time()) if now is None else int(now)
 with c:
  r=c.execute('SELECT status,attempts,lease_until FROM ov57_jobs WHERE workspace_id=? AND id=?',(wid,jid)).fetchone()
  if not r or r[1]>=MAX_ATTEMPTS or not (r[0]=='failed' or (r[0]=='running' and r[2]<now)):raise ValueError('Job is not recoverable')
  c.execute("UPDATE ov57_jobs SET status='queued',scheduled_at=?,lease_until=0,updated=? WHERE workspace_id=? AND id=?",(now,now,wid,jid))
  emit(c,wid,'job_requeued',jid);core.audit(c,uid,wid,'omni_job_requeued',jid)

def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 jobs=[dict(zip(('id','kind','status','scheduled_at','attempts','result','last_error'),r)) for r in c.execute('SELECT id,kind,status,scheduled_at,attempts,result,last_error FROM ov57_jobs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 events=[dict(zip(('kind','object_id','created'),r)) for r in c.execute('SELECT kind,object_id,created FROM ov57_events WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 40',(wid,))]
 return {'workspace_id':wid,'role':role,'capabilities':[{'key':k,'label':v,'mode':'local_read_only'} for k,v in KINDS.items()],'jobs':jobs,'events':events,'counts':{s:sum(j['status']==s for j in jobs) for s in ('queued','running','done','failed','cancelled')},'limitations':['Manual dispatch only; no background scheduler.','Only allowlisted local read-only capabilities; no arbitrary execution.','A running job can require owner recovery after a crash.']}

def render(c,uid,wid,csrf):
 d=overview(c,uid,wid);h=lambda x:html.escape(str(x),quote=True)
 action='/sovereign-omniverse-v57';hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
 cards=''.join('<article class="ov-card"><strong>'+h(k.title())+'</strong><span>'+str(v)+'</span></article>' for k,v in d['counts'].items())
 cap=''.join('<option value="'+h(k)+'">'+h(v)+'</option>' for k,v in KINDS.items())
 create=('<section class="ov-panel"><h2>Queue an internal capability</h2><form method="post" action="'+action+'">'+hidden+'<label>Capability<select name="kind">'+cap+'</select></label><label>Unique request key<input name="key" minlength="8" maxlength="100" required placeholder="e.g. health-review-001"></label><button name="action" value="enqueue">Queue job</button></form></section>') if d['role'] in ('owner','editor') else ''
 rows=[]
 for j in d['jobs']:
  actions=''
  if d['role'] in ('owner','editor') and j['status']=='queued':
   for act,label in (('run','Run now'),('cancel','Cancel')):
    actions+='<form method="post" action="'+action+'">'+hidden+'<input type="hidden" name="job" value="'+h(j['id'])+'"><button name="action" value="'+act+'">'+label+'</button></form>'
  if d['role']=='owner' and j['status'] in ('failed','running') and j['attempts']<MAX_ATTEMPTS:
   actions+='<form method="post" action="'+action+'">'+hidden+'<input type="hidden" name="job" value="'+h(j['id'])+'"><button name="action" value="recover">Recover (if eligible)</button></form>'
  rows.append('<article class="ov-job"><div><strong>'+h(KINDS.get(j['kind'],j['kind']))+'</strong><small>'+h(j['status'])+' · attempts '+str(j['attempts'])+'/'+str(MAX_ATTEMPTS)+'</small></div><code>'+h(j['result'] or j['last_error'] or 'Awaiting execution')+'</code><div class="ov-actions">'+actions+'</div></article>')
 events=''.join('<li><b>'+h(e['kind'].replace('_',' '))+'</b> · '+h(e['object_id'][:10])+'</li>' for e in d['events'])
 return '<section class="ov-hero"><span>VELXTRIA · PROJECT OMNIVERSE</span><h1>Build the foundation for what comes next.</h1><p>Durable job ledger, workspace events, allowlisted capabilities, and controlled recovery. Designed for safe expansion.</p><p><a href="/sovereign-business-graph-v57">Explore the Living Business Graph →</a></p></section><section class="ov-metrics">'+cards+'</section><div class="ov-layout"><main>'+create+'<section class="ov-panel"><h2>Job control</h2>'+(''.join(rows) or '<p>No jobs queued yet.</p>')+'</section></main><aside class="ov-panel"><h2>Event timeline</h2><ul>'+events+'</ul><h3>Safety boundaries</h3><p>Jobs are manually dispatched, local, and read-only. No background worker, external actions, or AI provider is enabled.</p></aside></div>'
