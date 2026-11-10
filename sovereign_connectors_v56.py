"""V56.11 Universal Business Connectors: safe read-only adapter registry and reviewed CSV snapshots.
No external network, credentials, scheduled jobs or remote API writes are implemented.
"""
import csv, io, json, hashlib, html, secrets, time, math, re
from urllib.parse import quote
import sovereign_v56 as core

MAX_BYTES=1024*1024
MAX_ROWS=5000
HEADERS=['external_id','period','revenue','expenses','leads','customers']
ADAPTERS={'csv_metrics_v1':{'label':'Read-only business metrics CSV','headers':HEADERS,'transport':'manual_upload','read_only':True}}

def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS sv56_connector_sources(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,name TEXT NOT NULL,adapter TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1)')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_connector_sources_scope ON sv56_connector_sources(workspace_id,created)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_connector_batches(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,source_id TEXT NOT NULL,sha256 TEXT NOT NULL,filename TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,status TEXT NOT NULL,row_count INTEGER NOT NULL,conflict_count INTEGER NOT NULL DEFAULT 0,UNIQUE(source_id,sha256))')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_connector_records(batch_id TEXT NOT NULL,workspace_id TEXT NOT NULL,source_id TEXT NOT NULL,external_id TEXT NOT NULL,period TEXT NOT NULL,revenue REAL NOT NULL,expenses REAL NOT NULL,leads INTEGER NOT NULL,customers INTEGER NOT NULL,PRIMARY KEY(batch_id,external_id))')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_connector_records_scope ON sv56_connector_records(workspace_id,source_id,period)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_connector_events(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,source_id TEXT NOT NULL,batch_id TEXT NOT NULL,actor INTEGER NOT NULL,event TEXT NOT NULL,created INTEGER NOT NULL)')

def event(c,uid,wid,sid,bid,name):
 c.execute('INSERT INTO sv56_connector_events VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(12),wid,sid,bid,uid,name,int(time.time())))
 core.audit(c,uid,wid,'connector_'+name,bid or sid)

def create_source(c,uid,wid,name,adapter='csv_metrics_v1'):
 core.access(c,uid,wid,write=True)
 name=name.strip()
 if not 2<=len(name)<=100:raise ValueError('Source name must contain 2–100 characters')
 if adapter not in ADAPTERS:raise ValueError('Unsupported connector adapter')
 sid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_connector_sources VALUES(?,?,?,?,?,?,1)',(sid,wid,name,adapter,uid,int(time.time())))
  event(c,uid,wid,sid,'','source_created')
 return sid

def parse(data):
 if not isinstance(data,bytes) or not 0<len(data)<=MAX_BYTES or b'\x00' in data:raise ValueError('CSV must be 1 byte to 1 MB without NUL bytes')
 try:
  reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''),strict=True)
  if reader.fieldnames!=HEADERS:raise ValueError('Expected headers: '+', '.join(HEADERS))
  rows=[];seen=set()
  for row in reader:
   if len(rows)>=MAX_ROWS:raise ValueError('Too many rows')
   if None in row or any(row.get(k) is None for k in HEADERS):raise ValueError('Malformed CSV row')
   eid=row['external_id'].strip();period=row['period'].strip()
   if not 1<=len(eid)<=100 or eid in seen:raise ValueError('Invalid or repeated external ID')
   if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])',period):raise ValueError('Invalid YYYY-MM period')
   seen.add(eid)
   amounts=[]
   for field in ('revenue','expenses'):
    value=float(row[field]);
    if not math.isfinite(value) or not 0<=value<=1e12:raise ValueError('Invalid monetary value')
    amounts.append(value)
   counts=[]
   for field in ('leads','customers'):
    value=row[field].strip()
    if not re.fullmatch(r'0|[1-9][0-9]*',value) or int(value)>1000000000:raise ValueError('Invalid count')
    counts.append(int(value))
   if counts[1]>counts[0]:raise ValueError('Customers exceed leads')
   rows.append((eid,period,*amounts,*counts))
  if not rows:raise ValueError('No rows')
  return rows
 except (UnicodeError,csv.Error,OverflowError,ValueError) as e:raise ValueError('Invalid connector CSV: '+str(e)) from e

def source(c,uid,wid,sid,write=False):
 core.access(c,uid,wid,write=write)
 row=c.execute('SELECT id,name,adapter,enabled FROM sv56_connector_sources WHERE workspace_id=? AND id=?',(wid,sid)).fetchone()
 if not row:raise ValueError('Connector source not found')
 return row

def preview(c,uid,wid,sid,data):
 source(c,uid,wid,sid,write=True)
 rows=parse(data);digest=hashlib.sha256(data).hexdigest()
 prior=c.execute('SELECT id,status FROM sv56_connector_batches WHERE source_id=? AND sha256=?',(sid,digest)).fetchone()
 existing={eid:(period,r,e,l,cu) for eid,period,r,e,l,cu in c.execute("SELECT r.external_id,r.period,r.revenue,r.expenses,r.leads,r.customers FROM sv56_connector_records r JOIN sv56_connector_batches b ON b.id=r.batch_id WHERE r.source_id=? AND b.status='applied' ORDER BY b.created,b.id",(sid,))}
 additions=[];unchanged=[];conflicts=[]
 for eid,period,r,e,l,cu in rows:
  old=existing.get(eid);new=(period,r,e,l,cu)
  if old is None:additions.append(eid)
  elif old==new:unchanged.append(eid)
  else:conflicts.append({'external_id':eid,'previous_period':old[0],'incoming_period':period})
 return {'source_id':sid,'sha256':digest,'row_count':len(rows),'new_ids':additions,'unchanged_ids':unchanged,'conflicts':conflicts,'duplicate_batch':bool(prior),'limitations':['Conflicting external IDs are never overwritten.','No remote API calls or credentials.','Snapshots remain separate from verified Sovereign metric imports until reviewed.']}

