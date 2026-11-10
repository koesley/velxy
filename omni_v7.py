"""V7 durable, permission-gated internal task orchestration; no external side effects."""
import html, json, secrets, time

def e(s):return html.escape(str(s),quote=True)
def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS vx7_runs(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,mission_id TEXT NOT NULL,plan_id TEXT NOT NULL,title TEXT NOT NULL,created_at INTEGER NOT NULL,status TEXT NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS vx7_tasks(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,user_id INTEGER NOT NULL,ordinal INTEGER NOT NULL,role TEXT NOT NULL,title TEXT NOT NULL,evidence TEXT NOT NULL,needs_approval INTEGER NOT NULL,status TEXT NOT NULL,approved_at INTEGER,completed_at INTEGER,completion_note TEXT NOT NULL DEFAULT '')''')
 c.execute('''CREATE TABLE IF NOT EXISTS vx7_events(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,task_id TEXT NOT NULL,user_id INTEGER NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL,created_at INTEGER NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS vx7_runs_scope ON vx7_runs(user_id,mission_id,created_at)')
 c.execute('CREATE INDEX IF NOT EXISTS vx7_tasks_scope ON vx7_tasks(user_id,run_id,ordinal)')

def log(c,uid,rid,tid,action,detail=''):
 c.execute('INSERT INTO vx7_events VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(16),rid,tid,uid,action,detail[:1200],int(time.time())))

def create(c,uid,pid):
 row=c.execute('SELECT mission_id,goal,plan_json FROM vx6_plans WHERE id=? AND user_id=?',(pid,uid)).fetchone()
 if not row:raise ValueError('Strategy not found in your account.')
 mid,goal,raw=row
 if not c.execute('SELECT 1 FROM vx52_missions WHERE id=? AND user_id=?',(mid,uid)).fetchone():raise ValueError('Mission not found.')
 existing=c.execute('SELECT id FROM vx7_runs WHERE plan_id=? AND user_id=?',(pid,uid)).fetchone()
 if existing:return existing[0]
 try:plan=json.loads(raw)
 except (ValueError,TypeError):raise ValueError('Invalid saved plan.')
 steps=plan.get('seven_day_plan',[])
 if not isinstance(steps,list) or not steps:raise ValueError('This strategy has no tasks.')
 rid=secrets.token_hex(16)
 c.execute('INSERT INTO vx7_runs VALUES(?,?,?,?,?,?,?)',(rid,uid,mid,pid,goal[:180],int(time.time()),'active'))
 for i,step in enumerate(steps[:14]):
  if not isinstance(step,dict):continue
  title=str(step.get('task','')).strip()[:900]
  if not title:continue
  tid=secrets.token_hex(16)
  # All work requires owner review; LLM cannot grant itself permission.
  c.execute('INSERT INTO vx7_tasks(id,run_id,user_id,ordinal,role,title,evidence,needs_approval,status) VALUES(?,?,?,?,?,?,?,?,?)',(tid,rid,uid,i+1,('Strategy','CRM','Verification')[i%3],title,str(step.get('evidence_needed',''))[:800],1,'blocked'))
 log(c,uid,rid,'','created','Plan imported as review-only internal tasks; no execution performed.')
 return rid

def act(c,uid,rid,tid,action,note=''):
 run=c.execute('SELECT status FROM vx7_runs WHERE id=? AND user_id=?',(rid,uid)).fetchone()
 if not run:raise ValueError('Workflow not found.')
 task=c.execute('SELECT ordinal,status FROM vx7_tasks WHERE id=? AND run_id=? AND user_id=?',(tid,rid,uid)).fetchone()
 if not task:raise ValueError('Task not found.')
 ordinal,status=task
 if action=='approve':
  if status!='blocked':raise ValueError('Only blocked tasks can be approved.')
  c.execute('UPDATE vx7_tasks SET status=?,approved_at=? WHERE id=? AND user_id=?',('approved',int(time.time()),tid,uid))
 elif action=='complete':
  if status!='approved':raise ValueError('Approve this task first.')
  if c.execute("SELECT 1 FROM vx7_tasks WHERE run_id=? AND user_id=? AND ordinal<? AND status!='completed' LIMIT 1",(rid,uid,ordinal)).fetchone():raise ValueError('Complete earlier tasks first.')
  note=note.strip()
  if len(note)<12 or len(note)>1200:raise ValueError('Add a 12–1200 character completion note explaining what you actually did.')
  c.execute('UPDATE vx7_tasks SET status=?,completed_at=?,completion_note=? WHERE id=? AND user_id=?',('completed',int(time.time()),note,tid,uid))
 elif action=='revoke':
  if status!='approved':raise ValueError('Only approved tasks can be revoked.')
  c.execute('UPDATE vx7_tasks SET status=?,approved_at=NULL WHERE id=? AND user_id=?',('blocked',tid,uid))
 else:raise ValueError('Unknown action.')
 log(c,uid,rid,tid,action,note if action=='complete' else 'Owner action')
 if not c.execute("SELECT 1 FROM vx7_tasks WHERE run_id=? AND user_id=? AND status!='completed' LIMIT 1",(rid,uid)).fetchone():
  c.execute('UPDATE vx7_runs SET status=? WHERE id=? AND user_id=?',('completed',rid,uid))
  log(c,uid,rid,'','workflow_completed','All internal tasks marked completed by owner; no external outcomes verified.')

def render(c,uid,csrf,mid=''):
 missions=c.execute('SELECT id,title FROM vx52_missions WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
 if not mid and missions:mid=missions[0][0]
 if mid not in [x[0] for x in missions]:mid=''
 token='<input type="hidden" name="csrf" value="'+e(csrf)+'">'
 out=['<section class="hero vx7-hero"><p class="eyebrow">VELXTRIA V7 / PROJECT OMNISCIENCE</p><h1>OPERATIONS.<br><em>UNDER CONTROL.</em></h1><p>Turn local AI strategies into durable, reviewable workflows. Approval gates, ordered tasks, and a complete audit trail. No automatic external actions.</p></section>',
 '<section class="panel"><h2>Mission command</h2><form method="get" action="/omniscience"><label>Choose mission<select name="id">']
 for id,title in missions:out.append('<option value="'+e(id)+'"'+(' selected' if id==mid else '')+'>'+e(title)+'</option>')
 out.append('</select></label><button>View mission workflows</button></form></section>')
 if not mid:return ''.join(out)+'<section class="panel">Create a mission first.</section>'
 plans=c.execute('SELECT id,goal FROM vx6_plans WHERE user_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 20',(uid,mid)).fetchall()
 out.append('<section class="panel"><p class="eyebrow">01 / ORCHESTRATION</p><h2>Import an AI strategy</h2><p>Each seven-day strategy becomes an ordered set of internal tasks. Importing does not execute anything.</p><form method="post" action="/omniscience">'+token+'<input type="hidden" name="action" value="create"><input type="hidden" name="mission_id" value="'+e(mid)+'"><label>Saved strategy<select name="plan_id">')
 for pid,goal in plans:out.append('<option value="'+e(pid)+'">'+e(goal[:150])+'</option>')
 out.append('</select></label><button '+('disabled' if not plans else '')+'>Create reviewed workflow</button></form>')
 if not plans:out.append('<p>No saved strategies yet. <a href="/singularity?id='+e(mid)+'">Generate one in Singularity AI</a>.</p>')
 out.append('</section>')
 runs=c.execute('SELECT id,title,status,created_at FROM vx7_runs WHERE user_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 20',(uid,mid)).fetchall()
 out.append('<section class="panel"><p class="eyebrow">02 / LIVE WORKFLOWS</p><h2>Mission execution board</h2>')
 if not runs:out.append('<p>No workflows imported yet.</p>')
 for rid,title,status,created in runs:
  tasks=c.execute('SELECT id,ordinal,role,title,evidence,status,completion_note FROM vx7_tasks WHERE run_id=? AND user_id=? ORDER BY ordinal',(rid,uid)).fetchall()
  done=sum(t[5]=='completed' for t in tasks)
  out.append('<details class="vx7-run" open><summary>'+e(title)+' · '+e(status)+' · '+str(done)+'/'+str(len(tasks))+' completed</summary><p>Created '+e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(created)))+' · Owner-reviewed task tracking, not autonomous execution.</p><div class="vx7-grid">')
  for tid,ordinal,role,task,evidence,ts,note in tasks:
   out.append('<article class="vx7-task"><span class="vx7-pill">'+e(role)+' · #'+str(ordinal)+'</span><span class="vx7-state">'+e(ts.upper())+'</span><h3>'+e(task)+'</h3><p><strong>Evidence needed:</strong> '+e(evidence)+'</p>')
   if note:out.append('<p><strong>Owner completion note:</strong> '+e(note)+'</p>')
   if ts in ('blocked','approved'):
    out.append('<form method="post" action="/omniscience">'+token+'<input type="hidden" name="mission_id" value="'+e(mid)+'"><input type="hidden" name="run_id" value="'+e(rid)+'"><input type="hidden" name="task_id" value="'+e(tid)+'">')
    if ts=='blocked':out.append('<input type="hidden" name="action" value="approve"><button>Approve internal task</button>')
    else:out.append('<input type="hidden" name="action" value="complete"><label>What did you actually complete?<textarea name="note" minlength="12" maxlength="1200" required></textarea></label><button>Record completion</button>')
    out.append('</form>')
    if ts=='approved':out.append('<form method="post" action="/omniscience">'+token+'<input type="hidden" name="mission_id" value="'+e(mid)+'"><input type="hidden" name="run_id" value="'+e(rid)+'"><input type="hidden" name="task_id" value="'+e(tid)+'"><input type="hidden" name="action" value="revoke"><button>Revoke approval</button></form>')
   out.append('</article>')
  out.append('</div><details><summary>Audit history</summary><ul>')
  events=c.execute('SELECT action,detail,created_at FROM vx7_events WHERE run_id=? AND user_id=? ORDER BY created_at DESC LIMIT 80',(rid,uid)).fetchall()
  for action,detail,ts in events:out.append('<li>'+e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(ts)))+' · '+e(action)+' · '+e(detail)+'</li>')
  out.append('</ul></details></details>')
 out.append('</section><section class="panel"><h2>Security boundary</h2><p>V7 only imports plans and records owner-approved internal task progress. It does not run arbitrary code, send email, update CRM, schedule jobs, charge money, or verify external outcomes. AI-generated instructions are treated as untrusted task descriptions.</p></section>')
 return ''.join(out)

CSS='''\n.vx7-hero{background:radial-gradient(ellipse at 75% 15%,#52317e,#171529 62%);border:1px solid #7556a3}.vx7-hero h1{font-size:clamp(2.5rem,6vw,4.7rem);letter-spacing:-.05em}.vx7-hero em{color:#c3a8ff;font-style:normal}.vx7-run{border:1px solid #52466e;border-radius:16px;margin:16px 0;padding:20px;background:#16182a}.vx7-run summary{cursor:pointer;color:#d5c1ff;font-weight:800}.vx7-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:20px 0}.vx7-task{background:#111527;border:1px solid #44405e;border-radius:14px;padding:18px}.vx7-task h3{font-size:1.05rem;line-height:1.5}.vx7-pill,.vx7-state{display:inline-block;padding:5px 9px;margin-right:6px;border:1px solid #6c5299;border-radius:30px;font-size:.73rem;color:#d4baff}.vx7-task textarea{min-height:80px}.vx7-task button{margin-top:10px}\n'''
