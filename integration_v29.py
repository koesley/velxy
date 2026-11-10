"""V29 Integration: read-only, tenant-safe customer journey and module diagnostics."""
import html
import empire_v19
import foundation_v26
import launchpad_v27


def esc(value):
 return html.escape(str(value),quote=True)

STAGES = (
 ('Workspace created', '/empire', 'A business workspace is available.'),
 ('Application published', '/genesis-prime', 'Publish an application for your business.'),
 ('First record saved', '/genesis-prime', 'Enter a sample record into your application.'),
 ('Business goal defined', '/nexus-intelligence', 'Define a measurable goal.'),
 ('Pilot feedback collected', '/launchpad', 'Collect written feedback from a trial.'),
)

REQUIRED_TABLES = ('empire_workspaces','empire_members','prime_apps','prime_records','autonomy_rules','nexus_goals','nexus_strategies','launchpad_pilots','launchpad_feedback')

def diagnostics(c):
 """Schema presence is not a functional, security, or production readiness certification."""
 found={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 return [(name, name in found) for name in REQUIRED_TABLES]

def journey(c,uid,wid):
 if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 base=launchpad_v27.evidence(c,wid)
 if len(base)!=3:raise ValueError('Unexpected onboarding evidence format')
 feedback=c.execute('SELECT COUNT(*) FROM launchpad_feedback WHERE workspace_id=?',(wid,)).fetchone()[0]
 return [True, bool(base[0][1]),bool(base[1][1]),bool(base[2][1]),feedback>0]

def render(c,uid,wid=''):
 ws=foundation_v26.workspaces(c,uid)
 if not ws:
  return '<section class="panel"><h1>V29 Integration</h1><p>Create your business workspace to begin the customer journey.</p><a href="/empire">Create workspace</a></section>'
 allowed={w[0] for w in ws}
 if not wid:wid=ws[0][0]
 if wid not in allowed:raise ValueError('Workspace unavailable')
 name=next(w[1] for w in ws if w[0]==wid)
 checks=journey(c,uid,wid)
 complete=sum(checks)
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
 steps=''.join('<li><strong>'+('✓ ' if done else '○ ')+esc(title)+'</strong><p>'+esc(description)+'</p><a href="'+url+'?w='+esc(wid)+'">'+('Review' if done else 'Continue')+' →</a></li>' for (title,url,description),done in zip(STAGES,checks))
 schema=diagnostics(c)
 rows=''.join('<tr><td>'+esc(name)+'</td><td>'+('Present' if ok else 'Missing')+'</td></tr>' for name,ok in schema)
 return ('<div class="v29"><section class="hero"><p class="eyebrow">VELXTRIA V29 · PROJECT INTEGRATION</p><h1>One connected customer journey.</h1><p>Follow each step from workspace setup to actual pilot feedback. All checks use saved data from your selected business workspace.</p></section>'
 '<section class="panel"><h2>Selected workspace: '+esc(name)+'</h2><form action="/integration" method="get"><label>Switch workspace<select name="w">'+options+'</select></label><button>Switch</button></form></section>'
 '<section class="panel"><h2>Journey progress: '+str(complete)+' / '+str(len(STAGES))+'</h2><progress value="'+str(complete)+'" max="'+str(len(STAGES))+'" aria-label="Customer journey completion"></progress><ol class="v29-steps">'+steps+'</ol></section>'
 '<section class="panel"><h2>Module schema diagnostics</h2><p>Read-only checks confirm that key SQLite tables exist. They do not prove module behavior, security, or production readiness.</p><div class="scroll"><table><thead><tr><th>Component table</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'
 '<section class="panel"><h2>Release limitations</h2><p>Local pilot only. No automatic production launch, customer invitation, payment activation, or external access. Full browser integration and security audits are still required.</p><a href="/ascension?w='+esc(wid)+'">Return to command center →</a></section></div>')

CSS='\n.v29{max-width:1050px;margin:auto}.v29 .v29-steps{display:grid;gap:12px;list-style:none;padding:0;counter-reset:journey}.v29 .v29-steps li{padding:16px;border:1px solid rgba(165,133,245,.3);border-radius:12px}.v29 .v29-steps p{margin:8px 0;color:#bdb4cc}.v29 progress{width:100%;height:16px;accent-color:#b49aff}.v29 .v29-steps a{color:#b49aff}\n'
