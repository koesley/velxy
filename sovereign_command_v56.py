"""V56.13 permission-scoped, read-only natural language command center.
Deterministic query routing; no LLM, SQL generation, external network or writes.
"""
import html, json, re
from urllib.parse import quote
import sovereign_v56 as core

INTENTS = (
 ('alerts', ('alert','alerts','guardian','health','warning','risk')),
 ('sources', ('connector','connectors','source','sources','snapshot','import')),
 ('strategies', ('strategy','strategies','scenario','simulation')),
 ('execution', ('execution','job','jobs','approval','task')),
 ('memory', ('memory','decision','decisions','outcome')),
 ('future', ('future','futures','forecast','projection','cash')),
)
LINKS = {'alerts':'/sovereign-guardian-v56','sources':'/sovereign-connectors-v56','strategies':'/sovereign-strategies-v56','execution':'/sovereign-execution-v56','memory':'/sovereign-memory-v56','future':'/sovereign-future-v56'}

def interpret(query):
 if not isinstance(query,str) or not query.strip() or len(query)>500 or any(ord(ch)<32 for ch in query):raise ValueError('Enter a question of 1–500 characters')
 q=query.lower(); words=set(re.findall(r"[a-z]+",q))
 if any(w in words for w in ('delete','send','pay','execute','approve','change','modify','create','update','transfer','cancel')):
  return 'blocked'
 scores=[(sum(1 for keyword in keywords if keyword in words),intent) for intent,keywords in INTENTS]
 best=max(x[0] for x in scores)
 if not best:return 'unsupported'
 winners=[intent for score,intent in scores if score==best]
 return winners[0] if len(winners)==1 else 'ambiguous'

def answer(c,uid,wid,query):
 core.access(c,uid,wid)
 intent=interpret(query)
 result={'question':query.strip(),'intent':intent,'workspace_id':wid,'read_only':True,'evidence':[],'limitations':[]}
 if intent=='blocked':result['answer']='This command center is read-only. Use the appropriate module and its explicit approval controls for changes.'
 elif intent=='ambiguous':result['answer']='Your question covers multiple modules. Ask about one area, such as alerts, connectors, strategies, execution, memory, or future.'
 elif intent=='unsupported':result['answer']='I cannot answer that from the supported local business records. Try asking about alerts, connectors, strategies, execution, memory, or future.'
 else:
  tables={
   'alerts':('sv56_guardian_alerts','status',"status='open'"),
   'sources':('sv56_connector_batches','status',"status='applied'"),
   'strategies':('sv56_strategy_runs',None,None),
   'execution':('sv56_exec_jobs',None,None),
   'memory':('sv56_memory_entries',None,None),
   'future':('sv56_future_runs',None,None),
  }
  table,field,filter_sql=tables[intent]
  exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
  if not exists:
   result['answer']='This module has no available local table in the current installation.'
  else:
   columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
   if 'workspace_id' not in columns:
    result['answer']='This module cannot be safely queried by workspace.'
   else:
    total=c.execute('SELECT COUNT(*) FROM '+table+' WHERE workspace_id=?',(wid,)).fetchone()[0]
    count=None
    if field in columns and filter_sql:
     count=c.execute('SELECT COUNT(*) FROM '+table+' WHERE workspace_id=? AND '+filter_sql,(wid,)).fetchone()[0]
    result['answer']={'alerts':f'{total} Guardian alerts recorded'+(f'; {count} currently open' if count is not None else ''), 'sources':f'{total} connector batches recorded'+(f'; {count} approved' if count is not None else ''),'strategies':f'{total} strategy evaluations recorded','execution':f'{total} execution jobs recorded','memory':f'{total} memory records recorded','future':f'{total} future simulation runs recorded'}[intent]+'. Counts reflect saved records, not independently verified business outcomes.'
    result['evidence']=[{'table':table,'workspace_id':wid,'count':total,'filtered_count':count}]
  result['module_url']=LINKS[intent]+'?w='+quote(wid,safe='')
 result['limitations']=['Read-only local SQLite queries; no generative model or autonomous agent.','Counts alone do not establish financial performance or causation.','Questions are not retained by this module.']
 return result

def render(c,uid,csrf,wid,question=''):
 core.access(c,uid,wid)
 e=lambda x:html.escape(str(x),quote=True)
 output=''
 if question:
  try:
   result=answer(c,uid,wid,question)
   output='<section class="cmd-result"><span class="cmd-eyebrow">VERIFIED LOCAL RESPONSE</span><h2>Answer</h2><p>'+e(result['answer'])+'</p>'
   if result.get('module_url'):output+='<a class="cmd-action" href="'+e(result['module_url'])+'">Open source module →</a>'
   if result['evidence']:output+='<details><summary>Evidence and query scope</summary><pre>'+e(json.dumps(result['evidence'],indent=2))+'</pre></details>'
   output+='</section>'
  except ValueError as exc:output='<section class="cmd-result"><p>'+e(exc)+'</p></section>'
 examples=('How many alerts?','Show connector sources','How many strategies?','Show execution jobs','Show memory decisions','Show future simulations')
 chips=''.join('<a href="/sovereign-command-v56?w='+quote(wid,safe='')+'&q='+quote(q,safe='')+'">'+e(q)+'</a>' for q in examples)
 return '<div class="cmd-shell"><section class="cmd-hero"><span class="cmd-eyebrow">✦ VELXTRIA / SOVEREIGN INTELLIGENCE</span><h1>Ask your business<span>.</span></h1><p>A clear answer, grounded in your workspace records. No guesses, no hidden actions.</p><form action="/sovereign-command-v56" method="get"><input type="hidden" name="w" value="'+e(wid)+'"><label for="cmd-question">Your question</label><div class="cmd-input-row"><input id="cmd-question" name="q" maxlength="500" required placeholder="Ask about alerts, strategies, execution..." value="'+e(question)+'"><button type="submit">Ask VELXTRIA →</button></div></form><div class="cmd-chips">'+chips+'</div></section>'+output+'<section class="cmd-note"><h2>Built for clarity and control</h2><p>This first version uses deterministic intent matching and workspace-scoped record counts. It does not generate SQL from prompts, use a paid AI API, take actions, or pretend to understand questions it cannot answer.</p></section></div>'
