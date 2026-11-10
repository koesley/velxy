"""VELXTRIA V26 Foundation: local-only workspace overview and verified SQLite backup."""
import hashlib,html,os,sqlite3,time
from pathlib import Path
import empire_v19

def esc(v):return html.escape(str(v),quote=True)
def workspaces(c,uid):
 return c.execute("SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.name",(uid,)).fetchall()

def overview(c,uid,wid):
 if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 tables={'Applications':('prime_apps','workspace_id'),'Automation rules':('autonomy_rules','workspace_id'),'Goals':('nexus_goals','workspace_id'),'Strategies':('nexus_strategies','workspace_id')}
 counts={}
 for label,(table,col) in tables.items():
  try:counts[label]=c.execute('SELECT COUNT(*) FROM '+table+' WHERE '+col+'=?',(wid,)).fetchone()[0]
  except sqlite3.OperationalError:counts[label]='Unavailable'
 return counts

def integrity(db_path):
 p=Path(db_path)
 if not p.is_file():raise ValueError('Database not found')
 # URI read-only; no schema migrations and no database writes.
 with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5) as c:
  results=[r[0] for r in c.execute('PRAGMA integrity_check').fetchall()]
 return {'ok':results==['ok'],'messages':results[:5],'bytes':p.stat().st_size}

def backup(db_path,uid,backup_root):
 p=Path(db_path).resolve();root=Path(backup_root).resolve()
 if not p.is_file():raise ValueError('Database not found')
 root.mkdir(mode=0o700,parents=True,exist_ok=True)
 stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
 target=root/('velxtria-backup-'+stamp+'-'+os.urandom(4).hex()+'.sqlite3')
 # Online backup API ensures a transactionally consistent copy even with WAL.
 try:
  with sqlite3.connect(str(p),timeout=10) as source,sqlite3.connect(str(target)) as dest:
   source.backup(dest)
  check=integrity(target)
  if not check['ok']:raise ValueError('Backup integrity verification failed')
  digest=hashlib.sha256(target.read_bytes()).hexdigest()
  (target.with_suffix('.sha256')).write_text(digest+'  '+target.name+'\n',encoding='utf-8')
  try:os.chmod(target,0o600);os.chmod(target.with_suffix('.sha256'),0o600)
  except OSError:pass
  return {'file':target.name,'sha256':digest,'bytes':check['bytes']}
 except Exception:
  target.unlink(missing_ok=True)
  raise

def readiness(c,db_path):
 status=integrity(db_path)
 return [('SQLite integrity', 'PASS' if status['ok'] else 'FAIL'),('Local database', 'PASS'),('Legacy module tenant-isolation audit','NOT VERIFIED'),('Browser end-to-end testing','NOT VERIFIED'),('Production authentication review','NOT VERIFIED'),('Production deployment','NOT READY')]

def render(c,uid,csrf,wid='',message='',db_path=None):
 ws=workspaces(c,uid)
 if not ws:return '<section class="panel"><h1>Foundation V26</h1><p>Create an Empire workspace first.</p><a href="/empire">Open Empire</a></section>'
 ids={w[0] for w in ws}
 if not wid:wid=ws[0][0]
 if wid not in ids:raise ValueError('Workspace unavailable')
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if wid==w[0] else '')+'>'+esc(w[1])+'</option>' for w in ws)
 cards=''.join('<div class="panel"><h3>'+esc(k)+'</h3><h2>'+esc(v)+'</h2></div>' for k,v in overview(c,uid,wid).items())
 links=''.join('<a href="'+url+'?w='+esc(wid)+'">'+esc(label)+'</a> &nbsp; ' for label,url in [('Applications','/genesis-prime'),('Automations','/autonomy'),('Oracle','/oracle'),('Strategies','/nexus-intelligence')])
 report=readiness(c,db_path) if db_path else []
 rows=''.join('<tr><td>'+esc(k)+'</td><td>'+esc(v)+'</td></tr>' for k,v in report)
 return ('<section class="hero"><p class="eyebrow">VELXTRIA V26 · PROJECT FOUNDATION</p><h1>Business Command Center</h1><p>One workspace overview, verified backups, and honest readiness reporting.</p></section>'
 '<section class="panel"><form method="get" action="/foundation"><label>Business workspace<select name="w">'+options+'</select></label><button>Switch workspace</button></form></section>'
 +('<section class="panel"><p>'+esc(message)+'</p></section>' if message else '')
 +'<div class="stats">'+cards+'</div><section class="panel"><h2>Your business tools</h2>'+links+'</section>'
 +'<section class="panel"><h2>Local database protection</h2><p>Backup uses SQLite online backup, validates the resulting file, and writes a SHA-256 checksum. Backups remain on your computer and are not included in project ZIP downloads.</p><form method="post" action="/foundation"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="backup"><button>Create verified backup</button></form></section>'
 +'<section class="panel"><h2>Readiness report</h2><table><tbody>'+rows+'</tbody></table><p>Passing database integrity does not establish security or production readiness.</p></section>')
