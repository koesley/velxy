"""Milestone 4: reviewed, tenant-scoped synchronization of imported monthly facts into the twin.
No external connector or inferred business relationships.
"""
import html, json, secrets, time
from urllib.parse import quote
import sovereign_v56 as core
import sovereign_twin_v56 as twin

def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_sync_runs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('completed','no_change')),created_count INTEGER NOT NULL,skipped_count INTEGER NOT NULL,conflict_count INTEGER NOT NULL)""")
 c.execute("CREATE INDEX IF NOT EXISTS sv56_sync_runs_scope ON sv56_sync_runs(workspace_id,created)")
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_sync_links(workspace_id TEXT NOT NULL,period TEXT NOT NULL,node_id TEXT NOT NULL,import_id TEXT NOT NULL,PRIMARY KEY(workspace_id,period),FOREIGN KEY(node_id) REFERENCES sv56_twin_nodes(id))""")
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_sync_conflicts(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,period TEXT NOT NULL,source_import_ids TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(workspace_id,period,source_import_ids))""")

def preview(c,uid,wid):
 core.access(c,uid,wid)
 rows=c.execute('SELECT period,import_id FROM sv56_metrics WHERE workspace_id=? ORDER BY period,import_id',(wid,)).fetchall()
 periods={}
 for period,iid in rows:periods.setdefault(period,set()).add(iid)
 links={p:(nid,iid) for p,nid,iid in c.execute('SELECT period,node_id,import_id FROM sv56_sync_links WHERE workspace_id=?',(wid,))}
 planned=[];conflicts=[];unchanged=[];stale=[]
 for period,ids in sorted(periods.items()):
  if len(ids)!=1:conflicts.append({'period':period,'source_import_ids':sorted(ids)});continue
  iid=next(iter(ids))
  if period in links:
   if links[period][1]==iid:unchanged.append(period)
   else:stale.append({'period':period,'existing_source':links[period][1],'incoming_source':iid})
  else:planned.append({'period':period,'source_import_id':iid})
 return {'workspace_id':wid,'to_create':planned,'unchanged':unchanged,'conflicts':conflicts,'requires_review':stale,'limitations':['Imports remain immutable; conflicting periods require source review.','Only unambiguous periods create twin nodes.','This is a local database adapter, not third-party synchronization.']}

def apply(c,uid,wid):
 core.access(c,uid,wid,write=True)
 state=preview(c,uid,wid)
 run_id=secrets.token_hex(12);created=0
 with c:
  for item in state['to_create']:
   period=item['period'];iid=item['source_import_id']
   # Avoid race or duplicate application and protect manually-created twin nodes.
   if c.execute('SELECT 1 FROM sv56_sync_links WHERE workspace_id=? AND period=?',(wid,period)).fetchone():continue
   node=twin.add_node(c,uid,wid,'metric_period',period,'sv56_import:'+iid)
   c.execute('INSERT INTO sv56_sync_links VALUES(?,?,?,?)',(wid,period,node,iid));created+=1
  for item in state['conflicts']:
   ids=json.dumps(item['source_import_ids'],separators=(',',':'))
   c.execute('INSERT OR IGNORE INTO sv56_sync_conflicts VALUES(?,?,?,?,?)',(secrets.token_hex(12),wid,item['period'],ids,int(time.time())))
  c.execute('INSERT INTO sv56_sync_runs VALUES(?,?,?,?,?,?,?,?)',(run_id,wid,uid,int(time.time()),'completed' if created else 'no_change',created,len(state['unchanged']),len(state['conflicts'])+len(state['requires_review'])))
  core.audit(c,uid,wid,'digital_twin_sync',run_id)
 return {'run_id':run_id,'created':created,'unchanged':len(state['unchanged']),'conflicts':state['conflicts'],'requires_review':state['requires_review']}

def status(c,uid,wid):
 state=preview(c,uid,wid)
 state['runs']=[{'id':i,'timestamp':ts,'status':s,'created':n,'unchanged':u,'conflicts':x} for i,ts,s,n,u,x in c.execute('SELECT id,created,status,created_count,skipped_count,conflict_count FROM sv56_sync_runs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 30',(wid,))]
 state['links']=[{'period':p,'node_id':nid,'source_import_id':iid} for p,nid,iid in c.execute('SELECT period,node_id,import_id FROM sv56_sync_links WHERE workspace_id=? ORDER BY period',(wid,))]
 return state

def render(c,uid,csrf,wid):
 r=status(c,uid,wid);esc=lambda s:html.escape(str(s),quote=True)
 rows=''.join('<tr><td>'+esc(i['period'])+'</td><td>'+esc(i['source_import_id'])+'</td></tr>' for i in r['to_create']) or '<tr><td colspan="2">No new unambiguous periods.</td></tr>'
 conflicts=''.join('<li>'+esc(i['period'])+' — '+esc(', '.join(i['source_import_ids']))+'</li>' for i in r['conflicts']) or '<li>None</li>'
 stale=''.join('<li>'+esc(i['period'])+' — review existing and incoming sources</li>' for i in r['requires_review']) or '<li>None</li>'
 runs=''.join('<tr><td>'+esc(i['status'])+'</td><td>'+str(i['created'])+'</td><td>'+str(i['conflicts'])+'</td></tr>' for i in r['runs']) or '<tr><td colspan="3">No synchronization attempts yet.</td></tr>'
 return '<section class="panel"><h1>Sovereign Sync & Reconciliation</h1><p>Preview and approve a local sync from imported monthly metrics into sourced Digital Twin nodes. Conflicting periods are never overwritten.</p><a href="/sovereign-sync-v56.json?w='+quote(wid,safe='')+'">Export synchronization status</a></section><section class="panel"><h2>Preview: '+str(len(r['to_create']))+' new periods</h2><table><tr><th>Period</th><th>Import source</th></tr>'+rows+'</table><p>'+str(len(r['unchanged']))+' unchanged periods.</p><h3>Import conflicts</h3><ul>'+conflicts+'</ul><h3>Source changes requiring review</h3><ul>'+stale+'</ul><form method="post" action="/sovereign-sync-v56"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><button>Apply unambiguous records</button></form></section><section class="panel"><h2>Sync history</h2><table><tr><th>Status</th><th>Created</th><th>Conflicts</th></tr>'+runs+'</table></section>'
