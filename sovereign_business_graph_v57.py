"""Omniverse V57.2: evidence-aware, workspace-scoped business relationship graph.
Human-curated records, not inferred facts or autonomous changes.
"""
import html,json,secrets,time,sqlite3
import sovereign_v56 as core
TYPES=('customer','product','service','supplier','team','process','metric','risk','channel','system')
RELATIONS=('depends_on','supplies','serves','measures','affects','owns','uses','related_to')

def init(c):
 core.setup(c)
 c.execute("CREATE TABLE IF NOT EXISTS ov57_graph_nodes(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,type TEXT NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL,confidence TEXT NOT NULL,source TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0)")
 c.execute('CREATE INDEX IF NOT EXISTS ov57_graph_nodes_scope ON ov57_graph_nodes(workspace_id,archived)')
 c.execute("CREATE TABLE IF NOT EXISTS ov57_graph_edges(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,source_id TEXT NOT NULL,target_id TEXT NOT NULL,relation TEXT NOT NULL,description TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0,UNIQUE(workspace_id,source_id,target_id,relation))")
 c.execute('CREATE INDEX IF NOT EXISTS ov57_graph_edges_scope ON ov57_graph_edges(workspace_id,archived)')

def _value(v,limit=160):
 if not isinstance(v,str) or not v.strip() or len(v.strip())>limit or any(ord(x)<32 and x not in '\n\t' for x in v):raise ValueError('Invalid text field')
 return v.strip()

def node(c,uid,wid,kind,name,description,confidence,source):
 core.access(c,uid,wid,write=True);init(c)
 if kind not in TYPES or confidence not in ('verified','reported','hypothesis'):raise ValueError('Invalid node classification')
 name=_value(name,100);description=_value(description,600);source=_value(source,250)
 nid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO ov57_graph_nodes VALUES(?,?,?,?,?,?,?,?,?,0)',(nid,wid,kind,name,description,confidence,source,uid,int(time.time())))
  core.audit(c,uid,wid,'graph_node_created',nid)
 return nid

def edge(c,uid,wid,source_id,target_id,relation,description):
 core.access(c,uid,wid,write=True);init(c)
 if relation not in RELATIONS or source_id==target_id:raise ValueError('Invalid relationship')
 description=_value(description,600)
 with c:
  ids=c.execute('SELECT id FROM ov57_graph_nodes WHERE workspace_id=? AND archived=0 AND id IN (?,?)',(wid,source_id,target_id)).fetchall()
  if len(ids)!=2:raise ValueError('Both nodes must belong to this workspace')
  eid=secrets.token_hex(12)
  try:c.execute('INSERT INTO ov57_graph_edges VALUES(?,?,?,?,?,?,?,?,0)',(eid,wid,source_id,target_id,relation,description,uid,int(time.time())))
  except sqlite3.IntegrityError as exc:raise ValueError('Relationship already exists') from exc
  core.audit(c,uid,wid,'graph_edge_created',eid)
 return eid

def archive(c,uid,wid,kind,identifier):
 core.access(c,uid,wid,write=True);init(c)
 if kind not in ('node','edge'):raise ValueError('Invalid record type')
 with c:
  if kind=='node':
   cur=c.execute('UPDATE ov57_graph_nodes SET archived=1 WHERE id=? AND workspace_id=? AND archived=0',(identifier,wid))
   if cur.rowcount:c.execute('UPDATE ov57_graph_edges SET archived=1 WHERE workspace_id=? AND (source_id=? OR target_id=?)',(wid,identifier,identifier))
  else:cur=c.execute('UPDATE ov57_graph_edges SET archived=1 WHERE id=? AND workspace_id=? AND archived=0',(identifier,wid))
  if cur.rowcount!=1:raise ValueError('Record not found')
  core.audit(c,uid,wid,'graph_'+kind+'_archived',identifier)

