"""Milestone 15: workspace-isolated, read-only unified command surface."""
import html
import urllib.parse
import sqlite3
import sovereign_v56 as core

MODULES=(
 ('Discover','Project Genesis','/sovereign-genesis-v56','sv56_genesis_sessions','Investigate new hypotheses and measured experiments.'),
 ('Discover','Ask VELXTRIA','/sovereign-command-v56',None,'Ask evidence-grounded questions.'),
 ('Observe','Business Guardian','/sovereign-guardian-v56','sv56_guardian_alerts','Review detected data-quality and business signals.'),
 ('Observe','Connectors','/sovereign-connectors-v56','sv56_connector_batches','Review imported connector batches.'),
 ('Observe','Digital Twin','/sovereign-twin-v56',None,'Inspect the current business snapshot.'),
 ('Decide','Executive Council','/sovereign-executive-v56',None,'Review executive decision support.'),
 ('Decide','Strategies','/sovereign-strategies-v56','sv56_strategy_runs','Compare modeled strategies.'),
 ('Decide','Future Simulator','/sovereign-future-v56','sv56_future_runs','Explore hypothetical futures.'),
 ('Act','Execution Center','/sovereign-execution-v56','sv56_exec_jobs','Manage human-approved work.'),
 ('Learn','Organizational Memory','/sovereign-memory-v56','sv56_memory_entries','Track decisions and reported outcomes.'),
)

def overview(c,uid,wid):
 role=core.access(c,uid,wid)
 tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 modules=[]
 for group,name,path,table,description in MODULES:
  count=None
  if table in tables:
   # Table names are hard-coded above, never accepted from user input.
   count=c.execute('SELECT COUNT(*) FROM '+table+' WHERE workspace_id=?',(wid,)).fetchone()[0]
  modules.append({'group':group,'name':name,'path':path+'?w='+urllib.parse.quote(wid,safe=''),'count':count,'description':description})
 genesis=next(x for x in modules if x['name']=='Project Genesis')['count']
 guardian=next(x for x in modules if x['name']=='Business Guardian')['count']
 checks=[
  {'name':'Workspace authorization','state':'verified','detail':'Workspace membership checked on every request.'},
  {'name':'Genesis evidence','state':'available' if genesis else 'needs attention','detail':'Discovery sessions are available.' if genesis else 'Create a discovery session from approved business evidence.'},
  {'name':'Guardian monitoring','state':'available' if guardian else 'needs attention','detail':'Guardian alerts are recorded.' if guardian else 'No guardian alerts recorded; this is not a clean bill of health.'},
  {'name':'Production readiness','state':'not verified','detail':'Local dashboard checks do not certify security, integration, or deployment readiness.'},
 ]
 priorities=[]
 counts={m['name']:m['count'] for m in modules}
 if not counts.get('Connectors'):
  priorities.append({'level':'start','title':'Connect approved business data','detail':'Stage and review a local CSV batch before drawing conclusions.','path':next(m['path'] for m in modules if m['name']=='Connectors')})
 if not counts.get('Project Genesis'):
  priorities.append({'level':'explore','title':'Start a discovery session','detail':'Investigate hypotheses only after validating business evidence.','path':next(m['path'] for m in modules if m['name']=='Project Genesis')})
 if counts.get('Business Guardian'):
  priorities.append({'level':'review','title':'Review Guardian alerts','detail':'Recorded alerts require human review; counts do not indicate severity.','path':next(m['path'] for m in modules if m['name']=='Business Guardian')})
 if counts.get('Execution Center'):
  priorities.append({'level':'review','title':'Inspect approved execution jobs','detail':'Confirm job state and approvals in the Execution Center.','path':next(m['path'] for m in modules if m['name']=='Execution Center')})
 if not counts.get('Organizational Memory'):
  priorities.append({'level':'learn','title':'Document a decision','detail':'Capture the evidence and owner-reported result for later comparison.','path':next(m['path'] for m in modules if m['name']=='Organizational Memory')})
 total=sum(m['count'] or 0 for m in modules)
 tracked=sum(m['count'] is not None for m in modules)
 return {'workspace_id':wid,'role':role,'modules':modules,'checks':checks,'priorities':priorities,'summary':{'recorded_items':total,'counted_modules':tracked,'available_modules':len(modules),'active_pathways':len({m['group'] for m in modules if m['count']})},'read_only':True,'limitations':['Counts are workspace-scoped records, not success metrics.','No automatic external execution, money movement, or AI claims.','This dashboard does not replace an end-to-end production audit.']}