def ingest(c,uid,wid,sid,filename,data):
 core.access(c,uid,wid,write=True)
 row=source(c,uid,wid,sid,write=True)
 if not row[3]:raise ValueError('Source is disabled')
 if not filename.lower().endswith('.csv') or len(filename)>120:raise ValueError('Provide a CSV filename')
 p=preview(c,uid,wid,sid,data)
 if p['duplicate_batch']:raise ValueError('This snapshot was already staged')
 rows=parse(data);bid=secrets.token_hex(12)
 with c:
  c.execute('INSERT INTO sv56_connector_batches VALUES(?,?,?,?,?,?,?,?,?,?)',(bid,wid,sid,p['sha256'],filename,uid,int(time.time()),'staged',len(rows),len(p['conflicts'])))
  c.executemany('INSERT INTO sv56_connector_records VALUES(?,?,?,?,?,?,?,?,?)',[(bid,wid,sid,*r) for r in rows])
  event(c,uid,wid,sid,bid,'snapshot_staged')
 return bid

def apply(c,uid,wid,bid):
 core.access(c,uid,wid,owner=True)
 row=c.execute('SELECT source_id,status FROM sv56_connector_batches WHERE workspace_id=? AND id=?',(wid,bid)).fetchone()
 if not row or row[1]!='staged':raise ValueError('Staged batch not found')
 sid=row[0];source(c,uid,wid,sid)
 incoming=c.execute('SELECT external_id,period,revenue,expenses,leads,customers FROM sv56_connector_records WHERE batch_id=? AND workspace_id=?',(bid,wid)).fetchall()
 existing={eid:(period,r,e,l,cu) for eid,period,r,e,l,cu in c.execute("SELECT r.external_id,r.period,r.revenue,r.expenses,r.leads,r.customers FROM sv56_connector_records r JOIN sv56_connector_batches b ON b.id=r.batch_id WHERE r.source_id=? AND b.status='applied' ORDER BY b.created,b.id",(sid,))}
 conflicts=[eid for eid,*values in incoming if eid in existing and existing[eid]!=tuple(values)]
 if conflicts:raise ValueError('Conflicting source records require manual reconciliation: '+', '.join(conflicts[:5]))
 with c:
  updated=c.execute("UPDATE sv56_connector_batches SET status='applied',conflict_count=0 WHERE id=? AND workspace_id=? AND status='staged'",(bid,wid)).rowcount
  if updated!=1:raise ValueError('Concurrent batch update')
  event(c,uid,wid,sid,bid,'snapshot_applied')
 return {'batch_id':bid,'status':'applied','rows':len(incoming)}

def history(c,uid,wid):
 core.access(c,uid,wid)
 sources=[{'id':i,'name':n,'adapter':a,'enabled':bool(en)} for i,n,a,en in c.execute('SELECT id,name,adapter,enabled FROM sv56_connector_sources WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 batches=[{'id':i,'source_id':sid,'filename':f,'status':s,'row_count':n,'conflict_count':x,'sha256':sha} for i,sid,f,s,n,x,sha in c.execute('SELECT id,source_id,filename,status,row_count,conflict_count,sha256 FROM sv56_connector_batches WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 events=[{'source_id':sid,'batch_id':bid,'event':ev,'timestamp':ts} for sid,bid,ev,ts in c.execute('SELECT source_id,batch_id,event,created FROM sv56_connector_events WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 return {'adapters':ADAPTERS,'sources':sources,'batches':batches,'events':events,'limitations':['Manual read-only CSV snapshot adapter only.','No OAuth, external API connectivity, automated polling, or writes to external platforms.','Staged records are isolated from core metrics.']}

def render(c,uid,csrf,wid):
 data=history(c,uid,wid);e=lambda x:html.escape(str(x),quote=True)
 source_options=''.join('<option value="'+e(s['id'])+'">'+e(s['name'])+'</option>' for s in data['sources'])
 rows=''.join('<tr><td>'+e(b['filename'])+'</td><td>'+e(b['status'])+'</td><td>'+str(b['row_count'])+'</td><td>'+str(b['conflict_count'])+'</td><td>'+ ('<form method="post" action="/sovereign-connectors-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="apply"><input type="hidden" name="batch_id" value="'+e(b['id'])+'"><button>Approve snapshot</button></form>' if b['status']=='staged' else '')+'</td></tr>' for b in data['batches']) or '<tr><td colspan="5">No snapshots yet.</td></tr>'
 return '<section class="panel"><h1>Universal Business Connectors — V56.11</h1><p>Read-only manual CSV adapter with staged snapshots, source provenance, owner approval, duplicate detection and fail-closed conflicts. No external API integrations yet.</p><a href="/sovereign-connectors-v56.json?w='+quote(wid,safe='')+'">Export connector history</a></section><section class="panel"><h2>Register source</h2><form method="post" action="/sovereign-connectors-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="create"><input name="name" maxlength="100" required placeholder="Source name"><button>Register read-only source</button></form></section><section class="panel"><h2>Stage snapshot</h2><p>CSV header: <code>'+e(','.join(HEADERS))+'</code>. Paste UTF-8 CSV data (max 1 MB, 5000 rows).</p><form method="post" action="/sovereign-connectors-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="stage"><select name="source_id" required>'+source_options+'</select><input name="filename" value="snapshot.csv" required><textarea name="csv_data" rows="7" required></textarea><button>Stage snapshot</button></form></section><section class="panel"><h2>Snapshot history</h2><table><tr><th>Filename</th><th>Status</th><th>Rows</th><th>Conflicts</th><th>Review</th></tr>'+rows+'</table></section>'
