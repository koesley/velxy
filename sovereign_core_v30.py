"""V30 local release gate: explicit evidence, no production certification."""
import html, os, sqlite3
from pathlib import Path
import empire_v19, foundation_v26, integration_v29

def esc(v): return html.escape(str(v), quote=True)

def assess(c,uid,wid,db_path):
    if not empire_v19.role(c,uid,wid): raise ValueError('Workspace unavailable')
    results=[]
    def add(name,ok,detail):results.append((name,'PASS' if ok else 'BLOCKED',detail))
    schema=integration_v29.diagnostics(c)
    missing=[name for name,ok in schema if not ok]
    add('Required module schemas',not missing,'All expected tables present' if not missing else 'Missing: '+', '.join(missing))
    try:
        check=foundation_v26.integrity(db_path)
        add('SQLite integrity',check['ok'],'Integrity check returned '+', '.join(check['messages']))
    except (OSError,sqlite3.Error,ValueError) as e:
        add('SQLite integrity',False,type(e).__name__)
    add('Local-only deployment',os.getenv('VELXTRIA_LOCAL_STUDIO')=='1' and os.getenv('VELXTRIA_DEPLOYMENT_MODE','local')=='local','Studio must remain local during pilot testing')
    add('Full end-to-end browser test',False,'Not yet executed or certified by this dashboard')
    add('External security review',False,'Independent authentication, authorization and deployment audit required')
    add('Production release',False,'Blocked until outstanding checks are verified independently')
    return results

def render(c,uid,wid,db_path):
    ws=foundation_v26.workspaces(c,uid)
    if not ws:return '<section class="panel"><h1>Sovereign Core V30</h1><p>Create a workspace first.</p><a href="/empire">Open Empire</a></section>'
    allowed={w[0] for w in ws}
    if not wid:wid=ws[0][0]
    if wid not in allowed:raise ValueError('Workspace unavailable')
    checks=assess(c,uid,wid,db_path)
    rows=''.join('<tr><td>'+esc(k)+'</td><td>'+esc(v)+'</td><td>'+esc(detail)+'</td></tr>' for k,v,detail in checks)
    opts=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
    passing=sum(v=='PASS' for _,v,_ in checks)
    return ('<section class="hero"><p class="eyebrow">VELXTRIA V30 · SOVEREIGN CORE</p><h1>Release readiness, without guesswork.</h1><p>Read-only local verification for the selected workspace. A PASS is a limited technical check, not a security certification.</p></section>'
      '<section class="panel"><form method="get" action="/sovereign-core"><label>Workspace<select name="w">'+opts+'</select></label><button>Inspect</button></form></section>'
      '<section class="panel"><h2>Release gate: NOT READY</h2><p>'+str(passing)+' of '+str(len(checks))+' checks passed. Production release remains blocked.</p><div class="scroll"><table><thead><tr><th>Check</th><th>Status</th><th>Evidence / limitation</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'
      '<section class="panel"><h2>Next steps</h2><p>Run the automated regression suite, test the complete browser journey, review authentication and CSRF protections, then test a restore from a verified backup on a separate copy.</p><p>No customer records are modified by this page.</p><a href="/integration?w='+esc(wid)+'">Customer journey</a> · <a href="/foundation?w='+esc(wid)+'">Verified backup tools</a></section>')
