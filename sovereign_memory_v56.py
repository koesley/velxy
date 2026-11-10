"""Sovereign M8: immutable, workspace-scoped decision and outcome memory.

No automatic learning or causal inference: all outcomes are human-reported.
"""
import html, json, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_execution_v56 as execution

KINDS=('decision','observation','outcome','lesson')
RESULTS=('unknown','positive','negative','mixed','inconclusive')

def setup(c):
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_memory_entries(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('decision','observation','outcome','lesson')),
 title TEXT NOT NULL,body TEXT NOT NULL,result TEXT NOT NULL,
 strategy_id TEXT,job_id TEXT,source_ids TEXT NOT NULL DEFAULT '[]',
 supersedes_id TEXT,created INTEGER NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_memory_scope ON sv56_memory_entries(workspace_id,created)')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_memory_job ON sv56_memory_entries(workspace_id,job_id)')
 c.execute('''CREATE TABLE IF NOT EXISTS sv56_memory_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id TEXT NOT NULL,entry_id TEXT NOT NULL,
 actor INTEGER NOT NULL,event TEXT NOT NULL,created INTEGER NOT NULL)''')

def _clean(value,label,limit):
 if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:raise ValueError('Invalid '+label)
 return value.strip()

def record(c,uid,wid,kind,title,body,result='unknown',strategy_id='',job_id='',source_ids=None,supersedes_id=''):
 core.access(c,uid,wid,write=True)
 if kind not in KINDS or result not in RESULTS:raise ValueError('Invalid memory category or result')
 title=_clean(title,'title',160);body=_clean(body,'description',4000)
 if kind!='outcome' and result!='unknown':raise ValueError('Only outcomes can have a result')
 if kind=='outcome' and not job_id:raise ValueError('Outcomes require an execution job')
 if source_ids is None:source_ids=[]
 if not isinstance(source_ids,list) or len(source_ids)>20 or any(not isinstance(x,str) or len(x)>128 or not x for x in source_ids):raise ValueError('Invalid sources')
 if len(set(source_ids))!=len(source_ids):raise ValueError('Duplicate sources')
 if job_id:
  row=c.execute('SELECT strategy_id,status FROM sv56_exec_jobs WHERE id=? AND workspace_id=?',(job_id,wid)).fetchone()
  if not row:raise ValueError('Execution job not found')
  if strategy_id and strategy_id!=row[0]:raise ValueError('Strategy does not match job')
  strategy_id=row[0]
  if kind=='outcome' and row[1]!='succeeded':raise ValueError('Outcomes require a completed job')
 if strategy_id and not c.execute('SELECT 1 FROM sv56_strategy_runs WHERE id=? AND workspace_id=?',(strategy_id,wid)).fetchone():raise ValueError('Strategy not found')
 if supersedes_id:
  prev=c.execute('SELECT kind,job_id,strategy_id FROM sv56_memory_entries WHERE id=? AND workspace_id=?',(supersedes_id,wid)).fetchone()
  if not prev:raise ValueError('Original memory not found')
  if (kind,job_id or None,strategy_id or None)!=(prev[0],prev[1],prev[2]):raise ValueError('Corrections must preserve kind and references')
  if c.execute('SELECT 1 FROM sv56_memory_entries WHERE workspace_id=? AND supersedes_id=?',(wid,supersedes_id)).fetchone():raise ValueError('Entry already superseded')
 now=int(time.time());mid=secrets.token_hex(12)
 with c:
  c.execute('''INSERT INTO sv56_memory_entries(id,workspace_id,actor,kind,title,body,result,strategy_id,job_id,source_ids,supersedes_id,created)
   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(mid,wid,uid,kind,title,body,result,strategy_id or None,job_id or None,json.dumps(source_ids),supersedes_id or None,now))
  c.execute('INSERT INTO sv56_memory_events(workspace_id,entry_id,actor,event,created) VALUES(?,?,?,?,?)',(wid,mid,uid,'corrected' if supersedes_id else 'created',now))
  core.audit(c,uid,wid,'memory_corrected' if supersedes_id else 'memory_created',mid)
 return mid

def history(c,uid,wid,query='',include_superseded=False):
 core.access(c,uid,wid)
 if not isinstance(query,str) or len(query)>160:raise ValueError('Invalid search')
 sql='''SELECT m.id,m.actor,m.kind,m.title,m.body,m.result,m.strategy_id,m.job_id,m.source_ids,m.supersedes_id,m.created,
 EXISTS(SELECT 1 FROM sv56_memory_entries newer WHERE newer.workspace_id=m.workspace_id AND newer.supersedes_id=m.id)
 FROM sv56_memory_entries m WHERE m.workspace_id=?'''
 args=[wid]
 if query.strip():
  # Escape SQL wildcard characters so search remains a literal substring search.
  term=query.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
  sql+=' AND (m.title LIKE ? ESCAPE \'\\\' OR m.body LIKE ? ESCAPE \'\\\')';args.extend(['%'+term+'%']*2)
 if not include_superseded:sql+=' AND NOT EXISTS(SELECT 1 FROM sv56_memory_entries n WHERE n.workspace_id=m.workspace_id AND n.supersedes_id=m.id)'
 sql+=' ORDER BY m.created DESC,m.rowid DESC LIMIT 100'
 out=[]
 for r in c.execute(sql,args):
  out.append(dict(zip(('id','actor','kind','title','body','result','strategy_id','job_id','source_ids','supersedes_id','created','superseded'),r)))
  out[-1]['source_ids']=json.loads(out[-1]['source_ids']);out[-1]['superseded']=bool(out[-1]['superseded'])
 return out

def timeline(c,uid,wid):
 core.access(c,uid,wid)
 memories=history(c,uid,wid,include_superseded=True)
 jobs=execution.history(c,uid,wid)
 return {'entries':memories,'execution_jobs':jobs['jobs'],'execution_events':jobs['events'],
         'human_reported_outcomes_only':True,'automatic_learning':False,'causal_inference':False}

def render(c,uid,csrf,wid,query=''):
 core.access(c,uid,wid)
 e=lambda x:html.escape(str(x),quote=True)
 jobs=execution.history(c,uid,wid)['jobs']
 h=['<section class="panel"><p class="eyebrow">PROJECT SOVEREIGN · MILESTONE 8</p><h1>Organizational Memory</h1><p>Versioned decisions, observations, outcomes, and lessons. Outcomes are human-reported, not independently verified. No automatic model training or causal claims.</p><p><a href="/sovereign-memory-v56.json?w='+quote(wid,safe='')+'">Export memory and execution timeline</a></p></section>']
 h.append('<section class="panel"><h2>Record a memory</h2><form method="post" action="/sovereign-memory-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><label>Category<select name="kind">'+''.join('<option>'+e(k)+'</option>' for k in KINDS)+'</select></label><label>Title<input name="title" maxlength="160" required></label><label>Details<textarea name="body" maxlength="4000" required></textarea></label><label>Reported result (outcomes only)<select name="result">'+''.join('<option>'+e(x)+'</option>' for x in RESULTS)+'</select></label><label>Linked execution job (required for outcomes)<select name="job_id"><option value="">None</option>')
 for j in jobs:h.append('<option value="'+e(j['id'])+'">'+e(j['id']+' · '+j['status'])+'</option>')
 h.append('</select></label><label>Supersede entry ID (corrections only)<input name="supersedes_id" maxlength="128"></label><button>Save memory</button></form></section>')
 h.append('<section class="panel"><h2>Memory history</h2><form method="get" action="/sovereign-memory-v56"><input type="hidden" name="w" value="'+e(wid)+'"><label>Search<input name="q" value="'+e(query)+'" maxlength="160"></label><button>Search</button></form>')
 for m in history(c,uid,wid,query):
  h.append('<article class="panel"><strong>'+e(m['title'])+'</strong> · '+e(m['kind'])+' · '+e(m['result'])+'<p>'+e(m['body'])+'</p><small>Entry: '+e(m['id'])+' · Job: '+e(m['job_id'] or 'none')+' · Strategy: '+e(m['strategy_id'] or 'none')+'</small></article>')
 h.append('</section>');return ''.join(h)