def render(c,uid,wid):
 d=overview(c,uid,wid);e=lambda v:html.escape(str(v),quote=True)
 groups=('Discover','Observe','Decide','Act','Learn')
 out=['<div class="unified-shell"><section class="unified-hero"><p class="unified-kicker">VELXTRIA / PROJECT SOVEREIGN · MILESTONE 15</p><h1>One command surface.<br><em>Every business possibility.</em></h1><p>A single place to move from evidence to discovery, decisions, approved work, and learning.</p><div class="unified-pills"><span>Workspace: '+e(wid)+'</span><span>Role: '+e(d['role'])+'</span><span>Read-only overview</span></div></section>']
 out.append('<section class="unified-section"><h2>Workspace pulse</h2><div class="unified-pulse">')
 for label,value in [('Recorded items',d['summary']['recorded_items']),('Counted modules',str(d['summary']['counted_modules'])+' / '+str(d['summary']['available_modules'])),('Pathways with records',str(d['summary']['active_pathways'])+' / 5')]:
  out.append('<div class="unified-metric"><strong>'+e(value)+'</strong><span>'+e(label)+'</span></div>')
 out.append('</div><p class="unified-disclaimer">Record counts measure stored entries, not revenue, outcomes, or health.</p></section>')
 out.append('<section class="unified-section"><h2>Suggested next steps</h2><p class="unified-disclaimer">Rule-based suggestions from workspace record presence; not AI diagnoses or automated actions.</p><div class="unified-priorities">')
 for item in d['priorities']:
  out.append('<a class="unified-priority" href="'+e(item['path'])+'"><span class="unified-tag">'+e(item['level'])+'</span><strong>'+e(item['title'])+'</strong><small>'+e(item['detail'])+'</small><span aria-hidden="true">↗</span></a>')
 if not d['priorities']:out.append('<p>No immediate record-presence suggestions. Review Guardian and business evidence regularly.</p>')
 out.append('</div></section>')
 out.append('<section class="unified-section"><h2>Operational pathways</h2><label class="unified-search-label" for="unified-search">Find a module</label><input id="unified-search" class="unified-search" type="search" placeholder="Search Genesis, Guardian, strategies…" autocomplete="off"><p id="unified-search-status" class="unified-disclaimer" aria-live="polite"></p><div class="unified-grid" id="unified-module-grid">')
 for group in groups:
  out.append('<article class="unified-card"><div class="unified-step">'+e(group)+'</div>')
  for m in d['modules']:
   if m['group']!=group:continue
   out.append('<a class="unified-module" href="'+e(m['path'])+'"><strong>'+e(m['name'])+'</strong><span>'+e(m['description'])+'</span><small>'+('No counter' if m['count'] is None else str(m['count'])+' records')+'</small></a>')
  out.append('</article>')
 out.append('</div></section><section class="unified-section"><h2>Readiness & evidence</h2><div class="unified-checks">')
 for check in d['checks']:out.append('<div class="unified-check"><strong>'+e(check['name'])+'</strong><span>'+e(check['state'])+'</span><p>'+e(check['detail'])+'</p></div>')
 out.append('</div><p class="unified-disclaimer">'+e(' '.join(d['limitations']))+'</p></section>')
 out.append('<script defer>(function(){"use strict";var input=document.getElementById("unified-search"),grid=document.getElementById("unified-module-grid"),status=document.getElementById("unified-search-status");if(!input||!grid)return;input.addEventListener("input",function(){var q=input.value.trim().toLocaleLowerCase(),shown=0;grid.querySelectorAll(".unified-card").forEach(function(card){var links=card.querySelectorAll(".unified-module"),n=0;links.forEach(function(link){var match=link.textContent.toLocaleLowerCase().includes(q);link.hidden=!match;if(match)n++});card.hidden=n===0;shown+=n});status.textContent=q?shown+" matching modules":""})})();</script></div>')
 return ''.join(out)