def overview(c,uid,wid):
 role=core.access(c,uid,wid);init(c)
 ns=[dict(zip(('id','type','name','description','confidence','source'),r)) for r in c.execute('SELECT id,type,name,description,confidence,source FROM ov57_graph_nodes WHERE workspace_id=? AND archived=0 ORDER BY created DESC,id DESC LIMIT 250',(wid,))]
 es=[dict(zip(('id','source_id','target_id','relation','description'),r)) for r in c.execute('SELECT id,source_id,target_id,relation,description FROM ov57_graph_edges WHERE workspace_id=? AND archived=0 ORDER BY created DESC,id DESC LIMIT 500',(wid,))]
 degree={n['id']:0 for n in ns}
 for e in es:
  for k in ('source_id','target_id'):
   if e[k] in degree:degree[e[k]]+=1
 isolated=[n['name'] for n in ns if degree[n['id']]==0]
 uncertain=[n['name'] for n in ns if n['confidence']=='hypothesis']
 dependency=[n['name'] for n in ns if sum(e['target_id']==n['id'] and e['relation']=='depends_on' for e in es)>=2]
 return {'workspace_id':wid,'role':role,'nodes':ns,'edges':es,'insights':{'unconnected':isolated[:30],'hypotheses':uncertain[:30],'shared_dependencies':dependency[:30]},'counts':{'nodes':len(ns),'relationships':len(es),'hypotheses':len(uncertain),'unconnected':len(isolated)},'limitations':['Manual business model; relationships are not independently verified.','Insights are descriptive graph checks, not predictions.','The view is capped at 250 nodes and 500 relationships.']}

def render(c,uid,wid,csrf):
 d=overview(c,uid,wid);h=lambda s:html.escape(str(s),quote=True)
 hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
 url='/sovereign-business-graph-v57'
 opts=''.join('<option value="'+h(n['id'])+'">'+h(n['name'])+' ('+h(n['type'])+')</option>' for n in d['nodes'])
 types=''.join('<option>'+h(x)+'</option>' for x in TYPES)
 rels=''.join('<option>'+h(x)+'</option>' for x in RELATIONS)
 forms=''
 if d['role'] in ('owner','editor'):
  forms='<div class="ov-layout"><section class="ov-panel"><h2>Add business entity</h2><form method="post" action="'+url+'">'+hidden+'<label>Type<select name="type">'+types+'</select></label><label>Name<input name="name" maxlength="100" required></label><label>Description<input name="description" maxlength="600" required></label><label>Evidence status<select name="confidence"><option>reported</option><option>verified</option><option>hypothesis</option></select></label><label>Source / reference<input name="source" maxlength="250" required></label><button name="action" value="node">Add entity</button></form></section><section class="ov-panel"><h2>Connect entities</h2><form method="post" action="'+url+'">'+hidden+'<label>From<select name="source_id">'+opts+'</select></label><label>Relationship<select name="relation">'+rels+'</select></label><label>To<select name="target_id">'+opts+'</select></label><label>Explanation<input name="description" maxlength="600" required></label><button name="action" value="edge">Add relationship</button></form></section></div>'
 cards=''.join('<article class="ov-card"><strong>'+h(k)+'</strong><span>'+str(v)+'</span></article>' for k,v in d['counts'].items())
 ns=[]
 for n in d['nodes']:
  archive_btn=('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="record" value="'+h(n['id'])+'"><button name="action" value="archive_node">Archive</button></form>') if d['role'] in ('owner','editor') else ''
  ns.append('<article class="ov-job"><strong>'+h(n['name'])+' <small>'+h(n['type'])+' · '+h(n['confidence'])+'</small></strong><p>'+h(n['description'])+'</p><small>Source: '+h(n['source'])+'</small>'+archive_btn+'</article>')
 names={n['id']:n['name'] for n in d['nodes']}
 edges=''.join('<li>'+h(names.get(e['source_id'],'Unknown'))+' <b>'+h(e['relation'].replace('_',' '))+'</b> '+h(names.get(e['target_id'],'Unknown'))+'</li>' for e in d['edges'])
 insights=''.join('<p><strong>'+h(k.replace('_',' ').title())+'</strong>: '+h(', '.join(v) if v else 'None recorded')+'</p>' for k,v in d['insights'].items())
 return '<section class="ov-hero"><span>PROJECT OMNIVERSE · BUSINESS GRAPH</span><h1>See how your business connects.</h1><p>Map systems, processes, products, customers, and dependencies. Trace evidence and discover gaps without inventing facts.</p><a href="/sovereign-omniverse-v57?w='+h(wid)+'">← Omniverse Command</a></section><section class="ov-metrics">'+cards+'</section>'+forms+'<div class="ov-layout" style="margin-top:18px"><section class="ov-panel"><h2>Business entities</h2>'+(''.join(ns) or '<p>No entities yet. Add the first one above.</p>')+'</section><aside class="ov-panel"><h2>Relationship map</h2><ul>'+edges+'</ul><h2>Evidence & blind spots</h2>'+insights+'<p>All relationships are manually entered and require verification before business decisions.</p></aside></div>'
