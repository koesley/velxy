"""V8 safe local agent tools: read-only scoped business diagnostics, durable results."""
import html,json,secrets,time

def esc(x):return html.escape(str(x),quote=True)
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS vx8_tool_runs(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,mission_id TEXT NOT NULL,tool TEXT NOT NULL,status TEXT NOT NULL,output_json TEXT NOT NULL,created_at INTEGER NOT NULL,completed_at INTEGER NOT NULL DEFAULT 0)""")
 c.execute('CREATE INDEX IF NOT EXISTS vx8_tool_runs_scope ON vx8_tool_runs(user_id,mission_id,created_at)')

TOOLS={'pipeline_audit':'CRM pipeline audit','mission_audit':'Mission execution audit','operations_audit':'Open task and finance overview'}

def run(c,uid,mid,tool):
 if tool not in TOOLS:raise ValueError('Unknown or unauthorized tool.')
 mission=c.execute('SELECT title FROM vx52_missions WHERE id=? AND user_id=?',(mid,uid)).fetchone()
 if not mission:raise ValueError('Mission is not accessible.')
 rid=secrets.token_hex(16);ts=int(time.time())
 c.execute('INSERT INTO vx8_tool_runs VALUES(?,?,?,?,?,?,?,?)',(rid,uid,mid,tool,'running','{}',ts,0))
 try:
  if tool=='pipeline_audit':
   rows=c.execute('SELECT stage,COUNT(*) FROM vx3_contacts WHERE user_id=? GROUP BY stage ORDER BY stage',(uid,)).fetchall()
   contacts=c.execute('SELECT name,stage,created_at FROM vx3_contacts WHERE user_id=? ORDER BY created_at DESC LIMIT 20',(uid,)).fetchall()
   output={'scope':'Current account CRM; not verified customer behavior','total_contacts':sum(x[1] for x in rows),'stages':{str(a):b for a,b in rows},'recent_contacts':[{'name':a,'stage':b,'created_at':d} for a,b,d in contacts],'recommendation':'Review leads without a recorded next step. No messages have been sent.'}
  elif tool=='mission_audit':
   actions=c.execute('SELECT status,COUNT(*) FROM vx53_actions WHERE mission_id=? AND user_id=? GROUP BY status',(mid,uid)).fetchall()
   evidence=c.execute('SELECT COUNT(*) FROM vx55_outcomes WHERE mission_id=? AND user_id=?',(mid,uid)).fetchone()[0] if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='vx55_outcomes'").fetchone() else None
   output={'scope':'Recorded internal actions only','mission':mission[0],'action_status_counts':{str(a):b for a,b in actions},'outcome_records':evidence,'warning':'Executed drafts are not proof of customer contact or revenue.'}
  else:
   tasks=c.execute('SELECT status,COUNT(*) FROM vx3_tasks WHERE user_id=? GROUP BY status',(uid,)).fetchall()
   entries=c.execute('SELECT kind,COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx3_entries WHERE user_id=? GROUP BY kind',(uid,)).fetchall()
   output={'scope':'Current account internal records','task_counts':{str(a):b for a,b in tasks},'recorded_entry_totals_cents':{str(a):{'count':b,'cents':d} for a,b,d in entries},'warning':'Entries are not reconciled bank balances or forecasts.'}
  c.execute('UPDATE vx8_tool_runs SET status=?,output_json=?,completed_at=? WHERE id=? AND user_id=?',('completed',json.dumps(output,ensure_ascii=False),int(time.time()),rid,uid))
 except Exception as exc:
  c.execute('UPDATE vx8_tool_runs SET status=?,output_json=?,completed_at=? WHERE id=? AND user_id=?',('failed',json.dumps({'error':type(exc).__name__}),int(time.time()),rid,uid))
  raise
 return rid

def render(c,uid,csrf,mid=''):
 missions=c.execute('SELECT id,title FROM vx52_missions WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
 if mid not in [m[0] for m in missions]:mid=missions[0][0] if missions else ''
 out=['<section class="hero vx8hero"><p class="eyebrow">VELXTRIA V8 / PROJECT SOVEREIGN</p><h1>AGENTS THAT <em>DO THE WORK.</em></h1><p>Execute real, account-scoped, read-only business diagnostics. Every run produces stored evidence. No email, payment, CRM mutation, shell execution, or hidden side effects.</p></section>', '<section class="panel"><h2>Mission scope</h2><form method="get" action="/sovereign"><label>Choose mission<select name="id">']
 for ident,title in missions:out.append('<option value="'+esc(ident)+'"'+(' selected' if ident==mid else '')+'>'+esc(title)+'</option>')
 out.append('</select></label><button>Load mission</button></form></section>')
 if not mid:return ''.join(out)+'<section class="panel">Create a mission first.</section>'
 out.append('<section class="panel"><p class="eyebrow">01 / EXECUTION RUNTIME</p><h2>Authorized agent tools</h2><p>These tools read real database records for your account. They run only when you click Run; no AI-generated text can invoke arbitrary tools.</p><div class="vx8grid">')
 for key,label in TOOLS.items():
  out.append('<article class="vx8tool"><h3>'+esc(label)+'</h3><p>'+esc({'pipeline_audit':'Summarize CRM stages and recent contacts.','mission_audit':'Inspect recorded mission action states.','operations_audit':'Summarize internal tasks and finance entries.'}[key])+'</p><form method="post" action="/sovereign"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="mission_id" value="'+esc(mid)+'"><input type="hidden" name="tool" value="'+key+'"><button>Run diagnostic</button></form></article>')
 out.append('</div></section><section class="panel"><p class="eyebrow">02 / AUDITABLE OUTPUT</p><h2>Execution history</h2>')
 rows=c.execute('SELECT tool,status,output_json,created_at FROM vx8_tool_runs WHERE user_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 30',(uid,mid)).fetchall()
 if not rows:out.append('<p>No diagnostic runs yet. Run a tool above to create the first evidence record.</p>')
 for tool,status,raw,ts in rows:
  try:formatted=json.dumps(json.loads(raw),indent=2,ensure_ascii=False)
  except ValueError:formatted='Invalid stored result'
  out.append('<details class="vx8result"><summary>'+esc(TOOLS.get(tool,tool))+' · '+esc(status)+' · '+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(ts)))+'</summary><pre>'+esc(formatted)+'</pre></details>')
 out.append('</section><section class="panel"><h2>Execution boundary</h2><p>V8 performs read-only internal database analysis. It does not yet provide autonomous background scheduling, multi-model agent coordination, or external action execution. Those require separate, tested permission and recovery systems.</p></section>')
 return ''.join(out)

CSS='\n.vx8hero{background:#171225;border:1px solid #7859a9}.vx8hero em{color:#c9aaff}.vx8grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}.vx8tool,.vx8result{border:1px solid #55436d;background:#19162b;border-radius:15px;padding:18px}.vx8result pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#d9c8f3}\n'
