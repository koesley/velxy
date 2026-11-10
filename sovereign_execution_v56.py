"""Milestone 7: workspace-scoped, approval-gated, internal-only execution."""
import html, json, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_strategy_v56 as strategy

ACTIONS={'create_review_task':'Create internal strategy review task'}

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_exec_policy(workspace_id TEXT PRIMARY KEY,paused INTEGER NOT NULL DEFAULT 0 CHECK(paused IN (0,1)),updated INTEGER NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_exec_jobs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,strategy_id TEXT NOT NULL,scenario_code TEXT NOT NULL,action_type TEXT NOT NULL,idempotency_key TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('proposed','approved','queued','running','succeeded','failed','rejected','cancelled','expired')),created_by INTEGER NOT NULL,approved_by INTEGER,created INTEGER NOT NULL,updated INTEGER NOT NULL,expires INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),lease_until INTEGER,details TEXT NOT NULL DEFAULT '',UNIQUE(workspace_id,idempotency_key))''')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_exec_tasks(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,job_id TEXT NOT NULL UNIQUE,title TEXT NOT NULL,created INTEGER NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_exec_events(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id TEXT NOT NULL,job_id TEXT,actor INTEGER NOT NULL,event TEXT NOT NULL,created INTEGER NOT NULL,details TEXT NOT NULL DEFAULT '')''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_exec_scope ON sv56_exec_jobs(workspace_id,created)')

def event(c,wid,job,actor,name,details=''):
 c.execute('INSERT INTO sv56_exec_events(workspace_id,job_id,actor,event,created,details) VALUES(?,?,?,?,?,?)',(wid,job,actor,name,int(time.time()),str(details)[:500]))

def paused(c,wid):
 row=c.execute('SELECT paused FROM sv56_exec_policy WHERE workspace_id=?',(wid,)).fetchone()
 return bool(row and row[0])

def set_pause(c,uid,wid,value):
 core.access(c,uid,wid,owner=True)
 with c:
  c.execute('INSERT INTO sv56_exec_policy(workspace_id,paused,updated) VALUES(?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET paused=excluded.paused,updated=excluded.updated',(wid,int(bool(value)),int(time.time())))
  event(c,wid,None,uid,'emergency_pause' if value else 'emergency_resume')

def propose(c,uid,wid,strategy_id,scenario_code,idempotency_key,ttl=86400):
 core.access(c,uid,wid,write=True)
 if not 8<=len(idempotency_key)<=128 or not idempotency_key.isascii() or not all(x.isalnum() or x in '-_:' for x in idempotency_key):raise ValueError('Invalid idempotency key')
 if not isinstance(ttl,int) or not 60<=ttl<=604800:raise ValueError('Invalid approval expiry')
 existing=c.execute('SELECT id,strategy_id,scenario_code FROM sv56_exec_jobs WHERE workspace_id=? AND idempotency_key=?',(wid,idempotency_key)).fetchone()
 if existing:
  if existing[1:]!=(strategy_id,scenario_code):raise ValueError('Idempotency key already used for a different request')
  return existing[0]
 row=c.execute('SELECT opportunity_key,result_json FROM sv56_strategy_runs WHERE id=? AND workspace_id=?',(strategy_id,wid)).fetchone()
 if not row:raise ValueError('Strategy not found')
 record=json.loads(row[1]);valid={s['code'] for s in record['scenarios']}
 if scenario_code not in valid:raise ValueError('Unknown scenario')
 current={r['id']:r for r in strategy.history(c,uid,wid)}
 if strategy_id not in current or current[strategy_id]['stale']:raise ValueError('Strategy evidence is stale')
 now=int(time.time());jid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_exec_jobs(id,workspace_id,strategy_id,scenario_code,action_type,idempotency_key,status,created_by,created,updated,expires) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(jid,wid,strategy_id,scenario_code,'create_review_task',idempotency_key,'proposed',uid,now,now,now+ttl))
  event(c,wid,jid,uid,'proposed',scenario_code)
 return jid

def change(c,uid,wid,jid,operation):
 core.access(c,uid,wid,owner=True)
 row=c.execute('SELECT status,expires,strategy_id FROM sv56_exec_jobs WHERE id=? AND workspace_id=?',(jid,wid)).fetchone()
 if not row:raise ValueError('Job not found')
 status,expires,sid=row
 allowed={'approve':('proposed','approved'),'reject':('proposed','rejected'),'queue':('approved','queued'),'cancel':('proposed','cancelled')}
 if operation not in allowed:raise ValueError('Invalid transition')
 source,target=allowed[operation]
 if status!=source:raise ValueError('Invalid execution state transition')
 if operation in ('approve','queue'):
  if paused(c,wid):raise ValueError('Emergency stop is active')
  if int(time.time())>=expires:raise ValueError('Approval expired')
  if next((r for r in strategy.history(c,uid,wid) if r['id']==sid),{'stale':True})['stale']:raise ValueError('Strategy evidence is stale')
 with c:
  c.execute('UPDATE sv56_exec_jobs SET status=?,approved_by=CASE WHEN ?="approve" THEN ? ELSE approved_by END,updated=? WHERE id=? AND workspace_id=? AND status=?',(target,operation,uid,int(time.time()),jid,wid,source))
  event(c,wid,jid,uid,operation)

def dispatch_one(c,uid,wid):
 """Owner-invoked synchronous internal action; no external effects or unbounded worker."""
 core.access(c,uid,wid,owner=True)
 if paused(c,wid):raise ValueError('Emergency stop is active')
 row=c.execute("SELECT id,strategy_id,scenario_code,expires FROM sv56_exec_jobs WHERE workspace_id=? AND status='queued' ORDER BY created,id LIMIT 1",(wid,)).fetchone()
 if not row:return None
 jid,sid,code,expires=row;now=int(time.time())
 if now>=expires:
  with c:
   c.execute("UPDATE sv56_exec_jobs SET status='expired',updated=? WHERE id=? AND status='queued'",(now,jid));event(c,wid,jid,uid,'expired')
  return jid
 if next((r for r in strategy.history(c,uid,wid) if r['id']==sid),{'stale':True})['stale']:
  with c:
   c.execute("UPDATE sv56_exec_jobs SET status='failed',details='Strategy evidence changed',updated=? WHERE id=? AND status='queued'",(now,jid));event(c,wid,jid,uid,'failed','stale evidence')
  return jid
 # Single SQLite transaction prevents duplicate task creation across competing dispatchers.
 with c:
  if paused(c,wid):raise ValueError('Emergency stop is active')
  claimed=c.execute("UPDATE sv56_exec_jobs SET status='running',attempts=attempts+1,lease_until=?,updated=? WHERE id=? AND workspace_id=? AND status='queued' AND attempts<3",(now+30,now,jid,wid)).rowcount
  if not claimed:return None
  event(c,wid,jid,uid,'running')
  c.execute('INSERT OR IGNORE INTO sv56_exec_tasks(id,workspace_id,job_id,title,created) VALUES(?,?,?,?,?)',(secrets.token_hex(12),wid,jid,'Review strategy '+sid+' / '+code,now))
  c.execute("UPDATE sv56_exec_jobs SET status='succeeded',details='Internal review task created',lease_until=NULL,updated=? WHERE id=? AND status='running'",(now,jid))
  event(c,wid,jid,uid,'succeeded','internal task')
 return jid

def history(c,uid,wid):
 core.access(c,uid,wid)
 jobs=[dict(zip(('id','strategy_id','scenario_code','action_type','status','created','expires','attempts','details'),r)) for r in c.execute('SELECT id,strategy_id,scenario_code,action_type,status,created,expires,attempts,details FROM sv56_exec_jobs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 tasks=[dict(zip(('id','job_id','title'),r)) for r in c.execute('SELECT id,job_id,title FROM sv56_exec_tasks WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,))]
 events=[dict(zip(('job_id','actor','event','created','details'),r)) for r in c.execute('SELECT job_id,actor,event,created,details FROM sv56_exec_events WHERE workspace_id=? ORDER BY id DESC LIMIT 150',(wid,))]
 return {'paused':paused(c,wid),'jobs':jobs,'tasks':tasks,'events':events,'allowed_actions':ACTIONS,'external_execution':False}

def render(c,uid,csrf,wid):
 core.access(c,uid,wid)
 e=lambda x:html.escape(str(x),quote=True)
 h=history(c,uid,wid);runs=strategy.history(c,uid,wid)
 form=lambda action,jid='':'<form method="post" action="/sovereign-execution-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="'+e(action)+'"><input type="hidden" name="job_id" value="'+e(jid)+'">'
 out=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 7</p><h1>Execution Center</h1><p>Internal review tasks only. Every action requires owner approval. No external writes, payments, or profit generation.</p><p><strong>Emergency stop: '+('ON' if h['paused'] else 'OFF')+'</strong></p>'+form('resume' if h['paused'] else 'pause')+'<button>'+('Resume dispatch' if h['paused'] else 'STOP dispatch')+'</button></form><p><a href="/sovereign-execution-v56.json?w='+quote(wid,safe='')+'">Export execution history</a></p></section>']
 out.append('<section class="panel"><h2>Propose internal task</h2>'+form('propose')+'<label>Simulation<select name="strategy_id">')
 for r in runs:
  if not r['stale']:out.append('<option value="'+e(r['id'])+'">'+e(r['id'])+'</option>')
 out.append('</select></label><label>Scenario code<input name="scenario_code" placeholder="retention_review" required></label><label>Idempotency key<input name="idempotency_key" placeholder="unique-request-001" required minlength="8" maxlength="128"></label><button>Propose review task</button></form></section>')
 out.append('<section class="panel"><h2>Queue</h2><p>Only workspace owners can approve or dispatch.</p>')
 for job in h['jobs']:
  out.append('<div class="panel"><strong>'+e(job['scenario_code'])+'</strong> · '+e(job['status'])+' · '+e(job['id'])+'<p>Strategy: '+e(job['strategy_id'])+'</p>')
  for op in ({'proposed':['approve','reject','cancel'],'approved':['queue'],'queued':[]} .get(job['status'],[])):
   out.append(form(op,job['id'])+'<button>'+e(op.title())+'</button></form>')
  out.append('</div>')
 out.append(form('dispatch')+'<button '+('disabled' if h['paused'] else '')+'>Dispatch next approved task</button></form></section>')
 out.append('<section class="panel"><h2>Created internal tasks</h2><ul>')
 for task in h['tasks']:out.append('<li>'+e(task['title'])+'</li>')
 out.append('</ul><h2>Audit events</h2><ul>')
 for ev in h['events']:out.append('<li>'+e(ev['event'])+' · '+e(ev['job_id'])+' · '+e(ev['details'])+'</li>')
 out.append('</ul></section>')
 return ''.join(out)
