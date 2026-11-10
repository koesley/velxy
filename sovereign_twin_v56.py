"""Sovereign Digital Twin milestone: typed, tenant-scoped, provenance-backed business graph.
Manual records only; no external sync or inferred business relationships.
"""
import json,html,secrets,time,re
import sovereign_v56 as core
from urllib.parse import quote
TYPES=('company','product','service','customer_segment','campaign','pipeline','workflow','expense_category','goal','supplier','metric_period')
RELATIONS={'offers':('company',('product','service')),'targets':('campaign',('customer_segment',)),'feeds':('campaign',('pipeline',)),'fulfills':('workflow',('product','service')),'depends_on':('goal',('workflow','campaign','pipeline','product','service')),'supplied_by':('product',('supplier',)),'tracks':('goal',('product','service','pipeline','customer_segment'))}

def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_twin_nodes(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,source TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,revision INTEGER NOT NULL DEFAULT 1,UNIQUE(workspace_id,kind,name))""")
 c.execute('CREATE INDEX IF NOT EXISTS sv56_twin_nodes_scope ON sv56_twin_nodes(workspace_id,kind)')
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_twin_edges(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,from_id TEXT NOT NULL,to_id TEXT NOT NULL,relation TEXT NOT NULL,source TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(workspace_id,from_id,to_id,relation),FOREIGN KEY(from_id) REFERENCES sv56_twin_nodes(id),FOREIGN KEY(to_id) REFERENCES sv56_twin_nodes(id))""")
 c.execute('CREATE INDEX IF NOT EXISTS sv56_twin_edges_scope ON sv56_twin_edges(workspace_id,from_id)')
 c.execute("""CREATE TABLE IF NOT EXISTS sv56_twin_changes(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,operation TEXT NOT NULL,object_id TEXT NOT NULL,created INTEGER NOT NULL)""")

def _text(v,label,limit=120):
 if not isinstance(v,str) or not 1<=len(v.strip())<=limit or any(ord(ch)<32 for ch in v):raise ValueError('Invalid '+label)
 return v.strip()

