"""V40 Genesis Reborn: safe SQLite diagnostics, indexing, and local maintenance.

No automatic destructive migrations, vacuum, or live restore. Local operator CLI only.
"""
import argparse, html, json, os, sqlite3, sys, time
from pathlib import Path

INDEX_SPECS = (
 ('sessions','user_id','idx_v40_sessions_user'),
 ('sessions','expires','idx_v40_sessions_expiry'),
 ('reports','user_id,created','idx_v40_reports_user_created'),
 ('deliveries','user_id,status','idx_v40_deliveries_user_status'),
 ('empire_members','user_id,workspace_id','idx_v40_members_user_workspace'),
 ('prime_apps','workspace_id','idx_v40_apps_workspace'),
 ('prime_records','workspace_id,app_id','idx_v40_records_workspace_app'),
 ('first_contact_issues','workspace_id','idx_v40_pilot_issues_workspace'),
)

def install_indexes(c):
    """Only create indexes for tables and columns already present; idempotent."""
    if not isinstance(c,sqlite3.Connection):raise ValueError('SQLite only')
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    created=[];skipped=[]
    for table,columns,name in INDEX_SPECS:
        if table not in tables:skipped.append(name);continue
        existing={r[1] for r in c.execute(f'PRAGMA table_info("{table}")')}
        if not set(columns.split(',')).issubset(existing):skipped.append(name);continue
        was_present=bool(c.execute('SELECT 1 FROM sqlite_master WHERE type="index" AND name=?',(name,)).fetchone())
        c.execute(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns})')
        if not was_present:created.append(name)
    return {'created':created,'skipped':skipped}

def inspect(path):
    """Read-only inspection, no schema changes and no DB creation."""
    path=Path(path)
    if not path.is_file():return {'ok':False,'error':'Database file does not exist','database':str(path)}
    try:
        with sqlite3.connect(f'file:{path.resolve().as_posix()}?mode=ro',uri=True,timeout=5) as c:
            integrity=c.execute('PRAGMA quick_check').fetchone()[0]
            foreign_keys=c.execute('PRAGMA foreign_key_check').fetchmany(20)
            tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            indexes=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_v40_%' ORDER BY name")]
            page_count=c.execute('PRAGMA page_count').fetchone()[0]
            page_size=c.execute('PRAGMA page_size').fetchone()[0]
            freelist=c.execute('PRAGMA freelist_count').fetchone()[0]
        return {'ok':integrity=='ok' and not foreign_keys,'integrity':integrity,'foreign_key_violations':len(foreign_keys),'table_count':len(tables),'v40_indexes':indexes,'database_bytes':path.stat().st_size,'allocated_bytes':page_count*page_size,'reclaimable_bytes_estimate':freelist*page_size,'database':str(path)}
    except (sqlite3.DatabaseError,OSError) as exc:return {'ok':False,'error':str(exc)[:200],'database':str(path)}

def render(data_root):
    """Operator-only read-only overview, never executes maintenance from web."""
    root=Path(data_root);status=inspect(root/'portal.sqlite3')
    esc=lambda s:html.escape(str(s),quote=True)
    rows=''.join('<tr><th>'+esc(k.replace('_',' ').title())+'</th><td>'+esc(v)+'</td></tr>' for k,v in status.items() if k!='database' and k!='v40_indexes')
    indexes=''.join('<li><code>'+esc(name)+'</code></li>' for name in status.get('v40_indexes',[])) or '<li>None detected</li>'
    return ('<section class="hero"><p class="eyebrow">VELXTRIA V40 / GENESIS REBORN</p><h1>Platform health & maintenance</h1><p>Read-only local SQLite diagnostics. No production certification or automated destructive operations.</p></section>'
      '<section class="panel"><h2>Database diagnostics</h2><table>'+rows+'</table></section>'
      '<section class="panel"><h2>Installed V40 indexes</h2><ul>'+indexes+'</ul></section>'
      '<section class="panel"><h2>Operator commands</h2><p><code>python genesis_reborn_v40.py check</code></p><p><code>python genesis_reborn_v40.py optimize</code></p><p><code>python -m unittest discover -p "test_*.py"</code></p><p>Optimize adds only compatible indexes and runs ANALYZE. Back up your database first. Maintenance is not available from this web page.</p></section>')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','optimize']);parser.add_argument('--db',default=str(Path(os.environ.get('VELXTRIA_DATA_DIR',Path(__file__).resolve().parent))/'portal.sqlite3'));args=parser.parse_args()
    if args.action=='optimize':
        if not Path(args.db).is_file():parser.error('Database does not exist; refusing to create it')
        with sqlite3.connect(args.db,timeout=15) as c:
            outcome=install_indexes(c);c.execute('ANALYZE')
        print(json.dumps({'optimization':outcome,'health':inspect(args.db)},indent=2))
    else:print(json.dumps(inspect(args.db),indent=2))
    return 0 if inspect(args.db).get('ok') else 1
if __name__=='__main__':sys.exit(main())