def _log(c,uid,wid,op,obj):
 c.execute('INSERT INTO sv56_twin_changes VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wid,uid,op,obj,int(time.time())))

def add_node(c,uid,wid,kind,name,source):
 core.access(c,uid,wid,write=True)
 if kind not in TYPES:raise ValueError('Unsupported entity type')
 name=_text(name,'name');source=_text(source,'source')
 if c.execute('SELECT 1 FROM sv56_twin_nodes WHERE workspace_id=? AND kind=? AND name=?',(wid,kind,name)).fetchone():raise ValueError('Entity already exists; use reconciliation rather than silently overwrite')
 ident=secrets.token_hex(12);ts=int(time.time())
 with c:
  c.execute('INSERT INTO sv56_twin_nodes VALUES(?,?,?,?,?,?,?,?)',(ident,wid,kind,name,source,ts,ts,1));_log(c,uid,wid,'node_created',ident)
 return ident

def add_edge(c,uid,wid,from_id,to_id,relation,source):
 core.access(c,uid,wid,write=True)
 source=_text(source,'source')
 if relation not in RELATIONS:raise ValueError('Unsupported relationship')
 if from_id==to_id:raise ValueError('Self relationship prohibited')
 a=c.execute('SELECT kind FROM sv56_twin_nodes WHERE workspace_id=? AND id=?',(wid,from_id)).fetchone()
 b=c.execute('SELECT kind FROM sv56_twin_nodes WHERE workspace_id=? AND id=?',(wid,to_id)).fetchone()
 if not a or not b:raise ValueError('Both entities must belong to this workspace')
 if a[0]!=RELATIONS[relation][0] or b[0] not in RELATIONS[relation][1]:raise ValueError('Relationship types incompatible')
 if c.execute('SELECT 1 FROM sv56_twin_edges WHERE workspace_id=? AND from_id=? AND to_id=? AND relation=?',(wid,from_id,to_id,relation)).fetchone():raise ValueError('Relationship already exists')
 ident=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_twin_edges VALUES(?,?,?,?,?,?,?)',(ident,wid,from_id,to_id,relation,source,int(time.time())));_log(c,uid,wid,'edge_created',ident)
 return ident

def reconcile(c,uid,wid,ident,expected_revision,new_name,new_source):
 core.access(c,uid,wid,write=True)
 new_name=_text(new_name,'name');new_source=_text(new_source,'source')
 try:expected_revision=int(expected_revision)
 except (TypeError,ValueError):raise ValueError('Invalid revision')
 with c:
  n=c.execute('UPDATE sv56_twin_nodes SET name=?,source=?,revision=revision+1,updated=? WHERE workspace_id=? AND id=? AND revision=?',(new_name,new_source,int(time.time()),wid,ident,expected_revision))
  if n.rowcount!=1:raise ValueError('Entity not found or modified since review')
  _log(c,uid,wid,'node_reconciled',ident)

def graph(c,uid,wid):
 core.access(c,uid,wid)
 nodes=[dict(zip(('id','kind','name','source','created','updated','revision'),r)) for r in c.execute('SELECT id,kind,name,source,created,updated,revision FROM sv56_twin_nodes WHERE workspace_id=? ORDER BY kind,name',(wid,))]
 edges=[dict(zip(('id','from_id','to_id','relation','source','created'),r)) for r in c.execute('SELECT id,from_id,to_id,relation,source,created FROM sv56_twin_edges WHERE workspace_id=? ORDER BY created,id',(wid,))]
 changes=[dict(zip(('operation','object_id','created'),r)) for r in c.execute('SELECT operation,object_id,created FROM sv56_twin_changes WHERE workspace_id=? ORDER BY created DESC LIMIT 50',(wid,))]
 return {'workspace_id':wid,'nodes':nodes,'edges':edges,'changes':changes,'limitations':['Manual, explicitly sourced records only.','Relationships are owner-entered, not inferred causality.','No automatic third-party synchronization.']}

def traverse(c,uid,wid,origin,max_depth=3):
 g=graph(c,uid,wid)
 if origin not in {n['id'] for n in g['nodes']}:raise ValueError('Entity not found')
 if not isinstance(max_depth,int) or max_depth<0 or max_depth>5:raise ValueError('Depth out of bounds')
 seen={origin};front={origin}
 for _ in range(max_depth):
  following={e['to_id'] for e in g['edges'] if e['from_id'] in front};front=following-seen;seen|=front
 return {'nodes':[n for n in g['nodes'] if n['id'] in seen],'edges':[e for e in g['edges'] if e['from_id'] in seen and e['to_id'] in seen]}

def render(c,uid,csrf,wid):
 g=graph(c,uid,wid);e=lambda s:html.escape(str(s),quote=True)
 nodes=''.join('<tr><td>'+e(n['kind'])+'</td><td>'+e(n['name'])+'</td><td>'+e(n['source'])+'</td><td>'+str(n['revision'])+'</td></tr>' for n in g['nodes']) or '<tr><td colspan="4">No business entities recorded.</td></tr>'
 edges=''.join('<tr><td>'+e(x['relation'])+'</td><td>'+e(x['from_id'])+'</td><td>'+e(x['to_id'])+'</td><td>'+e(x['source'])+'</td></tr>' for x in g['edges']) or '<tr><td colspan="4">No relationships recorded.</td></tr>'
 opts=''.join('<option value="'+e(n['id'])+'">'+e(n['kind']+': '+n['name'])+'</option>' for n in g['nodes'])
 types=''.join('<option>'+e(t)+'</option>' for t in TYPES)
 rels=''.join('<option>'+e(t)+'</option>' for t in RELATIONS)
 hidden='<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'">'
 return '<section class="panel"><h1>Sovereign Digital Twin 2.0</h1><p>Typed, sourced, workspace-isolated business graph. No inferred relationships or live connectors.</p><a href="/sovereign-twin-v56.json?w='+quote(wid,safe='')+'">Export graph JSON</a></section><section class="panel"><h2>Add entity</h2><form method="post" action="/sovereign-twin-v56">'+hidden+'<input type="hidden" name="action" value="node"><label>Type<select name="kind">'+types+'</select></label><label>Name<input name="name" maxlength="120" required></label><label>Source reference<input name="source" maxlength="120" required placeholder="Manual owner entry / source ID"></label><button>Add entity</button></form></section><section class="panel"><h2>Link entities</h2><form method="post" action="/sovereign-twin-v56">'+hidden+'<input type="hidden" name="action" value="edge"><label>From<select name="from_id">'+opts+'</select></label><label>Relationship<select name="relation">'+rels+'</select></label><label>To<select name="to_id">'+opts+'</select></label><label>Source<input name="source" maxlength="120" required></label><button>Link entities</button></form><p>Only compatible typed relationships are accepted.</p></section><section class="panel"><h2>Entities ('+str(len(g['nodes']))+')</h2><div class="scroll"><table><tr><th>Type</th><th>Name</th><th>Source</th><th>Revision</th></tr>'+nodes+'</table></div></section><section class="panel"><h2>Relationships ('+str(len(g['edges']))+')</h2><div class="scroll"><table><tr><th>Relation</th><th>From ID</th><th>To ID</th><th>Source</th></tr>'+edges+'</table></div></section>'
