"""VELXTRIA customer portal with public landing page and private preview guard."""
import base64, csv, hashlib, hmac, html, io, json, os, secrets, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.parse, zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread, Event
import payhip_integration
import persistent
import agent_core
import license_verification
import subscriptions
import site_stats
import btcpay_integration
import btcpay_mainnet
import referrals
import demo_shares
import demo_leads
import trust_pages
import notifications
import password_reset
import sales_pipeline
import sovereign_ascension
import ascension_recovery
import ascension_followups
import ascension_command_center
import ascension_next_actions
import ascension_executive_briefing
import ascension_workflows
import business_v3
import business_v4
import intelligence_v45
import operator_v5
import mission_v52
import mission_v53
import mission_v55
import singularity_v6
import omni_v7
import sovereign_v8
import constellation_v9
import trinity_v10
import recovery_v11
import omnipotence_v12
import singularity_x_v13
import prometheus_v14
import omega_v15
import evolution_v16
import phoenix_v17
import infinity_v18
import apex_v37
import atlas_v38
import catalyst_v39
import genesis_reborn_v40
import nexus_reforged_v41
import infinity_engine_v42
import autonomous_core_v43
import hyperion_v47
import singularity_v50
import ascendancy_v51
import omega_intelligence_v55
import sovereign_v56
import sovereign_intelligence_v56
import sovereign_sync_v56
import sovereign_execution_v56
import sovereign_future_v56
import sovereign_connectors_v56
import sovereign_genesis_v56
import sovereign_opportunities_v57
import business_os_v59
import business_agents_v59
import business_intelligence_v60
import agent_engine_v61
import business_collaboration_v62
import workflow_v63
import customer_assistant_v64
import integrations_v65
import native_integrations_v66
import hubspot_v67
import sync_control_v68
import hubspot_oauth_v70
import integration_health_v72
import sovereign_business_graph_v57
import sovereign_lab_v57
import sovereign_council_v57
import sovereign_omniverse_v57
import sovereign_nexus_v56
import sovereign_workflow_runtime_v56
import sovereign_workflows_v56
import sovereign_unified_v56
import sovereign_command_v56
import sovereign_guardian_v56
import sovereign_executive_v56
import sovereign_memory_v56
import sovereign_strategy_v56
import sovereign_execution_v56
import sovereign_opportunities_v56
import sovereign_twin_v56
import aegis_v54
import sentinel_v53
import titan_intelligence_v52
import omniscience_v49
import quantum_command_v48
import synapse_v44
import neural_network_v45
import evolution_engine_v46
import empire_v19
import genesis_prime_v20
import architect_v21
import autonomy_v22
import sentience_v23
import oracle_v24
import nexus_v25
import foundation_v26
import launchpad_v27
import ascension_v28
import integration_v29
import sovereign_core_v30
import first_contact_v31
import horizon_v32
import evolutionary_core_v33
import sentinel_v34
import titanium_v36
import sovereign_gate_v35
import site_studio
import revenue_priority_workbench
import revenue_priority_live
import revenue_followups_v23
import revenue_conversion_v24
import revenue_command_v25
import revenue_brief_v26
import revenue_goals_v27
import revenue_gap_v28
import revenue_execution_v29
import revenue_operations_v30
import revenue_recovery_v31
import operations_recovery_v31
import operations_performance_v32
import customer_outcomes_v33
import revenue_attribution_v34
import acquisition_intelligence_v35
import marketing_budget_v36
import campaign_experiments_v37
import experiment_decisions_v38
import campaign_optimization_v39
import optimization_impact_v40
import growth_intelligence_v41
import growth_strategy_v42
import sales_execution_v44

ROOT=Path(__file__).resolve().parent
DELIVERY_ENABLED=notifications.email_configured()
STOP=Event()
DATA_ROOT=Path(os.getenv('VELXTRIA_DATA_DIR',str(ROOT))).resolve()
DATA_ROOT.mkdir(parents=True,exist_ok=True)
DB=DATA_ROOT/'portal.sqlite3'; REPORTS=DATA_ROOT/'customer_reports'; REPORTS.mkdir(exist_ok=True)
MAX_BYTES=5*1024*1024; MAX_MONTHLY=50; LOCK=Lock()
REQUIRED=['Order ID','Order Date','Customer','Product','Quantity','Unit Price','Status','Region']
SITE_DESCRIPTION='VELXTRIA turns messy sales CSVs into clean monthly and product reports for small service businesses. Free demo, no signup. PRO $49/30 days, Bitcoin only.'

def now(): return int(time.time())
_SCHEMA_READY=False
_SCHEMA_LOCK=Lock()

def db():
 global _SCHEMA_READY
 c=persistent.connect(DB)
 if _SCHEMA_READY and not getattr(persistent,'REMOTE',False):
  # The ready flag is per-process, but the local sqlite file can be
  # replaced mid-process (test modules delete their temp data dir, and a
  # local database file can be removed while the server runs). A fresh
  # empty file has no tables, so verify the users table is still there
  # and re-initialize if it is gone. Remote databases cannot be swapped
  # this way, so the probe is local-only. Connections without an execute
  # method (offline test doubles) skip the probe.
  execute=getattr(c,'execute',None)
  if execute is not None:
   try:
    cur=execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    fetchone=getattr(cur,'fetchone',None)
    if fetchone is not None and fetchone() is None:
     _SCHEMA_READY=False
   except Exception:
    pass
 if not _SCHEMA_READY:
  with _SCHEMA_LOCK:
   if not _SCHEMA_READY:
    try:
     _initialize_schema(c)
    except BaseException:
     c.close()
     raise
    _SCHEMA_READY=True
 return c

def _initialize_schema(c):
 # Serialize schema creation across Render instances and deployments.
 # The transaction-scoped lock releases on commit or rollback, including crashes.
 # Guard on the connection itself, not the REMOTE flag: the flag describes
 # the deployment, but this function can be handed a sqlite connection
 # while the flag is set (tests, the Render build), and the Postgres-only
 # lock call crashes on sqlite.
 if isinstance(c, persistent.PgConnection):
  c.execute('SELECT pg_advisory_xact_lock(871329014, 20261120)')
 if persistent.REMOTE:
  c.execute("""CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer', access TEXT NOT NULL DEFAULT 'demo', created INTEGER NOT NULL)""")
 else:
  c.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer', access TEXT NOT NULL DEFAULT 'demo', created INTEGER NOT NULL)""")
 c.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires INTEGER NOT NULL, csrf TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))')
 c.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, filename TEXT NOT NULL, created INTEGER NOT NULL, status TEXT NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, digest TEXT NOT NULL, email_status TEXT NOT NULL DEFAULT 'not_sent', FOREIGN KEY(user_id) REFERENCES users(id))")
 c.execute("CREATE TABLE IF NOT EXISTS report_write_journal (report_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created INTEGER NOT NULL, state TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
 c.execute("CREATE TABLE IF NOT EXISTS deliveries (report_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, recipient TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '', next_attempt INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(report_id) REFERENCES reports(id))")
 c.execute('CREATE TABLE IF NOT EXISTS paid_licenses (license_hash TEXT PRIMARY KEY, license_key TEXT NOT NULL, user_id INTEGER NOT NULL UNIQUE, redeemed_at INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))')
 site_stats.ensure(c)
 payhip_integration.setup(c)
 subscriptions.setup(c)
 referrals.setup(c)
 demo_shares.setup(c)
 demo_leads.setup(c)
 notifications.setup(c)
 password_reset.setup(c)
 business_v3.setup(c)
 business_v4.setup(c)
 operator_v5.setup(c)
 mission_v52.setup(c)
 mission_v53.setup(c)
 mission_v55.setup(c)
 singularity_v6.setup(c)
 omni_v7.setup(c)
 sovereign_v8.setup(c)
 constellation_v9.setup(c)
 trinity_v10.setup(c)
 if not persistent.REMOTE: omnipotence_v12.setup(c)
 if not persistent.REMOTE: singularity_x_v13.setup(c)
 if not persistent.REMOTE: prometheus_v14.setup(c)
 empire_v19.setup(c)
 if not persistent.REMOTE: genesis_prime_v20.setup(c)
 if not persistent.REMOTE: architect_v21.setup(c)
 if not persistent.REMOTE: autonomy_v22.setup(c)
 if not persistent.REMOTE: sentience_v23.setup(c)
 if not persistent.REMOTE: oracle_v24.setup(c)
 if not persistent.REMOTE: nexus_v25.setup(c)
 if not persistent.REMOTE: launchpad_v27.setup(c)
 if not persistent.REMOTE: first_contact_v31.setup(c)
 if not persistent.REMOTE: horizon_v32.setup(c)
 if not persistent.REMOTE: evolutionary_core_v33.setup(c)
 if not persistent.REMOTE: sovereign_gate_v35.setup(c)
 if not persistent.REMOTE: autonomous_core_v43.setup(c)
 if not persistent.REMOTE: synapse_v44.setup(c)
 if not persistent.REMOTE: hyperion_v47.setup(c); quantum_command_v48.setup(c); omniscience_v49.setup(c)
 if not persistent.REMOTE: evolution_engine_v46.setup(c)
 btcpay_integration.setup(c)
 btcpay_mainnet.setup(c)
 agent_core.setup(c)
 if os.getenv("VELXTRIA_LOCAL_STUDIO","0")=="1" and not persistent.REMOTE: site_studio.setup(c)
 sovereign_v56.setup(c)
 if not persistent.REMOTE: sovereign_intelligence_v56.setup(c)
 if not persistent.REMOTE: sovereign_twin_v56.setup(c); sovereign_sync_v56.setup(c); sovereign_opportunities_v56.setup(c); sovereign_strategy_v56.setup(c); sovereign_execution_v56.setup(c); sovereign_memory_v56.setup(c); sovereign_future_v56.setup(c); sovereign_executive_v56.setup(c); sovereign_connectors_v56.setup(c); sovereign_guardian_v56.setup(c); sovereign_genesis_v56.setup(c)
 if not persistent.REMOTE: genesis_reborn_v40.install_indexes(c)
 c.commit()

def persistent_integrity_error():
 if persistent.REMOTE:
  from psycopg import IntegrityError
  return IntegrityError
 return sqlite3.IntegrityError

def pw_hash(password,salt): return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),250000).hex()
def escape(v): return html.escape(str(v),quote=True)
def valid_email(v):return '@' in v and '.' in v.split('@')[-1] and len(v)<255 and '\n' not in v

def shell(title,body,user=None,csrf=''):
 btc_note='Bitcoin payments are verified automatically via BTCPay' if btcpay_mainnet.checkout_enabled() else 'Bitcoin payments require manual confirmation'
 nav=('<a href="/sovereign-unified-v56">✦ Unified Command</a> <a href="/sovereign-genesis-v56">✦ Project Genesis</a> <a href="/sovereign-command-v56">✦ Ask VELXTRIA</a> <a href="/sovereign-guardian-v56">✦ Guardian</a> <a href="/sovereign-connectors-v56">✦ Connectors</a> <a href="/sovereign-executive-v56">✦ Executive Council 2.0</a> <a href="/sovereign-future-v56">✦ Future Simulator</a> <a href="/sovereign-memory-v56">✦ Memory</a> <a href="/sovereign-execution-v56">✦ Execution</a> <a href="/sovereign-strategies-v56">✦ Strategies</a> <a href="/sovereign-opportunities-v56">✦ Opportunities</a> <a href="/sovereign-sync-v56">✦ Twin Sync</a> <a href="/sovereign-twin-v56">✦ Digital Twin</a> <a href="/sovereign-council-v56">✦ Sovereign Council</a> <a href="/sovereign-v56">✦ Sovereign V56</a> <a href="/omega-v55">✦ Omega V55</a> <a href="/aegis-v54">✦ Aegis V54</a> <a href="/sentinel-v53">✦ Sentinel V53</a> <a href="/titan-intelligence">✦ Titan V52</a> <a href="/ascendancy-v51">✦ Ascendancy V51</a> <a href="/singularity-v50">✦ Singularity V50</a> <a href="/nexus-reforged">Command Center</a> <a href="/infinity-engine">Intelligence</a> <a href="/autonomous-core">Experiments</a> <a href="/synapse">Synapse</a> <a href="/omniscience">Omniscience V49</a> <a href="/quantum-command">Quantum V48</a> <a href="/hyperion">Hyperion V47</a> <a href="/neural-network">Neural V45</a> <a href="/evolution-engine">Evolution V46</a> <a href="/">Reports</a> <a href="/workspace">Business</a> <a href="/genesis-prime">Apps</a> <a href="/oracle">Oracle</a> <a href="/atlas">Onboarding</a> <a href="/catalyst">Release checks</a> <a href="/outreach-studio">Outreach Studio</a> <a href="/sales-pipeline">Sales Pipeline</a> <a href="/ascension">Ascension</a> <a href="/ascension-recovery">Recovery</a> <a href="/ascension-followups">Follow-up Studio</a> <a href="/ascension-command">Revenue Command</a> <a href="/ascension-next-actions">Next Actions</a> <a href="/ascension-briefing">Executive Briefing</a> <a href="/ascension-workflows">Workflow Orchestrator</a> <a href="/account">Account</a> <form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button class="link">Sign out</button></form>') if user else '<a href="/login">Sign in</a> <a href="/register">Create demo account</a>'
 return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{escape(SITE_DESCRIPTION)}"><meta property="og:title" content="VELXTRIA — Sales reporting made simple"><meta property="og:description" content="{escape(SITE_DESCRIPTION)}"><meta property="og:type" content="website"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><title>{escape(title)} · VELXTRIA</title><link rel="stylesheet" href="/style.css"><script defer src="/checkout-feedback.js"></script><link rel="stylesheet" href="/site-studio.css"></head><body class="{'workspace-page' if title == 'Business Workspace' else ''}"><header><div class="brand">✦ VELXTRIA <span>BUSINESS PLATFORM</span></div><nav class="velx-nav"><a class="velx-primary" href="/">Home</a><a class="velx-primary" href="/business-os-v59">Business OS</a><a class="velx-primary" href="/revenue-priority">Revenue Priority</a><a class="velx-primary" href="/account">Account</a><details class="velx-more"><summary>Explore platform ▾</summary><div class="velx-more-panel"><a class="velx-more-link" href="/business-os-v59">Business OS</a><a class="velx-more-link" href="/revenue-priority">Revenue Priority</a><a class="velx-more-link" href="/revenue-priority/live">Live Priorities</a><a class="velx-more-link" href="/revenue-followups">Follow-ups</a><a class="velx-more-link" href="/revenue-conversion">Conversion</a><a class="velx-more-link" href="/revenue-command">Revenue Command</a><a class="velx-more-link" href="/revenue-brief">Daily Brief</a><a class="velx-more-link" href="/revenue-goals">Goals</a><a class="velx-more-link" href="/revenue-gap">Gap Plan</a><a class="velx-more-link" href="/revenue-execution">Execution</a><a class="velx-more-link" href="/revenue-operations">Operations</a><a class="velx-more-link" href="/revenue-recovery">Recovery</a><a class="velx-more-link" href="/operations-recovery">Recovery</a><a class="velx-more-link" href="/operations-performance">Performance</a><a class="velx-more-link" href="/customer-outcomes">Outcomes</a><a class="velx-more-link" href="/revenue-sources">Sources</a><a class="velx-more-link" href="/revenue-attribution">Sources</a><a class="velx-more-link" href="/acquisition-intelligence">Acquisition</a><a class="velx-more-link" href="/marketing-budget">Budget Studio</a><a class="velx-more-link" href="/campaign-experiments">Campaign Lab</a><a class="velx-more-link" href="/experiment-decisions">Decisions</a><a class="velx-more-link" href="/campaign-optimization">Optimize</a><a class="velx-more-link" href="/optimization-impact">Impact</a><a class="velx-more-link" href="/growth-intelligence">Growth Center</a><a class="velx-more-link" href="/growth-strategy">Growth Strategy</a><a class="velx-more-link" href="/sales-execution">Sales Execution</a><a class="velx-more-link" href="/sales-pipeline">Sales Pipeline</a><a class="velx-more-link" href="/business-agents-v59">Agents</a><a class="velx-more-link" href="/sovereign-omniverse-v57">Omniverse</a><a class="velx-more-link" href="/sovereign-business-graph-v57">Business Graph</a><a class="velx-more-link" href="/sovereign-opportunities-v57">Opportunity Radar</a><a class="velx-more-link" href="/sovereign-council-v57">Council</a><a class="velx-more-link" href="/sovereign-lab-v57">Decision Lab</a><a class="velx-more-link" href="/sovereign-unified-v56">Command</a><a class="velx-more-link" href="/sovereign-workflows-v56">Workflow Studio</a><a class="velx-more-link" href="/sovereign-nexus-v56">Nexus</a><a class="velx-more-link" href="/sovereign-workflow-runs-v56">Operations</a><a class="velx-more-link" href="/">Reports</a><a class="velx-more-link" href="/sovereign-genesis-v56">Genesis</a><a class="velx-more-link" href="/sovereign-command-v56">Ask VELXTRIA</a><a class="velx-more-link" href="/sovereign-guardian-v56">Guardian</a><a class="velx-more-link" href="/sovereign-executive-v56">Intelligence</a><a class="velx-more-link" href="/sovereign-strategies-v56">Strategies</a><a class="velx-more-link" href="/sovereign-execution-v56">Execution</a>{nav}</div></details></nav></header><main>{body}</main><footer>VELXTRIA private preview · {btc_note} · Never upload sensitive data</footer></body></html>"""


def safe_next(value):
 """Return a safe post-login redirect path, or '/'.

 Only same-site absolute paths are accepted, so a login link can never
 bounce the user to another site.
 """
 if not isinstance(value,str) or not value.startswith('/'):
  return '/'
 # Browsers can normalize backslashes into forward slashes in Location
 # headers. Reject them, control characters, and scheme-relative URLs.
 if value.startswith('//') or '\\' in value or any(ord(ch)<32 or ord(ch)==127 for ch in value):
  return '/'
 return value

def referral_cookie_header(code):
 """Set-Cookie header for a validated referral code (first-party, 30 days)."""
 return ('Set-Cookie', referrals.COOKIE_NAME+'='+code+'; Path=/; Max-Age='
         +str(referrals.COOKIE_MAX_AGE)+'; SameSite=Lax')

def referral_code_from_request(handler):
 """A referral code carried by this request: the ?ref= query first, then the
 referral cookie. Only returns codes that exist, so junk can never attribute
 a signup."""
 q=urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query).get('ref',[''])[0]
 cookie=SimpleCookie()
 try:cookie.load(handler.headers.get('Cookie',''))
 except Exception:pass
 morsel=cookie.get(referrals.COOKIE_NAME)
 code=q or (morsel.value if morsel else '')
 if not referrals.valid_code(code):
  return ''
 with db() as c:
  if referrals.referrer_for_code(c,code) is None:
   return ''
 return code

# Small built-in sample dataset for the public sample report. Clearly sample
# data, never a real customer's data. Three rows are intentionally messy
# (a duplicate order, an invalid date, a zero quantity) so the sample shows
# both accepted and flagged rows, as the real engine does.
SAMPLE_SALES_CSV="""Order ID,Order Date,Customer,Product,Quantity,Unit Price,Status,Region
S-1001,2026-10-03,Sample Customer A,Window Cleaning,2,85.00,Paid,Louisville
S-1002,2026-10-05,Sample Customer B,Deep Cleaning,1,180.00,Paid,Louisville
S-1003,2026-10-12,Sample Customer A,Gutter Cleaning,1,120.00,Paid,Jeffersonville
S-1004,2026-10-20,Sample Customer C,Window Cleaning,3,85.00,Pending,Louisville
S-1005,2026-11-02,Sample Customer B,Deep Cleaning,1,180.00,Paid,Louisville
S-1006,2026-11-09,Sample Customer D,Pressure Washing,1,150.00,Paid,New Albany
S-1001,2026-11-10,Sample Customer E,Window Cleaning,1,85.00,Paid,Louisville
S-1007,not-a-date,Sample Customer F,Deep Cleaning,1,180.00,Paid,Louisville
S-1008,2026-11-15,Sample Customer G,Gutter Cleaning,0,120.00,Paid,Louisville
"""

_SAMPLE_REPORT_HTML=None

def _csv_rows_html(rows):
 if not rows:return ''
 head,body=rows[0],rows[1:]
 out=['<table><thead><tr>'+''.join('<th>'+escape(c)+'</th>' for c in head)+'</tr></thead><tbody>']
 for r in body:out.append('<tr>'+''.join('<td>'+escape(c)+'</td>' for c in r)+'</tr>')
 out.append('</tbody></table>')
 return ''.join(out)

def _csv_table_html(path):
 with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
 return _csv_rows_html(rows)

def _read_csv_rows(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.reader(f))

def report_summaries_html(monthly_rows,product_rows,stats):
 """Monthly + product summary tables with the headline stats, as shown on
 the landing page sample report and the instant demo result."""
 return ('<div class="v8-sample-tables"><div><h4>Monthly summary</h4>'+_csv_rows_html(monthly_rows)+'</div><div><h4>Product summary</h4>'+_csv_rows_html(product_rows)+'</div></div><p class="v8-sample-stats">'+' · '.join(escape(l) for l in stats)+'</p>')

def sample_report_html():
 """Render the public sample report with the real report engine.

 Runs automate.py on the small built-in sample dataset and renders the
 monthly and product summaries it produces. Cached per process; any failure
 returns '' so the landing page still renders.
 """
 global _SAMPLE_REPORT_HTML
 if _SAMPLE_REPORT_HTML is not None:return _SAMPLE_REPORT_HTML
 _SAMPLE_REPORT_HTML=''
 try:
  report=run_report_engine(SAMPLE_SALES_CSV.encode('utf-8'))
  _SAMPLE_REPORT_HTML=report_summaries_html(report['monthly_rows'],report['product_rows'],report['stats'])
 except Exception:
  _SAMPLE_REPORT_HTML=''
 return _SAMPLE_REPORT_HTML

# The five files the report engine produces for every report.
REPORT_FILES=['cleaned_sales.csv','rejected_rows.csv','monthly_summary.csv','product_summary.csv','run_summary.txt']

# Headline lines from run_summary.txt shown on screen (same lines the demo
# and the report view render, so the numbers always match the ZIP).
_SUMMARY_STAT_PREFIXES=('Source rows:','Accepted rows:','Rejected rows:','Paid revenue')

def validate_csv_upload(filename,data,columns_hint='Expand the required headers on the dashboard.'):
 """Shared upload validation for the dashboard upload and the anonymous demo.

 Returns the decoded CSV text. Raises ValueError with the same messages the
 dashboard upload has always shown, so existing behaviour is unchanged.
 """
 if not filename.lower().endswith('.csv') or not data or len(data)>MAX_BYTES:
  raise ValueError('Upload one nonempty CSV file up to 5 MB.')
 if b'\x00' in data:raise ValueError('Invalid CSV file.')
 try:decoded=data.decode('utf-8-sig')
 except UnicodeError:raise ValueError('Could not read this file as UTF-8 text.')
 reader=csv.DictReader(io.StringIO(decoded))
 if reader.fieldnames!=REQUIRED:raise ValueError('Incorrect columns. '+columns_hint)
 if len(decoded.splitlines())>20001:raise ValueError('Limit is 20,000 lines per upload.')
 return decoded

def run_report_engine(data):
 """Run the real report engine on raw CSV bytes.

 Returns {'zip_bytes','accepted','rejected','stats','monthly_rows',
 'product_rows','summary'}. Raises ValueError on any processing failure.
 Nothing is persisted: the caller decides what to keep.
 """
 with tempfile.TemporaryDirectory() as t:
  work=Path(t);shutil.copy2(ROOT/'automate.py',work/'automate.py');(work/'messy_sales_input.csv').write_bytes(data)
  result=subprocess.run([sys.executable,'-I',str(work/'automate.py')],cwd=work,timeout=30,capture_output=True,text=True)
  if result.returncode:raise ValueError('Processing failed: '+(result.stderr or result.stdout)[-300:])
  out=work/'output'
  if not all((out/f).exists() for f in REPORT_FILES):raise ValueError('Missing report output')
  def rowcount(path):
   with path.open(encoding='utf-8-sig',newline='') as f:return max(0,sum(1 for _ in csv.reader(f))-1)
  accepted=rowcount(out/'cleaned_sales.csv');rejected=rowcount(out/'rejected_rows.csv')
  summary=(out/'run_summary.txt').read_text(encoding='utf-8')
  stats=[l for l in summary.splitlines() if l.startswith(_SUMMARY_STAT_PREFIXES)]
  archive=io.BytesIO()
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for f in REPORT_FILES:z.write(out/f,arcname=f)
  return {'zip_bytes':archive.getvalue(),'accepted':accepted,'rejected':rejected,'stats':stats,'monthly_rows':_read_csv_rows(out/'monthly_summary.csv'),'product_rows':_read_csv_rows(out/'product_summary.csv'),'summary':summary}

# Anonymous demo downloads: ZIP bytes held in memory only, keyed by a random
# token, expiring after 10 minutes. Nothing is written to disk or the
# database, so a demo never creates an account, a report row, or a stored
# file. Capped so a burst of demos cannot grow memory without bound.
DEMO_ZIP_TTL=600
DEMO_ZIP_MAX=25
DEMO_COOKIE='velxtria_demo'
_DEMO_ZIPS={}
_DEMO_ZIPS_LOCK=Lock()

def store_demo_zip(zip_bytes,accepted,rejected,filename):
 token=secrets.token_urlsafe(24);now_s=time.time()
 with _DEMO_ZIPS_LOCK:
  for key in [k for k,(_,exp,*_rest) in _DEMO_ZIPS.items() if exp<=now_s]:del _DEMO_ZIPS[key]
  while len(_DEMO_ZIPS)>=DEMO_ZIP_MAX:del _DEMO_ZIPS[min(_DEMO_ZIPS,key=lambda k:_DEMO_ZIPS[k][1])]
  _DEMO_ZIPS[token]=(zip_bytes,now_s+DEMO_ZIP_TTL,accepted,rejected,filename)
 return token

def take_demo_zip(token):
 if not token:return None
 with _DEMO_ZIPS_LOCK:
  entry=_DEMO_ZIPS.get(token)
  if not entry:return None
  data,exp,*_=entry
  if exp<=time.time():
   del _DEMO_ZIPS[token]
   return None
  return data

def peek_demo_zip(token):
 """A demo entry without removing it, or None when unknown or expired."""
 if not token:return None
 with _DEMO_ZIPS_LOCK:
  entry=_DEMO_ZIPS.get(token)
  if not entry:return None
  if entry[1]<=time.time():
   del _DEMO_ZIPS[token]
   return None
  return entry

def claim_demo_zip(token):
 """Atomically take a demo entry for claiming, or None when unknown,
 expired, or already claimed."""
 if not token:return None
 with _DEMO_ZIPS_LOCK:
  entry=_DEMO_ZIPS.pop(token,None)
  if not entry:return None
  if entry[1]<=time.time():return None
  return entry

def restore_demo_zip(token,entry):
 """Restore an unclaimed demo after a transient storage failure.

 Only restore while the original expiry is valid and no newer entry has
 replaced this token. The same token remains usable for the visitor.
 """
 if not token or not entry or entry[1]<=time.time():return False
 with _DEMO_ZIPS_LOCK:
  if token in _DEMO_ZIPS:return False
  _DEMO_ZIPS[token]=entry
  return True

def public_base_url(host):
 """Absolute site URL for robots.txt / sitemap.xml, from the request Host.

 Render serves HTTPS; local dev serves HTTP. No hardcoded host, so the
 same code serves the preview, local runs, and any future domain.
 """
 scheme='https' if os.getenv('VELXTRIA_DEPLOYMENT_MODE')=='render-preview' else 'http'
 return scheme+'://'+(host or 'velxtria-private-preview-tzie.onrender.com')

def robots_txt(base):
 """Search engines may index the public landing and about pages only.
 Everything behind a login (reports, downloads, founder stats, account)
 stays out of the index.
 """
 return ('User-agent: *\n'
  'Allow: /\n'
  'Allow: /about\n'
  'Disallow: /dashboard\n'
  'Disallow: /report\n'
  'Disallow: /founder-stats\n'
  'Disallow: /login\n'
  'Disallow: /signup\n'
  'Disallow: /account\n'
  'Disallow: /download\n'
  'Disallow: /try-download\n'
  '\n'
  'Sitemap: '+base+'/sitemap.xml\n')

def sitemap_xml(base):
 """The only public pages: the landing page and /about."""
 urls=''.join('<url><loc>'+base+path+'</loc></url>' for path in ('/','/about','/terms','/privacy','/contact'))
 return ('<?xml version="1.0" encoding="UTF-8"?>\n'
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+urls+'</urlset>')

def landing_buy_html(user,csrf):
 """Buy block for the landing page.

 Logged-in users get the real BTCPay checkout form (same route and CSRF as
 the dashboard; checkout-feedback.js already guards that form against
 double submits). Logged-out visitors are sent to sign in and then back to
 the landing page. When checkout is disabled the button is shown as coming
 soon, never posted to a dead route.
 """
 if user:
  if btcpay_mainnet.checkout_enabled():
   return '<form method="post" action="/btcpay/mainnet/checkout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button class="v8-primary" type="submit">Get PRO — $49 with Bitcoin</button></form><p class="v8-buy-note">BTCPay creates a secure invoice and PRO activates automatically once the payment settles. Nothing is charged until you pay.</p>'
  return '<button class="v8-primary" type="button" disabled>Get PRO — $49 with Bitcoin</button><p class="v8-buy-note">Bitcoin checkout is coming soon. Create a demo account to try the free reports meanwhile.</p>'
 nxt=urllib.parse.quote('/account#billing',safe='')
 return '<a class="v8-primary" href="/login?next='+nxt+'">Get PRO — $49 with Bitcoin</a><p class="v8-buy-note">Sign in, then open your account billing section to start secure Bitcoin checkout. New here? <a href="/register?next='+nxt+'">Create a free account</a> first. PRO activates only after verified payment.</p>'

def pro_upgrade_html(user,csrf,pending_mainnet=None):
 """PRO upsell block, shared by the dashboard and the paywall page.

 Same three states the dashboard shows: a pending payment gets a
 continue-to-checkout panel, an enabled checkout gets the real BTCPay
 form, and a disabled checkout gets the manual-arrangement text. One
 helper so the paywall can never drift from what a paying customer sees.
 """
 if btcpay_mainnet.checkout_enabled():
  if pending_mainnet:
   return '<section class="panel"><h2>Bitcoin payment pending</h2><p>Your $49 PRO payment is waiting for Bitcoin payment. Complete it at the BTCPay checkout, then use Check payment status — PRO activates automatically once the payment settles.</p><p><a href="'+escape(pending_mainnet['checkout_url'])+'">Continue to BTCPay checkout</a></p><form method="post" action="/btcpay/mainnet/check-status"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button>Check payment status</button></form></section>'
  return '<section class="panel"><h2>VELXTRIA PRO · $49 / 30 days</h2><p>50 reports per billing cycle. Pay with Bitcoin: BTCPay creates a secure invoice and PRO activates automatically once the payment settles. Nothing is charged until you pay.</p><form method="post" action="/btcpay/mainnet/checkout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button>Pay $49 with Bitcoin</button></form></section>'
 btc_address=os.getenv('VELXTRIA_BITCOIN_ADDRESS','bc1qxdjxk3kzke0shnlqupkndyel7mf9v6fahfkgx4').strip()
 return '<section class="panel"><h2>VELXTRIA PRO · $49 / 30 days</h2><p>Direct Bitcoin payment is available by manual arrangement only. Contact the VELXTRIA operator to confirm the exact BTC amount and payment reference <strong>before sending</strong>. No automatic invoice, exchange-rate quote, payment verification, or access activation is enabled.</p><p>Bitcoin network (BTC) receiving address:</p><p><code style="overflow-wrap:anywhere;word-break:break-all">'+escape(btc_address)+'</code></p><p><strong>Do not send BTC until you receive a confirmed amount and instructions.</strong> Payments to the wrong network or address may be irreversible.</p></section>'

RENEWAL_WINDOW_DAYS=14

def renewal_days_left(ent,now=None):
 """Whole days until a PRO period ends, or None when not PRO."""
 if ent['plan']!='pro' or not ent['end']:
  return None
 now=int(time.time()) if now is None else now
 seconds=ent['end']-now
 if seconds<=0:
  return 0
 return (seconds+86399)//86400

def renewal_html(user,csrf,ent,pending_mainnet=None):
 """Renewal block for a PRO user whose period ends soon.

 Shown only inside the renewal window (14 days): the countdown plus the
 same BTCPay checkout form new customers get, so renewing is one click.
 A renewal payment settles into a period that starts when the current one
 ends — renewing early never loses days (see
 btcpay_mainnet._claim_and_activate). Outside the window, or without an
 active PRO period, there is nothing to renew, so this returns ''.
 """
 days=renewal_days_left(ent)
 if days is None or days>RENEWAL_WINDOW_DAYS:
  return ''
 if days==0:
  when='today'
 elif days==1:
  when='tomorrow'
 else:
  when='in %d days'%days
 end=datetime.fromtimestamp(ent['end'],timezone.utc).strftime('%Y-%m-%d')
 head=('<section class="panel"><h2>Renew PRO</h2><p>Your PRO ends '+when+' ('+end
       +'). Renew now for another 30 days — the new period starts when the '
       'current one ends, so you lose no days.</p>')
 if not btcpay_mainnet.checkout_enabled():
  return head+'<p>Bitcoin checkout is coming soon.</p></section>'
 if pending_mainnet:
  link=pending_mainnet.get('checkout_url','')
  return (head+'<p>Your renewal payment is waiting — '
          +('<a href="'+escape(link)+'">complete it at BTCPay</a>' if link else 'complete it at BTCPay')
          +'. PRO extends automatically once it settles.</p></section>')
 return (head+'<form method="post" action="/btcpay/mainnet/checkout">'
         '<input type="hidden" name="csrf" value="'+escape(csrf)+'">'
         '<button>Renew PRO — $49 with Bitcoin</button></form></section>')

def paywall_html(user,csrf,used,pending_mainnet=None):
 """Free-limit page: the moment a user is most likely to pay, show them
 how instead of a bare error. `used` is their lifetime free-report count.
 """
 return ('<section class="panel"><h2>You have used your 3 free reports</h2>'
  '<p>You have generated '+str(used)+' free reports — the lifetime free allowance. '
  'Go PRO to keep going: 50 reports per billing cycle for $49 / 30 days, paid with Bitcoin. '
  'PRO activates automatically once the payment settles.</p></section>'
  +pro_upgrade_html(user,csrf,pending_mainnet)
  +'<p><a href="/">Back to dashboard</a></p>')

def landing_pricing_html(user,csrf):
 return '''<section id="v8-pricing" class="v8-pricing"><div class="v8-sectiontop"><span>02 / PRICING</span><span>SIMPLE, NO SURPRISES.</span></div><h2>START FREE.<br><em>GO PRO WHEN IT PAYS.</em></h2><div class="v8-plans"><article class="v8-plan"><h3>FREE</h3><p class="v8-price">$0</p><ul><li>3 reports, lifetime</li><li>Upload a sales CSV, get cleaned data and summaries</li><li>No card, no purchase required</li></ul><a class="v8-ghost" href="/register">Create demo account ↗</a></article><article class="v8-plan v8-plan-pro"><h3>PRO</h3><p class="v8-price">$49 <span>/ 30 days</span></p><ul><li>50 reports per billing cycle</li><li>Pay with Bitcoin — verified automatically via BTCPay</li><li>PRO activates once the payment settles</li></ul>'''+landing_buy_html(user,csrf)+'''</article></div><p class="v8-pricing-note">Prices in USD. Bitcoin payment only — no card, no Stripe.</p></section>'''

def landing_demo_html():
 """No-signup instant demo: upload a CSV on the landing page and see the
 report. No account, no email, nothing saved — the file is processed once
 and never stored.
 """
 return '''<section id="try" class="v8-demo"><div class="v8-sectiontop"><span>TRY IT NOW</span><span>NO ACCOUNT. NO WAITING.</span></div><h2>YOUR FILE.<br><em>YOUR NUMBERS. RIGHT NOW.</em></h2><p>See how VELXTRIA works in minutes. <a href="/sample-sales.csv" download="VELXTRIA_Sample_Sales.csv">Download the sample sales CSV</a>, then select that file below and generate a real report. The sample is fictional and contains intentionally invalid rows to demonstrate data cleaning.</p><p>Already have a supported export? Upload it below instead. Use only sample or non-sensitive data in this preview.</p><form method="post" action="/try" enctype="multipart/form-data"><label>Choose CSV<input type="file" name="file" accept=".csv,text/csv" required></label><button class="v8-primary" type="submit">Generate my report</button></form><p class="v8-demo-note">5 MB maximum · 20,000 rows · Your download link works for 10 minutes — create a free account to keep your reports.</p><details><summary>Required column headers</summary><code>'''+escape(', '.join(REQUIRED))+'''</code></details></section>'''

def demo_result_html(result,token,share_token=None,user=None,csrf=''):
 """The instant demo result: the report summaries on screen, a ZIP download,
 and the next step (free account to keep reports, PRO for more)."""
 nxt=urllib.parse.quote('/account#billing',safe='')
 share=''
 if share_token:
  link=btcpay_mainnet.site_url()+'/demo/'+share_token
  share=('<p class="v8-demo-note">Share this result: <a href="'+escape(link)+'">'+escape(link)+'</a></p>'
         '<p class="v8-demo-note">The link shows only these summaries — never your file or a raw row — and works for 30 days.</p>')
 if user:
  keep=('<form method="post" action="/claim-demo"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><input type="hidden" name="token" value="'+escape(token)+'"><button>Save this report to my account</button></form>'
        '<p class="v8-demo-note">Saves as one of your free reports — no re-upload.</p>')
  email_form=''
 else:
  keep=('<p class="v8-demo-note">Want to keep it? <a href="/register">Create a free account</a> — then claim this report from your dashboard. It stays claimable for 10 minutes.</p>')
  email_form=''
  if share_token:
   # Anonymous runners vanish after the demo — this is the only chance
   # to reach them again. Email the report (summaries + share link) and
   # record the lead; no account needed.
   email_form=('<form method="post" action="/demo/email"><input type="hidden" name="share_token" value="'+escape(share_token)+'"><label>Email me this report<input name="email" type="email" required placeholder="you@yourbusiness.com"></label><button class="v8-primary" type="submit">Email me this report</button></form>'
               '<p class="v8-demo-note">We send only this report, with a link to create your free account. No account needed to receive it.</p>')
 return ('<div class="v8"><section class="v8-demo-result"><div class="v8-sectiontop"><span>YOUR DEMO REPORT</span><span>BUILT BY THE REAL ENGINE.</span></div><h2>THERE IT IS.<br><em>YOUR BUSINESS, CLEANED UP.</em></h2>'
  +report_summaries_html(result['monthly_rows'],result['product_rows'],result['stats'])
  +'<p>Accepted '+str(result['accepted'])+' rows · flagged '+str(result['rejected'])+' rows. The full package — cleaned data, flagged rows, and summaries — is in the ZIP.</p>'
  +'<a class="v8-primary" href="/try-download?token='+escape(token)+'">Download report ZIP</a>'
  +'<p class="v8-demo-note">Download link works for 10 minutes. Your file was processed once and never stored.</p>'
  +share
  +keep
  +email_form
  +'<p class="v8-demo-note">Ready for more? <a href="/login?next='+nxt+'">Sign in to open PRO billing and checkout</a>. Payment is optional and verified before activation.</p></section></div>')

def report_view_html(row,monthly_rows,product_rows,stats):
 """A saved report, viewed on screen: the same monthly + product summaries
 the demo shows, read back from the stored ZIP so the numbers always match
 the download. row is (id, filename, created, status, accepted, rejected)."""
 ident,filename,created,status,accepted,rejected=row
 when=datetime.fromtimestamp(created,timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
 return ('<section class="panel"><h2>Report: '+escape(filename)+'</h2><p>Processed '+escape(when)+' · Status '+escape(status)+' · Accepted '+str(accepted)+' rows · flagged '+str(rejected)+' rows</p>'
  +report_summaries_html(monthly_rows,product_rows,stats)
  +'<p><a href="/download?id='+escape(ident)+'">Download ZIP</a> · <a href="/">Back to dashboard</a></p></section>')

def read_report_summaries(zip_bytes):
 """Parse the monthly + product summary tables and headline stats out of a
 stored report ZIP. Raises ValueError on a missing or unreadable file so
 the caller can answer 503, the same as a missing report file."""
 try:
  with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
   names=z.namelist()
   if not all(f in names for f in ('monthly_summary.csv','product_summary.csv','run_summary.txt')):
    raise ValueError('incomplete report package')
   monthly_rows=list(csv.reader(io.StringIO(z.read('monthly_summary.csv').decode('utf-8-sig'))))
   product_rows=list(csv.reader(io.StringIO(z.read('product_summary.csv').decode('utf-8-sig'))))
   summary=z.read('run_summary.txt').decode('utf-8')
 except (ValueError,KeyError,zipfile.BadZipFile,UnicodeError) as e:
  raise ValueError('unreadable report package') from e
 stats=[l for l in summary.splitlines() if l.startswith(_SUMMARY_STAT_PREFIXES)]
 return monthly_rows,product_rows,stats

def landing_sample_html():
 sample=sample_report_html()
 body=sample if sample else '<p>Sample report is being prepared — please try again shortly.</p>'
 return '''<section id="v8-sample" class="v8-sample"><div class="v8-sectiontop"><span>03 / SAMPLE REPORT</span><span>SEE WHAT YOU GET.</span></div><h2>A REAL REPORT.<br><em>FROM SAMPLE DATA.</em></h2><p>This sample was built by the same report engine that processes your uploads, from a small sample sales file — not a real business. It accepted the clean rows, flagged the messy ones, and summarized the rest.</p>'''+body+'''</section>'''

def landing_page(user=None,csrf=''):
 return """<div class="v8">
 <div class="v8-orbit v8-orbit-a"></div><div class="v8-orbit v8-orbit-b"></div>
 <section class="v8-hero">
  <div class="v8-copy">
   <div class="v8-status"><span class="v8-live"></span> VELXTRIA / INTELLIGENT REPORTING <span class="v8-status-right">PRIVATE PREVIEW</span></div>
   <h1>RUN YOUR BUSINESS.<br><span>WITH MORE</span><br><i>CLARITY.</i></h1>
   <p>VELXTRIA helps small businesses turn supported sales exports into organized reports, spot data problems, and explore the business tools already available in one workspace. Start with a demo using sample data.</p>
   <div class="v8-actions"><a class="v8-primary" href="#try">TRY IT NOW — NO ACCOUNT <span>↗</span></a><a class="v8-ghost" href="/register">CREATE FREE ACCOUNT <span>↗</span></a><a class="v8-ghost" href="/login">SIGN IN <span>↗</span></a><a class="v8-ghost" href="#v8-process">EXPLORE THE SYSTEM <span>↓</span></a></div>
   <div class="v8-disclaimer">PRIVATE PREVIEW <span>•</span> SAMPLE OR NON-SENSITIVE DATA ONLY <span>•</span> PAID ACCESS REQUIRES VERIFIED PAYMENT; DO NOT SEND FUNDS WITHOUT CONFIRMING THE CURRENT CHECKOUT PROCESS</div>
  </div>
  <div class="v8-stage" aria-label="Illustrative reporting command center">
   <div class="v8-ring ring-1"></div><div class="v8-ring ring-2"></div><div class="v8-ring ring-3"></div>
   <div class="v8-core"><span>✦</span><strong>VX</strong><small>DATA ENGINE</small></div>
   <div class="v8-float v8-float-a"><span>01 / INPUT</span><b>SALES.CSV</b><small>SCHEMA CHECK</small><div class="v8-mini-lines"><i></i><i></i><i></i></div></div>
   <div class="v8-float v8-float-b"><span>02 / PROCESS</span><b>ROW VALIDATION</b><div class="v8-bars"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><small>ILLUSTRATIVE VISUAL</small></div>
   <div class="v8-float v8-float-c"><span>03 / OUTPUT</span><b>REPORT PACKAGE</b><small>CSV + SUMMARIES + ZIP</small><div class="v8-check">✓ READY TO DOWNLOAD</div></div>
   <div class="v8-coordinate">VX / SYSTEM 08<br>VISUAL DEMONSTRATION</div>
  </div>
 </section>
 <section class="v8-ticker" aria-label="Product capabilities"><div>DATA CLEANING <span>✦</span> ROW VALIDATION <span>✦</span> MONTHLY SUMMARIES <span>✦</span> PRODUCT REPORTS <span>✦</span> ZIP EXPORT <span>✦</span> DATA CLEANING <span>✦</span> ROW VALIDATION <span>✦</span></div></section>
 <section id="v8-process" class="v8-process"><div class="v8-sectiontop"><span>01 / THE PIPELINE</span><span>SIMPLICITY, ENGINEERED.</span></div><h2>THREE MOVES.<br><em>ONE CLEARER PICTURE.</em></h2><div class="v8-steps">
  <article><div class="v8-stephead"><span>01</span><span>↗</span></div><div class="v8-stepicon">▤</div><h3>IMPORT</h3><p>Upload a supported sales CSV with the required column headers.</p><small>CSV / UP TO 5 MB</small></article>
  <article><div class="v8-stephead"><span>02</span><span>↗</span></div><div class="v8-stepicon">⌁</div><h3>REFINE</h3><p>Separate accepted records from flagged rows and create structured summaries.</p><small>VALIDATE / ORGANIZE</small></article>
  <article><div class="v8-stephead"><span>03</span><span>↗</span></div><div class="v8-stepicon">⇩</div><h3>DEPLOY</h3><p>Download cleaned sales data, rejected rows, and summaries in one ZIP.</p><small>REPORT PACKAGE / ZIP</small></article>
 </div></section>
 """+landing_demo_html()+landing_pricing_html(user,csrf)+landing_sample_html()+"""<section class="v8-bottom"><div><span>04 / YOUR NEXT MOVE</span><h2>LESS MESS.<br><em>MORE MOMENTUM.</em></h2><p>Try the private reporting demo with sample or non-sensitive data. No purchase required.</p></div><a class="v8-primary" href="#try">TRY IT NOW — NO ACCOUNT <span>↗</span></a></section>
 <div class="v8-footnote">✦ VELXTRIA <span>BUILT FOR CLEARER WORKFLOWS · PREVIEW EDITION</span> · <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/contact">Contact</a></div>
 </div>"""

LANDING_CSS = r"""
/* V8: a substantially different visual system. No JavaScript or external assets. */
body:has(.v8){background:#070811;color:#f3f1ff}
body:has(.v8) main{max-width:unset;padding:0}
body:has(.v8) header{position:relative;z-index:10;background:#0a0a15;border-bottom:1px solid #29263c;padding-left:clamp(1rem,4vw,5rem);padding-right:clamp(1rem,4vw,5rem)}
.v8{position:relative;overflow:hidden;font-family:inherit;background:#080911;color:#f5f1ff}
.v8 *{box-sizing:border-box}
.v8 a{text-decoration:none}
.v8:before{content:"";position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(#a78eff0b 1px,transparent 1px),linear-gradient(90deg,#a78eff0b 1px,transparent 1px);background-size:68px 68px;mask-image:linear-gradient(#000 0%,transparent 80%)}
.v8-orbit{position:absolute;pointer-events:none;border-radius:50%;filter:blur(90px)}
.v8-orbit-a{top:40px;right:7%;width:550px;height:550px;background:#6b35d633;animation:v8-breathe 9s ease-in-out infinite alternate}
.v8-orbit-b{top:400px;left:-180px;width:360px;height:360px;background:#9d4af51a;animation:v8-breathe 12s ease-in-out infinite alternate-reverse}
.v8-hero{position:relative;min-height:760px;max-width:1600px;margin:auto;padding:clamp(4rem,8vw,8rem) clamp(1.5rem,5vw,6rem);display:grid;grid-template-columns:1fr 1fr;gap:2rem;align-items:center}
.v8-copy{position:relative;z-index:2}
.v8-status{display:inline-flex;align-items:center;gap:.7rem;flex-wrap:wrap;color:#c6b7ff;font-size:.65rem;letter-spacing:.16em;font-weight:800;border:1px solid #564479;padding:.7rem 1rem;border-radius:5px;background:#1c1731b0}
.v8-status-right{color:#8f8aab;border-left:1px solid #544570;padding-left:.8rem}
.v8-live{height:7px;width:7px;border-radius:50%;background:#c2a4ff;box-shadow:0 0 14px #c2a4ff}
.v8 h1{font-size:clamp(3.7rem,6.7vw,7.8rem);line-height:.99;letter-spacing:-.075em;font-weight:900;margin:2.2rem 0;white-space:nowrap}
.v8 h1 span{color:#aaa1c2}
.v8 h1 i,.v8-process h2 em,.v8-bottom h2 em,.v8-pricing h2 em,.v8-sample h2 em{font-style:normal;background:linear-gradient(110deg,#a888ff,#d0a7ff 45%,#ffb7f1);color:transparent;background-clip:text;-webkit-background-clip:text}
.v8-copy>p{max-width:560px;color:#bbb6cd;line-height:1.8;font-size:1.05rem}
.v8-actions{display:flex;gap:1rem;align-items:center;flex-wrap:wrap;margin-top:2.3rem}
.v8-primary{display:inline-flex;align-items:center;justify-content:space-between;gap:2rem;padding:1.2rem 1.5rem;background:#c5a7ff;color:#110c1c!important;font-size:.75rem;letter-spacing:.1em;font-weight:900;border:1px solid #d9c5ff;clip-path:polygon(0 0,calc(100% - 15px) 0,100% 15px,100% 100%,0 100%);transition:transform .25s,background .25s}
.v8-primary:hover{background:#ebdfff;transform:translateY(-4px)}
.v8-ghost{color:#e3d8ff!important;font-size:.72rem;font-weight:800;letter-spacing:.09em;padding:1.1rem .5rem}
.v8-ghost span{margin-left:.8rem;color:#bca1ff}
.v8-disclaimer{margin-top:2.6rem;color:#77738c;font-size:.58rem;letter-spacing:.12em;line-height:2}
.v8-disclaimer span{color:#aa89ee;margin:0 .4rem}
.v8-stage{position:relative;height:570px;min-width:0;perspective:900px}
.v8-stage:before{content:"";position:absolute;inset:13%;border-radius:50%;background:radial-gradient(circle,#a263ff30,transparent 65%);filter:blur(32px)}
.v8-ring{position:absolute;top:50%;left:50%;border:1px solid #ac7cff50;border-radius:50%;transform:translate(-50%,-50%) rotateX(64deg) rotate(-18deg);box-shadow:0 0 40px #7139d21c}
.ring-1{width:480px;height:480px;animation:v8-spin 28s linear infinite}
.ring-2{width:370px;height:370px;border-style:dashed;border-color:#b37cff55;animation:v8-spin-reverse 24s linear infinite}
.ring-3{width:260px;height:260px;border-color:#d9b7ff90;animation:v8-spin 16s linear infinite}
.v8-core{position:absolute;top:50%;left:50%;width:210px;height:210px;transform:translate(-50%,-50%);border:1px solid #d0a8ff9c;box-shadow:0 0 35px #8c50ff55,inset 0 0 65px #6b2ad14d;background:radial-gradient(circle at 35% 30%,#5a3486,#1c1730 60%,#0e0e1c);border-radius:40px;display:flex;align-items:center;justify-content:center;flex-direction:column;animation:v8-float 6s ease-in-out infinite}
.v8-core>span{position:absolute;top:15px;right:23px;color:#d8baff;font-size:1.3rem}
.v8-core strong{font-size:5.2rem;letter-spacing:-.12em;line-height:1;font-weight:900;color:#e4d1ff;text-shadow:0 0 32px #d2a9ff66}
.v8-core small{font-size:.62rem;letter-spacing:.24em;color:#c6a7ff}
.v8-float{position:absolute;z-index:2;width:210px;padding:1.2rem;background:linear-gradient(135deg,#242039ed,#111321f2);border:1px solid #655184;box-shadow:0 22px 55px #0009;backdrop-filter:blur(16px);border-radius:8px;animation:v8-float 7s ease-in-out infinite}
.v8-float>span{display:block;color:#b899ff;font-size:.59rem;letter-spacing:.15em;font-weight:800}
.v8-float>b{display:block;color:#f1eaff;font-size:.85rem;letter-spacing:.07em;margin:1rem 0 .6rem}
.v8-float>small{display:block;color:#9991ad;font-size:.56rem;letter-spacing:.09em}
.v8-float-a{top:7%;left:0;transform:rotate(-5deg)}
.v8-float-b{right:-1%;top:19%;animation-delay:-2s}
.v8-float-c{bottom:6%;left:9%;animation-delay:-4s}
.v8-mini-lines{display:grid;gap:6px;margin-top:1rem}.v8-mini-lines i{display:block;background:#755ba5;height:6px;border-radius:2px}.v8-mini-lines i:nth-child(2){width:65%}.v8-mini-lines i:nth-child(3){width:85%}
.v8-bars{display:flex;align-items:end;height:50px;gap:5px;margin:1rem 0}.v8-bars i{flex:1;background:linear-gradient(#d3a7ff,#6035b4);height:45%;border-radius:2px}.v8-bars i:nth-child(2){height:70%}.v8-bars i:nth-child(3){height:52%}.v8-bars i:nth-child(4){height:95%}.v8-bars i:nth-child(5){height:62%}.v8-bars i:nth-child(6){height:83%}.v8-bars i:nth-child(7){height:57%}
.v8-check{margin-top:1rem;border-top:1px solid #584771;padding-top:.7rem;color:#c7b4ff;font-size:.62rem;letter-spacing:.07em}
.v8-coordinate{position:absolute;bottom:0;right:0;font-size:.59rem;color:#746d90;letter-spacing:.14em;text-align:right;line-height:1.8}
.v8-ticker{border-top:1px solid #37304c;border-bottom:1px solid #37304c;background:#151121;overflow:hidden;white-space:nowrap;padding:1.1rem 0}
.v8-ticker div{display:inline-block;min-width:100%;font-size:.73rem;letter-spacing:.23em;font-weight:800;color:#c2b1dd;animation:v8-marquee 28s linear infinite}
.v8-ticker span{color:#9c70e5;padding:0 2.5rem}
.v8-process{max-width:1500px;margin:auto;padding:7rem clamp(1.5rem,5vw,6rem)}
.v8-sectiontop{display:flex;justify-content:space-between;gap:1rem;border-top:1px solid #443755;padding-top:1rem;font-size:.65rem;letter-spacing:.16em;color:#a991d6;font-weight:800}
.v8-process h2,.v8-bottom h2,.v8-pricing h2,.v8-sample h2{font-size:clamp(2.5rem,5vw,5.7rem);line-height:1.06;letter-spacing:-.065em;margin:2.4rem 0 3.5rem;font-weight:900}
.v8-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}
.v8-steps article{position:relative;min-height:340px;padding:2rem;background:linear-gradient(145deg,#201b32,#10121d);border:1px solid #423553;transition:transform .3s,border-color .3s,box-shadow .3s}
.v8-steps article:hover{transform:translateY(-9px);border-color:#ac80ff;box-shadow:0 20px 50px #0007}
.v8-stephead{display:flex;justify-content:space-between;color:#ab8fe1;font-size:.75rem;letter-spacing:.1em}
.v8-stepicon{font-size:3rem;color:#c4a2ff;margin:2rem 0 1rem}
.v8-steps h3{font-size:1.5rem;letter-spacing:.07em;margin:.5rem 0}
.v8-steps p{color:#b1acc3;line-height:1.7}
.v8-steps small{position:absolute;bottom:1.5rem;left:2rem;color:#806eaa;font-size:.6rem;letter-spacing:.12em}
.v8-bottom{position:relative;display:flex;align-items:center;justify-content:space-between;gap:3rem;padding:5rem clamp(1.5rem,8vw,8rem);background:radial-gradient(ellipse at 75% 30%,#7c3ad133,transparent 48%),#151021;border-top:1px solid #423155;border-bottom:1px solid #423155}
.v8-bottom>div>span{color:#b69ae8;font-size:.7rem;letter-spacing:.2em;font-weight:800}
.v8-bottom h2{margin:1.5rem 0}
.v8-bottom p{color:#c4bad7;line-height:1.7}
.v8-bottom .v8-primary{flex-shrink:0}
.v8-footnote{display:flex;justify-content:space-between;gap:1rem;padding:2rem clamp(1.5rem,5vw,6rem);font-size:.72rem;letter-spacing:.14em;font-weight:800;color:#c3a3ff}
.v8-footnote span{color:#746d8b;font-size:.58rem}
@keyframes v8-breathe{from{opacity:.45;transform:scale(.9)}to{opacity:1;transform:scale(1.2)}}
@keyframes v8-float{0%,100%{translate:0 0}50%{translate:0 -14px}}
@keyframes v8-spin{to{transform:translate(-50%,-50%) rotateX(64deg) rotate(342deg)}}
@keyframes v8-spin-reverse{to{transform:translate(-50%,-50%) rotateX(64deg) rotate(-378deg)}}
@keyframes v8-marquee{to{transform:translateX(-20%)}}
@media(max-width:1100px){.v8-hero{grid-template-columns:1fr;padding-top:5rem}.v8 h1{font-size:clamp(3.6rem,9vw,6rem)}.v8-stage{max-width:650px;width:100%;margin:0 auto}.v8-hero{min-height:unset}}
@media(max-width:700px){.v8 h1{font-size:clamp(3.1rem,11vw,5rem)}.v8-stage{height:420px}.v8-ring.ring-1{width:330px;height:330px}.v8-ring.ring-2{width:260px;height:260px}.v8-ring.ring-3{width:190px;height:190px}.v8-core{width:145px;height:145px;border-radius:28px}.v8-core strong{font-size:3.6rem}.v8-float{width:145px;padding:.7rem}.v8-float>b{font-size:.65rem}.v8-float-a{top:3%;left:0}.v8-float-b{top:14%;right:0}.v8-float-c{bottom:0;left:0}.v8-steps{grid-template-columns:1fr}.v8-steps article{min-height:290px}.v8-bottom{flex-direction:column;align-items:flex-start}.v8-sectiontop{flex-wrap:wrap}.v8-disclaimer{font-size:.52rem}}
@media(max-width:390px){.v8 h1{font-size:2.8rem}.v8-stage{height:360px}.v8-float{width:130px}.v8-status-right{display:none}.v8-core{width:125px;height:125px}.v8-core strong{font-size:3rem}}
@media(prefers-reduced-motion:reduce){.v8 *,.v8:before{animation:none!important;transition:none!important;translate:none!important}}
/* Landing pricing + sample report (public, sells PRO). */
.v8-pricing{max-width:1500px;margin:auto;padding:7rem clamp(1.5rem,5vw,6rem)}
.v8-plans{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.v8-plan{padding:2rem;background:linear-gradient(145deg,#201b32,#10121d);border:1px solid #423553}
.v8-plan-pro{border-color:#ac80ff;box-shadow:0 20px 50px #0007}
.v8-plan h3{font-size:1rem;letter-spacing:.2em;color:#c4a2ff}
.v8-price{font-size:3rem;font-weight:900;margin:1rem 0}
.v8-price span{font-size:1rem;color:#b1acc3}
.v8-plan ul{list-style:none;padding:0;color:#b1acc3;line-height:2}
.v8-plan ul li:before{content:"✓ ";color:#c4a2ff}
.v8-plan .v8-primary{margin-top:1.5rem}
.v8-buy-note{color:#b1acc3;line-height:1.7;margin-top:1rem;font-size:.9rem}
.v8-pricing-note{color:#806eaa;font-size:.7rem;letter-spacing:.1em;margin-top:2rem}
.v8-sample{max-width:1500px;margin:auto;padding:7rem clamp(1.5rem,5vw,6rem)}
.v8-sample>p{color:#b1acc3;line-height:1.7;max-width:720px}
.v8-sample-tables{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:2rem}
.v8-sample-tables table{width:100%;border-collapse:collapse;background:#141226;border:1px solid #423553}
.v8-sample-tables th,.v8-sample-tables td{padding:.7rem 1rem;text-align:left;border-bottom:1px solid #2c2540;color:#e6e0f5;font-size:.9rem}
.v8-sample-tables th{color:#c4a2ff;letter-spacing:.1em;font-size:.7rem}
.v8-sample-tables h4{color:#c4a2ff;letter-spacing:.15em;font-size:.75rem;margin-bottom:.8rem}
.v8-sample-stats{color:#c4a2ff;margin-top:1.5rem;font-size:.95rem}
@media(max-width:700px){.v8-plans,.v8-sample-tables{grid-template-columns:1fr}}
/* Instant demo: no-signup CSV upload on the landing page, and its result. */
.v8-demo{max-width:1500px;margin:auto;padding:7rem clamp(1.5rem,5vw,6rem)}
.v8-demo h2,.v8-demo-result h2{font-size:clamp(2.5rem,5vw,5.7rem);line-height:1.06;letter-spacing:-.065em;margin:2.4rem 0 1.5rem;font-weight:900}
.v8-demo h2 em,.v8-demo-result h2 em{font-style:normal;background:linear-gradient(110deg,#a888ff,#d0a7ff 45%,#ffb7f1);color:transparent;background-clip:text;-webkit-background-clip:text}
.v8-demo>p,.v8-demo-result>p{color:#b1acc3;line-height:1.7;max-width:720px}
.v8-demo form{margin-top:2.5rem;display:flex;gap:1.5rem;align-items:flex-end;flex-wrap:wrap}
.v8-demo label{display:flex;flex-direction:column;gap:.7rem;color:#c4a2ff;font-size:.7rem;letter-spacing:.15em;font-weight:800}
.v8-demo input[type=file]{color:#e6e0f5;font:inherit;font-size:.9rem;letter-spacing:0;font-weight:400}
.v8-demo input[type=file]::file-selector-button{padding:.9rem 1.2rem;background:linear-gradient(145deg,#201b32,#10121d);border:1px solid #423553;color:#e6e0f5;font:inherit;font-weight:700;cursor:pointer;margin-right:1rem}
.v8-demo form .v8-primary{border:none;cursor:pointer;font:inherit;font-size:.75rem;letter-spacing:.1em;font-weight:900}
.v8-demo-note{color:#806eaa;font-size:.85rem;line-height:1.7;margin-top:1.5rem;max-width:720px}
.v8-demo-note a{color:#c4a2ff;text-decoration:underline}
.v8-demo details{margin-top:1.5rem;color:#b1acc3}
.v8-demo details summary{cursor:pointer;color:#c4a2ff;font-size:.8rem;letter-spacing:.1em}
.v8-demo details code{display:block;margin-top:.8rem;color:#e6e0f5;font-size:.9rem}
.v8-demo-result{max-width:1500px;margin:auto;padding:5rem clamp(1.5rem,5vw,6rem)}
.v8-demo-result .v8-primary{margin:2rem 0 .5rem}
.v8-demo-result .v8-sample-tables{margin:2rem 0}
@media(max-width:700px){.v8-demo form{flex-direction:column;align-items:flex-start}}
"""

# V4 workspace visual refinement: native controls retain their existing form behavior.
WORKSPACE_CSS = r"""
.workspace-page select {
  appearance:none;-webkit-appearance:none;display:block;width:100%;max-width:100%;
  min-height:48px;padding:12px 48px 12px 16px;border-radius:12px;
  border:1px solid #544b77;color:#f1eaff;background-color:#111324;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%23c4a6ff' stroke-width='2.3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-position:right 15px center;background-repeat:no-repeat;
  font:inherit;font-weight:600;cursor:pointer;transition:border-color .18s,box-shadow .18s,background-color .18s;
}
.workspace-page select:hover{border-color:#a98aff;background-color:#1d1a32}
.workspace-page select:focus-visible{outline:2px solid #b49aff;outline-offset:2px;box-shadow:0 0 0 4px #a98aff24}
.workspace-page select option{color:#f1eaff;background:#17182a}
.workspace-page input:not([type=hidden]):not([type=checkbox]),.workspace-page textarea{
  border-radius:12px;border:1px solid #514a70;background:#101222;color:#f1eaff;
  min-height:48px;padding:12px 15px;font:inherit;box-sizing:border-box;
}
.workspace-page input:not([type=hidden]):not([type=checkbox]):focus-visible,.workspace-page textarea:focus-visible{outline:2px solid #ad90ff;outline-offset:2px}
.workspace-page button:not(.link){border-radius:12px;min-height:45px;padding:11px 20px;font-weight:750;
  background:linear-gradient(125deg,#b39aff,#9579f0);color:#100d1d;border:1px solid #c8b5ff;
  cursor:pointer;transition:filter .18s,transform .18s,box-shadow .18s}
.workspace-page button:not(.link):hover{filter:brightness(1.1);transform:translateY(-1px);box-shadow:0 8px 24px #8b63e43b}
.workspace-page button:not(.link):focus-visible{outline:2px solid #e0d4ff;outline-offset:3px}
.workspace-page label{display:block;margin-bottom:14px}
.workspace-page label select{margin-top:8px}
.workspace-page td select{min-width:145px;min-height:40px;padding:8px 38px 8px 12px;font-size:.9rem}
.workspace-page td button{min-height:40px!important;padding:8px 13px!important}
.workspace-page td form{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
@media(max-width:650px){.workspace-page td form{min-width:210px}.workspace-page select{font-size:16px}}
@media(prefers-reduced-motion:reduce){.workspace-page select,.workspace-page button{transition:none!important}}
"""


def render_agents(csrf):
 with db() as c:
  is_paused=agent_core.paused(c); tasks=agent_core.tasks(c)
 task_rows=''
 for tid,title,stage,status,draft in tasks:
  actions=''
  if status=='queued':actions='<button name="action" value="advance:'+escape(tid)+'">Advance simulation</button>'
  elif status=='awaiting_approval':actions='<button name="action" value="approve:'+escape(tid)+'">Approve draft (no send)</button> <button name="action" value="reject:'+escape(tid)+'">Reject</button>'
  task_rows+='<article class="panel"><h3>'+escape(title)+'</h3><p>'+escape(stage)+' · '+escape(status)+'</p><pre style="white-space:pre-wrap">'+escape(draft)+'</pre><form method="post" action="/agents"><input type="hidden" name="csrf" value="'+escape(csrf)+'">'+actions+'</form></article>'
 return '<section class="panel"><h1>Founder Agent Control — simulation</h1><p>Agents are '+('PAUSED' if is_paused else 'ACTIVE')+'. No external emails, payments, lead searches, or deployments occur.</p><form method="post" action="/agents"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button name="action" value="'+('resume' if is_paused else 'pause')+'">'+('Resume internal simulation' if is_paused else 'Emergency pause')+'</button></form><form method="post" action="/agents"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><label>New task<input name="title" maxlength="160" required></label><button name="action" value="create">Create task</button></form><p><a href="/">Back to reporting</a></p></section>'+task_rows

V51_CSS = r'''
/* V5.1: dashboard visual polish, accessible contrast, consistent controls */
:root{--vx-text:#e7e2ff;--vx-muted:#a9b4d4;--vx-accent:#aa93ff}
body{color:var(--vx-text);background:radial-gradient(ellipse 85% 35% at 55% -10%,rgba(93,58,166,.17),transparent 75%),#090d19}
body:not(:has(.v8)) h1,body:not(:has(.v8)) h2,body:not(:has(.v8)) h3{color:#e8dfff;letter-spacing:-.025em;text-shadow:0 2px 24px rgba(150,111,255,.14)}
body:not(:has(.v8)) .hero h1{background:linear-gradient(105deg,#fff1ff 5%,#c6b0ff 48%,#91b9ff 100%);color:transparent;-webkit-background-clip:text;background-clip:text;text-shadow:none;font-weight:850;letter-spacing:-.045em}
body:not(:has(.v8)) .panel>h2{padding-bottom:10px;border-bottom:1px solid rgba(168,147,255,.14)}
body:not(:has(.v8)) .panel{background:linear-gradient(145deg,#171d31,#13192b);border-color:#363c59;box-shadow:0 14px 38px rgba(0,0,0,.09)}
body:not(:has(.v8)) .stats b{background:linear-gradient(90deg,#e2c9ff,#aa9cff,#8bbfff);color:transparent;-webkit-background-clip:text;background-clip:text}
body:not(:has(.v8)) button:not(.link){min-height:44px;line-height:1.25;margin:3px 0;border:1px solid rgba(255,255,255,.12);background:linear-gradient(135deg,#b4a0ff,#9782f1);box-shadow:0 4px 14px rgba(112,85,222,.16);transition:transform .15s,box-shadow .15s}
body:not(:has(.v8)) button:not(.link):hover{transform:translateY(-1px);box-shadow:0 6px 22px rgba(147,114,255,.28)}
body:not(:has(.v8)) button:focus-visible,body:not(:has(.v8)) a:focus-visible,body:not(:has(.v8)) input:focus-visible,body:not(:has(.v8)) select:focus-visible{outline:3px solid #c9b9ff;outline-offset:3px}
body:not(:has(.v8)) button.secondary-button{background:#252943;color:#d8d0ff;border-color:#55517c;box-shadow:none}
body:not(:has(.v8)) .action-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-top:20px}
body:not(:has(.v8)) .action-row form{display:inline-flex;margin:0}
body:not(:has(.v8)) .proposal-card{border:1px solid #353c59;border-radius:15px;padding:24px;margin:18px 0;background:#12182a}
body:not(:has(.v8)) .proposal-card h3{margin-top:0}
body:not(:has(.v8)) .execution-list{display:grid;gap:12px}
body:not(:has(.v8)) .execution-item{background:#101627;border:1px solid #333c59;padding:16px;border-radius:12px}
body:not(:has(.v8)) .execution-item p{margin:8px 0}
body:not(:has(.v8)) nav{flex-wrap:wrap;gap:14px 20px}
body:not(:has(.v8)) table form{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
body:not(:has(.v8)) table select{min-width:125px}
body:not(:has(.v8)) input,body:not(:has(.v8)) select,body:not(:has(.v8)) textarea{border:1px solid #465273;background:#0e1425;color:#e9e6ff;border-radius:9px;padding:12px}
body:not(:has(.v8)) table td{vertical-align:middle}
@media(max-width:680px){body:not(:has(.v8)) .action-row{align-items:stretch}body:not(:has(.v8)) .action-row button{width:100%}}
@media(prefers-reduced-motion:reduce){body:not(:has(.v8)) button{transition:none!important}}
/* V5.2 Mission Control */
.mission-form{display:grid;gap:18px;max-width:850px}.mission-form label{display:grid;gap:9px;font-weight:650}.mission-form input,.mission-form textarea{width:100%;box-sizing:border-box;padding:13px 15px;border:1px solid #44456e;border-radius:12px;background:#101426;color:#eee8ff;font:inherit}.mission-form textarea{resize:vertical}.mission-form button{justify-self:start}.mission-card{background:linear-gradient(140deg,#151a2d,#111629);border:1px solid #393b60;border-radius:20px;padding:25px;margin:20px 0}.mission-top{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}.mission-top h3{margin:0}.mission-status{border:1px solid #7666bd;color:#d7c9ff;border-radius:99px;padding:5px 13px;font-size:.8rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase}.mission-meter{height:9px;border-radius:50px;background:#2b2c4c;overflow:hidden;margin:20px 0 9px}.mission-meter span{display:block;height:100%;border-radius:50px;background:linear-gradient(90deg,#8d72ee,#b99cff,#8bd4ff)}.mission-note{color:#aeb5d7;font-size:.89rem}.mission-steps{padding-left:24px;line-height:1.95;color:#d5d5ed}.mission-actions{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:22px 0}.mission-actions form{margin:0}.mission-actions button{margin:0!important}.mission-history{border-top:1px solid #363a58;padding-top:14px}.mission-history summary{cursor:pointer;color:#c7b5ff;font-weight:650}.mission-history li{margin:9px 0;overflow-wrap:anywhere}nav{display:flex;flex-wrap:wrap;gap:14px;align-items:center}nav a{white-space:nowrap}@media(max-width:650px){.mission-card{padding:17px}.mission-actions{flex-direction:column;align-items:stretch}.mission-actions form,.mission-actions button{width:100%}}


/* V5.4 Overmind: mission readability and controls */
.v54-panel{border-color:#6550a6!important;background:linear-gradient(130deg,#1c1634,#11192d)!important}
.v54-next{font-size:1.12rem;line-height:1.7;color:#e5d9ff;font-weight:650}
.v54-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:14px;margin:20px 0}
.v54-stats>div{padding:16px;border:1px solid #454067;border-radius:14px;background:#14182d;display:flex;flex-direction:column;gap:5px}
.v54-stats strong{font-size:1.8rem;color:#c6a9ff}.v54-stats span{font-size:.85rem;color:#b8b9d1}
.v54-draft{display:grid;gap:12px;margin:18px 0;padding:16px;border:1px solid #454067;border-radius:14px;background:#15182b}
.v54-draft label{display:grid;gap:9px;font-weight:650;color:#d7c6ff}.v54-draft textarea{width:100%;box-sizing:border-box;background:#0e1223;color:#f0e9ff;border:1px solid #62578e;border-radius:10px;padding:12px;font:inherit;resize:vertical}
.v54-draft button{justify-self:start}.v54-timeline{list-style:none;padding:0;display:grid;gap:12px}.v54-timeline li{border-left:3px solid #9277ee;padding:8px 16px;background:#171a2c;border-radius:0 10px 10px 0}.v54-timeline small{display:block;color:#adb5d5;margin-top:4px}.v54-timeline p{margin:8px 0 0;overflow-wrap:anywhere}.proposal-card .action-row{gap:16px!important;flex-wrap:wrap}.proposal-card .action-row form{margin:0!important}

'''

class Handler(BaseHTTPRequestHandler):
 def preview_guard(self):
  # The separate HTTP Basic Auth preview gate is disabled.
  # Customer sessions, workspace permissions, and founder roles remain enforced.
  return False
  if os.getenv('VELXTRIA_DEPLOYMENT_MODE','local') != 'render-preview':
   return False
  path = urllib.parse.urlsplit(self.path).path
  if path == '/healthz' and self.command == 'GET':
   return False
  # Public marketing page and its stylesheet only; app remains protected.
  if self.command == 'GET' and path in ('/about','/style.css'):
   return False
  # Payhip cannot supply the browser's preview Basic Auth.
  # The webhook independently checks its Payhip signature and never grants access.
  if path == '/webhooks/payhip' and self.command == 'POST':
   return False
  expected=os.getenv('VELXTRIA_PREVIEW_PASSWORD','')
  if not expected:
   self.respond(503,'Preview password not configured','text/plain')
   return True
  supplied=self.headers.get('Authorization','')
  try:
   scheme, encoded=supplied.split(' ',1)
   decoded=base64.b64decode(encoded,validate=True).decode('utf-8')
   username, password=decoded.split(':',1)
  except (ValueError, UnicodeError):
   scheme = ''
   username = password = ''
  if scheme.lower() != 'basic':
   username = password = ''
  # Visitors see the public introduction instead of a credential prompt.
  if self.command == 'GET' and path == '/' and username != 'velxtria':
   self.redirect('/about')
   return True
  if username != 'velxtria' or not hmac.compare_digest(password,expected):
   self.respond(401,'VELXTRIA private preview — authentication required','text/plain', [('WWW-Authenticate','Basic realm="VELXTRIA Private Preview"')])
   return True
  return False
 def log_message(self,format,*args): pass
 def respond(self,status,body,content_type='text/html; charset=utf-8',headers=()):
  b=body.encode() if isinstance(body,str) else body
  self.send_response(status)
  self.send_header('Content-Type',content_type)
  self.send_header('Content-Length',str(len(b)))
  self.send_header('X-Content-Type-Options','nosniff')
  if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview': self.send_header('Strict-Transport-Security','max-age=31536000')
  self.send_header('X-Frame-Options','DENY')
  self.send_header('Referrer-Policy','no-referrer')
  # Static assets pass their own Cache-Control so browsers cache them;
  # everything else defaults to no-store. The extra headers are sent
  # after this block, so a duplicate would go out if we sent both.
  if not any(k.lower()=='cache-control' for k,v in headers):self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'")
  for k,v in headers:self.send_header(k,v)
  self.end_headers();self.wfile.write(b)
 def fail(self,status,message,user=None,csrf=''):
  self.respond(status,shell('Notice','<section class="panel"><h2>'+escape(message)+'</h2><p><a href="/">Return to dashboard</a></p></section>',user,csrf))
 def demo_fail(self,message):
  # Anonymous demo error: point back at the demo form on the landing page,
  # not at a dashboard the visitor does not have.
  body='<div class="v8"><section class="v8-demo-result"><div class="v8-sectiontop"><span>TRY THE DEMO</span><span>THAT FILE DID NOT WORK.</span></div><h2>COULD NOT RUN<br><em>THAT FILE.</em></h2><p>'+escape(message)+'</p><p><a class="v8-primary" href="/#try">Try another file</a></p></section></div>'
  return self.respond(400,shell('Try the demo',body))
 def identity(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except Exception:return None,None,None
  token=cookie.get('velxtria_session')
  if not token:return None,None,None
  with db() as c:
   row=c.execute('SELECT u.id,u.email,u.role,u.access,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.value.encode()).hexdigest(),now())).fetchone()
  if not row:return None,None,None
  return dict(zip(['id','email','role','access'],row[:4])),row[4],token.value
 def require(self):
  user,csrf,token=self.identity()
  if not user:self.fail(401,'Please sign in first.');return None
  return user,csrf,token
 def do_GET(self):
  if urllib.parse.urlsplit(self.path).path == '/healthz': return self.respond(200,'ok','text/plain')
  if self.preview_guard(): return
  p=urllib.parse.urlsplit(self.path).path
  if p=='/health/ready':
   if os.getenv('VELXTRIA_DEPLOYMENT_MODE') != 'render-preview':
    return self.respond(404,'Not found','text/plain')
   try:
    import verify_readiness
    ready = verify_readiness.check()
   except Exception:
    ready = False
   return self.respond(200 if ready else 503,
                       'ready' if ready else 'unavailable',
                       'text/plain',
                       headers=[('Cache-Control','no-store')])
  if p=='/health/db':
   if os.getenv('VELXTRIA_DEPLOYMENT_MODE') != 'render-preview':
    return self.respond(404,'Not found','text/plain')
   try:
    import verify_database
    status=verify_database.check()
   except Exception:
    status='failed'
   return self.respond(200 if status=='connected' else 503,status,'text/plain')
  if p=='/health/storage':
   if os.getenv('VELXTRIA_DEPLOYMENT_MODE') != 'render-preview':
    return self.respond(404,'Not found','text/plain')
   try:
    import verify_storage
    status=verify_storage.check()
   except Exception:
    status='failed'
   return self.respond(200 if status=='connected' else 503,status,'text/plain')
  if p=='/sample-sales.csv':
   return self.respond(200,SAMPLE_SALES_CSV,'text/csv; charset=utf-8',headers=[('Content-Disposition','attachment; filename="VELXTRIA_Sample_Sales.csv"'),('Cache-Control','public, max-age=3600')])
  if p=='/robots.txt':
   return self.respond(200,robots_txt(public_base_url(self.headers.get('Host'))),'text/plain',headers=[('Cache-Control','public, max-age=3600')])
  if p=='/sitemap.xml':
   return self.respond(200,sitemap_xml(public_base_url(self.headers.get('Host'))),'application/xml',headers=[('Cache-Control','public, max-age=3600')])
  if p=='/terms':
   return self.respond(200,shell('Terms of Service',trust_pages.TERMS_HTML))
  if p=='/privacy':
   return self.respond(200,shell('Privacy Policy',trust_pages.PRIVACY_HTML))
  if p=='/contact':
   return self.respond(200,shell('Contact',trust_pages.CONTACT_HTML))
  if p in ('/favicon.svg','/favicon.ico'):
   return self.respond(200,trust_pages.FAVICON_SVG,'image/svg+xml',headers=[('Cache-Control','public, max-age=86400')])
  if p=='/founder-stats':
   user,csrf,_=self.identity()
   if not user:return self.fail(401,'Please sign in first.')
   if user['role']!='admin':return self.fail(403,'Founder access required.',user,csrf)
   with db() as c:totals,daily,recent=site_stats.summary(c)
   return self.respond(200,shell('Founder stats',site_stats.stats_html(totals,daily,recent),user,csrf))
  if p=='/ascension-workflows':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=ascension_workflows.dashboard(c,user['id'],csrf)
   return self.respond(200,shell('Workflow Orchestrator',body,user,csrf))
  if p=='/ascension-briefing':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=ascension_executive_briefing.dashboard(c,user['id'])
   return self.respond(200,shell('Executive Briefing',body,user,csrf))
  if p=='/ascension-next-actions':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=ascension_next_actions.dashboard(c,user['id'])
   return self.respond(200,shell('Next Best Actions',body,user,csrf))
  if p=='/ascension-command':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=ascension_command_center.dashboard(c,user['id'])
   return self.respond(200,shell('Revenue Command Center',body,user,csrf))
  if p=='/ascension-followups':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=ascension_followups.dashboard(c,user['id'],csrf)
   return self.respond(200,shell('Follow-up Studio',body,user,csrf))
  if p=='/ascension-recovery':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=ascension_recovery.dashboard(c,user['id'],csrf)
   return self.respond(200,shell('Revenue Recovery',body,user,csrf))
  if p=='/ascension':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=sovereign_ascension.dashboard(c,user['id'],csrf)
   return self.respond(200,shell('Sovereign Ascension',body,user,csrf))
  if p=='/sales-pipeline':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   with db() as c:body=sales_pipeline.dashboard(c,user['id'],csrf)
   return self.respond(200,shell('Sales Pipeline',body,user,csrf))
  if p=='/outreach-studio':
   auth=self.require()
   if not auth:return
   user,csrf,_=auth
   import outreach_copy
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   val=lambda k: q.get(k,[''])[0][:500]
   name=val('business');industry=val('industry') or 'general';style=val('style') or 'bold'
   observation=val('observation');source=val('source')
   body='<section class="hero"><h1>VELXTRIA Outreach Studio</h1><p>Personalized, review-first email drafts. Nothing is sent automatically.</p></section>'
   body+='<section class="panel"><form method="get" action="/outreach-studio">'
   for key,label in [('business','Business name'),('first_name','Contact first name'),('industry','Industry (restaurant, retail, construction, service)'),('observation','Verified observation (optional)'),('source','Observation source URL or note')]:
    body+='<label>'+escape(label)+'<input name="'+key+'" maxlength="500" value="'+escape(val(key))+'"></label>'
   body+='<label>Voice<select name="style">'+''.join('<option value="'+x+'"'+(' selected' if style==x else '')+'>'+x.title()+'</option>' for x in ('bold','curious','personal'))+'</select></label><button type="submit">Generate draft</button></form></section>'
   if name:
    try:
     result=outreach_copy.draft(outreach_copy.Prospect(name,industry,val('first_name'),observation,source),style)
     checks=outreach_copy.quality_check(outreach_copy.Prospect(name,industry,val('first_name'),observation,source),result)
     if checks['warnings']:body+='<section class="panel"><h3>Quality checks</h3><ul>'+''.join('<li>'+escape(w)+'</li>' for w in checks['warnings'])+'</ul></section>'
     body+='<section class="panel"><h2>Review before sending</h2><p><strong>Subject:</strong> '+escape(result['subject'])+'</p><textarea readonly rows="16" style="width:100%">'+escape(result['body'])+'</textarea><p>Confirm the observation and source are accurate. Respect declines and opt-outs; do not send without review.</p></section>'
    except ValueError as exc:body+='<section class="panel"><p>'+escape(exc)+'</p></section>'
   body+='<section class="panel"><h2>Reply triage</h2><p>Paste a prospect reply to get a suggested next step. Declines and opt-outs are not invitations to keep pitching.</p><form method="get" action="/outreach-studio"><label>Prospect reply<textarea name="reply" maxlength="500" rows="3">'+escape(val('reply'))+'</textarea></label><button type="submit">Review reply</button></form>'
   if val('reply'):
    guidance=outreach_copy.reply_guidance(val('reply'))
    body+='<p><strong>'+escape(guidance['classification'].replace('_',' ').title())+'</strong>: '+escape(guidance['recommended_action'])+'</p>'
    if guidance['suggested_reply']:body+='<textarea readonly rows="4" style="width:100%">'+escape(guidance['suggested_reply'])+'</textarea>'
   body+='</section>'
   return self.respond(200,shell('Outreach Studio',body,user,csrf))
  if p=='/about':
   user,csrf,_=self.identity()
   with db() as c:site_stats.record(c,'about_view')
   ref=referral_code_from_request(self) if not user else ''
   headers=[referral_cookie_header(ref)] if ref else ()
   return self.respond(200,shell('Meet VELXTRIA',landing_page(user,csrf)),headers=headers)
  if p=='/checkout-feedback.js':
   js="""document.addEventListener('submit',function(e){var f=e.target;if(!f || !f.action || !f.action.includes('/btcpay/mainnet/checkout'))return;var b=f.querySelector('button[type="submit"],button:not([type])');if(!b)return;if(b.disabled){e.preventDefault();return;}b.disabled=true;b.textContent='Preparing secure Bitcoin checkout…';b.setAttribute('aria-busy','true');var note=document.createElement('span');note.setAttribute('role','status');note.textContent=' Creating your invoice; please wait.';f.appendChild(note);});"""
   return self.respond(200,js,'application/javascript',headers=[('Cache-Control','public, max-age=3600')])
  if p=='/style.css':return self.respond(200,(ROOT/'style.css').read_bytes()+(LANDING_CSS+WORKSPACE_CSS+V51_CSS+sovereign_v56.CSS+omega_intelligence_v55.CSS+aegis_v54.CSS+sentinel_v53.CSS+titan_intelligence_v52.CSS+ascendancy_v51.CSS+singularity_v6.CSS+omni_v7.CSS+sovereign_v8.CSS+constellation_v9.CSS+trinity_v10.CSS+omnipotence_v12.CSS+singularity_x_v13.CSS+prometheus_v14.CSS+omega_v15.CSS+evolution_v16.CSS+phoenix_v17.CSS+infinity_v18.CSS+ascension_v28.CSS+integration_v29.CSS+atlas_v38.CSS+nexus_reforged_v41.CSS).encode('utf-8'),'text/css; charset=utf-8',headers=[('Cache-Control','public, max-age=3600')])
  if p in ('/site-studio.css','/site-preview.css') and os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE:
   return self.respond(200,(ROOT/p.lstrip('/')).read_bytes(),'text/css; charset=utf-8')
  if p.startswith('/assistant-v64/'):
   token=p[len('/assistant-v64/'):]
   if '/' in token:return self.respond(404,'Not found','text/plain')
   question=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('q',[''])[0][:400]
   with db() as c:body=customer_assistant_v64.page(c,token,question)
   if body is None:return self.respond(404,'Assistant not available','text/plain')
   return self.respond(200,body,'text/html; charset=utf-8',headers=[('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors *"),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
  if p.startswith('/faq-v62/'):
   token=p[len('/faq-v62/'):]
   if '/' in token:return self.respond(404,'Not found','text/plain')
   question=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('q',[''])[0][:200]
   with db() as c:body=business_collaboration_v62.widget_html(c,token,question)
   if body is None:return self.respond(404,'FAQ not available','text/plain')
   return self.respond(200,body,'text/html; charset=utf-8',headers=[('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors *"),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
  user,csrf,_=self.identity()
  if p=='/signup':
   nxt=safe_next(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('next',[''])[0])
   return self.redirect('/register'+('?next='+urllib.parse.quote(nxt,safe='') if nxt!='/' else ''))
  if p=='/login':
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   nxt=safe_next(q.get('next',[''])[0])
   banner=''
   if q.get('registered',[''])[0]=='1':banner='<p>Account created — sign in to start your first report.</p>'
   elif q.get('reset',[''])[0]=='1':banner='<p>Password updated — sign in with your new password.</p>'
   reg='/register'+('?next='+urllib.parse.quote(nxt,safe='') if nxt!='/' else '')
   return self.respond(200,shell('Sign in','<section class="panel narrow"><h1>Welcome back</h1>'+banner+'<form method="post" action="/login"><input type="hidden" name="next" value="'+escape(nxt)+'"><label>Email<input name="email" type="email" required></label><label>Password<input name="password" type="password" required></label><button>Sign in</button></form><p><a href="/forgot">Forgot your password?</a></p><p>No account yet? <a href="'+reg+'">Create a demo account</a></p></section>'))
  if p=='/forgot':
   return self.respond(200,shell('Reset password','<section class="panel narrow"><h1>Forgot your password?</h1><p>Enter the email on your account and we will send a reset link. It works once and expires in one hour.</p><form method="post" action="/forgot"><label>Email<input name="email" type="email" required></label><button>Send reset link</button></form><p><a href="/login">Back to sign in</a></p></section>'))
  if p=='/reset':
   token=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('token',[''])[0]
   with db() as c:valid=password_reset.verify_token(c,token) is not None
   if not valid:return self.respond(400,shell('Reset password','<section class="panel narrow"><h1>Link expired</h1><p>This reset link is expired or already used. <a href="/forgot">Request a new one</a>.</p></section>'))
   return self.respond(200,shell('Reset password','<section class="panel narrow"><h1>Choose a new password</h1><form method="post" action="/reset"><input type="hidden" name="token" value="'+escape(token)+'"><label>New password (12+ characters)<input name="password" type="password" minlength="12" required></label><button>Update password</button></form></section>'))
  if p=='/register':
   nxt=safe_next(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('next',[''])[0])
   login='/login'+('?next='+urllib.parse.quote(nxt,safe='') if nxt!='/' else '')
   ref=referral_code_from_request(self)
   ref_field='<input type="hidden" name="ref" value="'+escape(ref)+'">' if ref else ''
   headers=[referral_cookie_header(ref)] if ref else ()
   return self.respond(200,shell('Register','<section class="panel narrow"><h1>Create a local demo account</h1><p>This account does not verify Payhip payments.</p><form method="post" action="/register"><input type="hidden" name="next" value="'+escape(nxt)+'">'+ref_field+'<label>Email<input name="email" type="email" required></label><label>Password (12+ characters)<input name="password" type="password" minlength="12" required></label><button>Create account</button></form><p>Already have an account? <a href="'+login+'">Sign in</a></p></section>'),headers=headers)
  if p=='/try':return self.redirect('/#try')
  if p=='/try-download':
   # Anonymous demo ZIP: held in memory only, token expires after 10 minutes.
   token=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('token',[''])[0]
   data=take_demo_zip(token)
   if data is None:return self.respond(404,'Demo download expired — run the demo again to generate a new report.','text/plain')
   return self.respond(200,data,'application/zip',headers=[('Content-Disposition','attachment; filename="VELXTRIA_Demo_Report.zip"')])
  if p.startswith('/demo/'):
   # Shared demo result: summaries only, never the file or a raw row.
   share_token=p[len('/demo/'):]
   if not share_token or '/' in share_token:
    return self.respond(404,'This shared demo has expired or does not exist.','text/plain')
   with db() as c:
    shared=demo_shares.get(c,share_token)
    if shared:site_stats.record(c,'demo_share_view',share_token)
   if not shared:return self.respond(404,'This shared demo has expired or does not exist.','text/plain')
   body=('<div class="v8"><section class="v8-demo-result"><div class="v8-sectiontop"><span>SHARED DEMO REPORT</span><span>BUILT BY VELXTRIA.</span></div><h2>SOMEONE CLEANED UP<br><em>THEIR SALES DATA.</em></h2>'
    +report_summaries_html(shared['monthly_rows'],shared['product_rows'],shared['stats'])
    +'<p>Accepted '+str(shared['accepted'])+' rows · flagged '+str(shared['rejected'])+' rows. Only the summaries are shared — the original file and raw rows were never stored.</p>'
    +'<a class="v8-primary" href="/#try">Try it with your own CSV — no account</a>'
    +'<form method="post" action="/demo/email"><input type="hidden" name="share_token" value="'+escape(share_token)+'"><label>Email me this report<input name="email" type="email" required placeholder="you@yourbusiness.com"></label><button class="v8-primary" type="submit">Email me this report</button></form>'
    +'<p class="v8-demo-note">We send only this report, with a link to create your free account. No account needed to receive it.</p>'
    +'<p class="v8-demo-note">VELXTRIA turns messy sales CSVs into clean monthly and product reports. Free demo, no signup. PRO $49/30 days, Bitcoin only.</p></section></div>')
   return self.respond(200,shell('Shared demo report',body))
  if p=='/' and not user:
   with db() as c:site_stats.record(c,'landing_view')
   ref=referral_code_from_request(self)
   headers=[referral_cookie_header(ref)] if ref else ()
   return self.respond(200,shell('Sales reporting made simple',landing_page(user,csrf)),headers=headers)
  if not user:return self.redirect('/login')
  if p=='/sales-execution':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=sales_execution_v44.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Sales Execution Queue',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/growth-strategy':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=growth_strategy_v42.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Growth Strategy Engine',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/growth-intelligence':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=growth_intelligence_v41.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Business Growth Intelligence Center',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/optimization-impact':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=optimization_impact_v40.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Optimization Impact Ledger',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/campaign-optimization':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=campaign_optimization_v39.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Campaign Optimization Workbench',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/experiment-decisions':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=experiment_decisions_v38.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Experiment Decision Engine',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/campaign-experiments':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=campaign_experiments_v37.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Campaign Experiment Lab',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/marketing-budget':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=marketing_budget_v36.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Marketing Budget Allocation Studio',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/acquisition-intelligence':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=acquisition_intelligence_v35.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Customer Acquisition Intelligence',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-attribution':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_attribution_v34.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Lead Source & Outcome Intelligence',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-sources':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_attribution_v34.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Revenue Source Intelligence',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/customer-outcomes':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=customer_outcomes_v33.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Customer Outcomes Ledger',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/operations-performance':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=operations_performance_v32.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Operations Performance Engine',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/operations-recovery':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=operations_recovery_v31.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Operations Recovery Engine',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-recovery':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_recovery_v31.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Operations Recovery Engine',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-operations':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_operations_v30.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Revenue Operations Intelligence',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-execution':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_execution_v29.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Revenue Execution Board',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-gap':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_gap_v28.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Revenue Gap Action Plan',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-goals':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_goals_v27.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Pipeline Goal Tracker',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-brief':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_brief_v26.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Daily Revenue Action Brief',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-command':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_command_v25.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Revenue Command Center',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-conversion':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_conversion_v24.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Revenue Conversion Dashboard',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-followups':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_followups_v23.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Follow-up Tracker',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-priority/live':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':
    return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
      wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=revenue_priority_live.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Live Pipeline Priorities',body,user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/revenue-priority':
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   return self.respond(200,shell('Revenue Priority Workbench',revenue_priority_workbench.render(q),user,csrf),headers=[('Cache-Control','no-store'),('Referrer-Policy','no-referrer')])
  if p=='/':
   if btcpay_integration.configured():
    try:
     with db() as c:btcpay_integration.reconcile(c,user['id'])
    except RuntimeError:pass
   if btcpay_mainnet.configured():
    try:
     with db() as c:btcpay_mainnet.reconcile(c,user['id'])
    except RuntimeError:pass
   with db() as c:
    reports=c.execute('SELECT id,filename,created,status,accepted,rejected,email_status FROM reports WHERE user_id=? ORDER BY created DESC LIMIT 30',(user['id'],)).fetchall()
    ent,count,remaining=subscriptions.usage(c,user['id'])
    pending_mainnet=btcpay_mainnet.pending_order(c,user['id'])
    ref_code=referrals.code_for(c,user['id'])
    ref_stats=referrals.stats(c,user['id'])
   rows=''.join('<tr><td>'+escape(r[1])+'</td><td>'+escape(datetime.fromtimestamp(r[2],timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+'</td><td>'+escape(r[3])+'</td><td>'+str(r[4])+' / '+str(r[5])+'</td><td><a href="/report?id='+escape(r[0])+'">View</a> · <a href="/download?id='+escape(r[0])+'">Download ZIP</a></td><td>'+escape(r[6])+'</td></tr>' for r in reports)
   access='Verified PRO · 50 reports/billing cycle' if ent['plan']=='pro' else 'Free demo · 3 reports total · subscription '+('expired' if ent['status']=='active' else ent['status'].replace('_',' '))
   report_label='Reports this billing cycle' if ent['plan']=='pro' else 'Free reports used (lifetime)'
   limit_label='50 reports per verified billing cycle' if ent['plan']=='pro' else '3 free reports total'
   upgrade_html=pro_upgrade_html(user,csrf,pending_mainnet) if ent['plan']!='pro' else ''
   body=f"""<section class="hero"><p class="eyebrow">CUSTOMER PORTAL</p><h1>Your reports, handled.</h1><p>Upload a supported sales CSV. VELXTRIA cleans records, flags errors, and creates downloadable reports automatically.</p></section><div class="stats"><div><b>{count}</b><small>{escape(report_label)}</small></div><div><b>{remaining}</b><small>Remaining {escape(ent['plan'].upper())} allowance</small></div><div><b>{escape(access)}</b><small>Access status</small></div></div><section class="panel"><h2>Process a CSV</h2><p>5 MB maximum · {escape(limit_label)} · Supported sales-export schema only</p><form method="post" action="/upload" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{escape(csrf)}"><label>Choose CSV<input type="file" name="file" accept=".csv,text/csv" required></label><label><input type="checkbox" name="email_report" value="yes"> Email the completed report to my account address (requires configured SMTP)</label><button>Generate report</button></form><details><summary>Required column headers</summary><code>{escape(', '.join(REQUIRED))}</code></details></section><section class="panel"><h2>Your reports</h2><div class="scroll"><table><thead><tr><th>File</th><th>Processed</th><th>Status</th><th>Accepted / flagged</th><th>Result</th><th>Email</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No reports yet.</td></tr>'}</tbody></table></div></section>"""
   if os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE: body+='<section class="panel"><h2>Site Studio</h2><a href="/site-studio">Create a company website draft</a></section>'
   body+='<section class="panel"><h2>Business Workspace</h2><p>Manage contacts, track income and expenses, review insights, and organize follow-up tasks in one place.</p><a href="/workspace">Open Business Workspace</a></section>'
   body+=upgrade_html
   body+=renewal_html(user,csrf,ent,pending_mainnet)
   demo_cookie=SimpleCookie()
   try:demo_cookie.load(self.headers.get('Cookie',''))
   except Exception:pass
   demo_morsel=demo_cookie.get(DEMO_COOKIE)
   demo_entry=peek_demo_zip(demo_morsel.value) if demo_morsel else None
   if demo_entry:
    body+='<section class="panel"><h2>Your demo report is waiting</h2><p>You ran the instant demo — save it to your account instead of uploading the file again. It counts as one of your free reports.</p><form method="post" action="/claim-demo"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><input type="hidden" name="token" value="'+escape(demo_morsel.value)+'"><button>Save demo report to my account</button></form></section>'
   ref_link=btcpay_mainnet.site_url()+'/?ref='+ref_code
   body+='<section class="panel"><h2>Refer friends — earn free PRO</h2><p>Share your link: <a href="'+escape(ref_link)+'">'+escape(ref_link)+'</a></p><p>When someone signs up with your link and pays $49 for PRO, you get a free month of PRO. Referred signups: '+str(ref_stats['signups'])+' · Paid referrals: '+str(ref_stats['paid'])+' · Free months earned: '+str(ref_stats['months_earned'])+'</p></section>'
   if user['role']=='admin':
    body+='<section class="panel"><a href="/agents">Open Founder Agent Control</a> · <a href="/founder-stats">Founder stats — traffic and funnel</a></section>'
    with db() as c:
     users=c.execute('SELECT email,role,access FROM users ORDER BY created DESC').fetchall();errors=c.execute("SELECT count(*) FROM reports WHERE status != 'ready'").fetchone()[0]
    body+='<section class="panel"><h2>Founder overview</h2><p>Accounts: '+str(len(users))+' · Failed reports: '+str(errors)+'</p><p>Payhip verification: <strong>STAGING ONLY — manual review; no automatic access</strong>. Email: <strong>'+('configured' if DELIVERY_ENABLED else 'not configured')+'</strong>. Do not use this prototype to enforce paid access.</p></section>'
   return self.respond(200,shell('Dashboard',body,user,csrf))
  if p=='/sovereign-gate':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign Gate requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=sovereign_gate_v35.render(c,user['id'],csrf,q.get('w',[''])[0],DATA_ROOT)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Sovereign Gate V35',body,user,csrf))
  if p=='/integration-health-v72':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=integration_health_v72.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Integration Health V72',body,user,csrf))
  if p=='/hubspot-oauth-v70/callback':
   if not user:return self.redirect('/login')
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    if q.get('error'):raise ValueError('HubSpot authorization declined')
    with db() as c:wid=hubspot_oauth_v70.finish(c,user['id'],q.get('state',[''])[0],q.get('code',[''])[0])
    return self.redirect('/hubspot-oauth-v70?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/hubspot-oauth-v70':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=hubspot_oauth_v70.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('HubSpot OAuth V70',body,user,csrf))
  if p=='/sync-control-v68':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=sync_control_v68.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Sync Control V68',body,user,csrf))
  if p=='/hubspot-v67':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=hubspot_v67.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('HubSpot Sync V67',body,user,csrf))
  if p=='/native-integrations-v66':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=native_integrations_v66.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Native Integrations V66',body,user,csrf))
  if p=='/integrations-v65':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=integrations_v65.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Integrations V65',body,user,csrf))
  if p=='/workflow-v63':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=workflow_v63.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Workflow V63',body,user,csrf))
  if p=='/business-collaboration-v62':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=business_collaboration_v62.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Website FAQ & Collaboration V62',body,user,csrf))
  if p=='/agent-engine-v61':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=agent_engine_v61.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Agent Engine V61',body,user,csrf))
  if p=='/business-intelligence-v60':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     body=business_intelligence_v60.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Business Intelligence V60',body,user,csrf))
  if p in ('/business-os-v59','/business-os-v59.csv','/business-agents-v59'):
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS V59 is not enabled.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.csv'):body=business_os_v59.export_csv(c,user['id'],wid)
     elif p=='/business-os-v59':body=business_os_v59.render(c,user['id'],wid,csrf,q.get('search',[''])[0],q.get('status',['all'])[0],q.get('page',['1'])[0])
     else:body=business_agents_v59.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.csv'):return self.respond(200,body.encode('utf-8'),'text/csv; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-leads.csv"')])
   return self.respond(200,shell('Business OS V59',body,user,csrf))
  if p in ('/sovereign-lab-v57','/sovereign-lab-v57.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Decision Lab requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_lab_v57.overview(c,user['id'],wid)
     else:body=sovereign_lab_v57.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Omniverse Decision Laboratory',body,user,csrf))
  if p in ('/sovereign-council-v57','/sovereign-council-v57.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Council requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_council_v57.overview(c,user['id'],wid)
     else:body=sovereign_council_v57.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Omniverse Intelligence Council',body,user,csrf))
  if p in ('/sovereign-business-graph-v57','/sovereign-business-graph-v57.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Business Graph requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_business_graph_v57.overview(c,user['id'],wid)
     else:body=sovereign_business_graph_v57.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Omniverse Business Graph',body,user,csrf))
  if p in ('/sovereign-opportunities-v57','/sovereign-opportunities-v57.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Opportunity Radar requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_opportunities_v57.suggestions(c,user['id'],wid)
     else:body=sovereign_opportunities_v57.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('OMNIS Opportunity Radar',body,user,csrf))
  if p in ('/sovereign-omniverse-v57','/sovereign-omniverse-v57.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omniverse requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_omniverse_v57.overview(c,user['id'],wid)
     else:body=sovereign_omniverse_v57.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Project Omniverse',body,user,csrf))
  if p in ('/sovereign-nexus-v56','/sovereign-nexus-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Workflow Nexus requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_nexus_v56.advanced_overview(c,user['id'],wid)
     else:body=sovereign_nexus_v56.render_advanced(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Workflow Nexus',body,user,csrf))
  if p in ('/sovereign-workflow-runs-v56','/sovereign-workflow-runs-v56.json','/sovereign-workflow-runs-v56.csv'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Workflow Operations requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.csv'):payload=sovereign_workflow_runtime_v56.export_csv(c,user['id'],wid)
     elif p.endswith('.json'):payload=sovereign_workflow_runtime_v56.overview(c,user['id'],wid)
     else:body=sovereign_workflow_runtime_v56.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.csv'):return self.respond(200,payload.encode('utf-8'),'text/csv; charset=utf-8')
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Workflow Operations',body,user,csrf))
  if p in ('/sovereign-workflows-v56','/sovereign-workflows-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Workflow Studio requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_workflows_v56.overview(c,user['id'],wid)
     else:body=sovereign_workflows_v56.render(c,user['id'],wid,csrf)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Workflow Studio',body,user,csrf))
  if p in ('/sovereign-unified-v56','/sovereign-unified-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Unified Command requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_unified_v56.overview(c,user['id'],wid)
     else:body=sovereign_unified_v56.render(c,user['id'],wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Unified Command',body,user,csrf))
  if p in ('/sovereign-genesis-v56','/sovereign-genesis-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Genesis requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload={'sessions':sovereign_genesis_v56.history(c,user['id'],wid),'experiments':sovereign_genesis_v56.experiments(c,user['id'],wid)}
     else:body=sovereign_genesis_v56.render(c,user['id'],csrf,wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Project Genesis',body,user,csrf))
  if p in ('/sovereign-command-v56','/sovereign-command-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Command Center requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0];question=q.get('q',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_command_v56.answer(c,user['id'],wid,question)
     else:body=sovereign_command_v56.render(c,user['id'],csrf,wid,question)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Ask VELXTRIA',body,user,csrf))
  if p in ('/sovereign-guardian-v56','/sovereign-guardian-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Guardian requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_guardian_v56.history(c,user['id'],wid)
     else:body=sovereign_guardian_v56.render(c,user['id'],csrf,wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Business Guardian',body,user,csrf))
  if p in ('/sovereign-connectors-v56','/sovereign-connectors-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Connectors require local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_connectors_v56.history(c,user['id'],wid)
     else:body=sovereign_connectors_v56.render(c,user['id'],csrf,wid)
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Universal Business Connectors',body,user,csrf))
  if p in ('/sovereign-executive-v56','/sovereign-executive-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Executive Council requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_executive_v56.history(c,user['id'],wid)
     else:body=sovereign_executive_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Executive Intelligence Council 2.0',body,user,csrf))
  if p in ('/sovereign-future-v56','/sovereign-future-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Future simulator requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_future_v56.history(c,user['id'],wid)
     else:body=sovereign_future_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Future Simulator',body,user,csrf))
  if p in ('/sovereign-memory-v56','/sovereign-memory-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Memory requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_memory_v56.timeline(c,user['id'],wid)
     else:body=sovereign_memory_v56.render(c,user['id'],csrf,wid,q.get('q',[''])[0])
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Memory',body,user,csrf))
  if p in ('/sovereign-execution-v56','/sovereign-execution-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Execution requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_execution_v56.history(c,user['id'],wid)
     else:body=sovereign_execution_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Execution',body,user,csrf))
  if p in ('/sovereign-strategies-v56','/sovereign-strategies-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Strategy simulation requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_strategy_v56.history(c,user['id'],wid)
     else:body=sovereign_strategy_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Strategies',body,user,csrf))
  if p in ('/sovereign-opportunities-v56','/sovereign-opportunities-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Opportunity discovery requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_opportunities_v56.history(c,user['id'],wid)
     else:body=sovereign_opportunities_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Opportunities',body,user,csrf))
  if p in ('/sovereign-sync-v56','/sovereign-sync-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sync requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_sync_v56.status(c,user['id'],wid)
     else:body=sovereign_sync_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Sync',body,user,csrf))
  if p in ('/sovereign-twin-v56','/sovereign-twin-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Digital Twin requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if not wid:
      row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone();wid=row[0] if row else ''
     if not wid:raise ValueError('Create a workspace first')
     if p.endswith('.json'):payload=sovereign_twin_v56.graph(c,user['id'],wid)
     else:body=sovereign_twin_v56.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Digital Twin',body,user,csrf))
  if p in ('/sovereign-council-v56','/sovereign-council-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign Council requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);wid=q.get('w',[''])[0]
   try:
    with db() as c:
     if p.endswith('.json'):
      if not wid:raise ValueError('Workspace required')
      payload=sovereign_intelligence_v56.history(c,user['id'],wid)
     else:
      if not wid:
       row=c.execute('SELECT workspace_id FROM empire_members WHERE user_id=? LIMIT 1',(user['id'],)).fetchone()
       wid=row[0] if row else ''
      body=sovereign_intelligence_v56.render(c,user['id'],csrf,wid) if wid else '<section class="panel">Create a workspace first.</section>'
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode(),'application/json; charset=utf-8')
   return self.respond(200,shell('Sovereign Council',body,user,csrf))
  if p in ('/sovereign-v56','/sovereign-v56.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     wid=q.get('w',[''])[0]
     if p.endswith('.json'):
      if not wid:raise ValueError('Workspace required')
      payload=sovereign_v56.report(c,user['id'],wid)
     else:body=sovereign_v56.render(c,user['id'],csrf,wid,q.get('rc',['0'])[0],q.get('ec',['0'])[0])
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v56-sovereign.json"')])
   return self.respond(200,shell('Sovereign V56',body,user,csrf))
  if p in ('/omega-v55','/omega-v55.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omega requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     args=(c,user['id'],q.get('w',[''])[0],q.get('question',['overview'])[0],q.get('capacity',['20'])[0])
     if p.endswith('.json'):payload=omega_intelligence_v55.report(*args)
     else:body=omega_intelligence_v55.render(c,user['id'],csrf,*args[2:])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v55-omega.json"')])
   return self.respond(200,shell('Omega Intelligence V55',body,user,csrf))
  if p in ('/aegis-v54','/aegis-v54.json','/aegis-v54.csv'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Aegis requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith(('.json','.csv')):payload=aegis_v54.report(c,user['id'],q.get('w',[''])[0])
     else:body=aegis_v54.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v54-aegis.json"')])
   if p.endswith('.csv'):return self.respond(200,aegis_v54.csv_export(payload).encode('utf-8'),'text/csv; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v54-aegis.csv"')])
   return self.respond(200,shell('Aegis V54',body,user,csrf))
  if p in ('/sentinel-v53','/sentinel-v53.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sentinel requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=sentinel_v53.report(c,user['id'],q.get('w',[''])[0])
     else:body=sentinel_v53.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v53-sentinel.json"')])
   return self.respond(200,shell('Sentinel V53',body,user,csrf))
  if p in ('/titan-intelligence','/titan-intelligence.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Titan Intelligence requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=titan_intelligence_v52.report(c,user['id'],q.get('w',[''])[0])
     else:body=titan_intelligence_v52.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v52-titan-intelligence.json"')])
   return self.respond(200,shell('Titan Intelligence V52',body,user,csrf))
  if p in ('/ascendancy-v51','/ascendancy-v51.json','/ascendancy-v51.csv'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Ascendancy requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   wid=q.get('w',[''])[0];status=q.get('filter',['all'])[0]
   try:
    with db() as c:
     if p.endswith('.json'):payload=ascendancy_v51.report(c,user['id'],wid,status)
     elif p.endswith('.csv'):payload=ascendancy_v51.csv_export(c,user['id'],wid,status)
     else:body=ascendancy_v51.render(c,user['id'],csrf,wid,status)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v51-actions.json"')])
   if p.endswith('.csv'):return self.respond(200,payload,'text/csv; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v51-actions.csv"')])
   return self.respond(200,shell('Ascendancy V51',body,user,csrf))
  if p in ('/singularity-v50','/singularity-v50.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Singularity requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=singularity_v50.report(c,user['id'],q.get('w',[''])[0])
     else:body=singularity_v50.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v50-singularity.json"')])
   return self.respond(200,shell('Singularity V50',body,user,csrf))
  if p in ('/omniscience','/omniscience.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omniscience requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=omniscience_v49.report(c,user['id'],q.get('w',[''])[0])
     else:body=omniscience_v49.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v49-omniscience.json"')])
   return self.respond(200,shell('Omniscience V49',body,user,csrf))
  if p in ('/quantum-command','/quantum-command.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Quantum Command requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=quantum_command_v48.report(c,user['id'],q.get('w',[''])[0])
     else:body=quantum_command_v48.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v48-quantum.json"')])
   return self.respond(200,shell('Quantum Command V48',body,user,csrf))
  if p in ('/hyperion','/hyperion.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Hyperion requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=hyperion_v47.report(c,user['id'],q.get('w',[''])[0])
     else:body=hyperion_v47.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v47-hyperion.json"')])
   return self.respond(200,shell('Hyperion V47',body,user,csrf))
  if p in ('/evolution-engine','/evolution-engine.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Evolution Engine requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=evolution_engine_v46.report(c,user['id'],q.get('w',[''])[0])
     else:body=evolution_engine_v46.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v46-evolution-evidence.json"')])
   return self.respond(200,shell('Evolution Engine V46',body,user,csrf))
  if p in ('/neural-network','/neural-network.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Neural Network requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=neural_network_v45.report(c,user['id'],q.get('w',[''])[0])
     else:body=neural_network_v45.render(c,user['id'],q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v45-neural-evidence.json"')])
   return self.respond(200,shell('Neural Network V45',body,user,csrf))
  if p in ('/synapse','/synapse.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Synapse requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=synapse_v44.report(c,user['id'],q.get('w',[''])[0])
     else:body=synapse_v44.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v44-synapse.json"')])
   return self.respond(200,shell('Synapse V44',body,user,csrf))
  if p in ('/autonomous-core','/autonomous-core.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Autonomous Core requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):payload=autonomous_core_v43.report(c,user['id'],q.get('w',[''])[0])
     else:body=autonomous_core_v43.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v43-experiments.json"')])
   return self.respond(200,shell('Autonomous Core V43',body,user,csrf))
  if p in ('/infinity-engine','/infinity-engine.json'):
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Infinity Engine requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:
     if p.endswith('.json'):
      payload=infinity_engine_v42.report(c,user['id'],q.get('w',[''])[0])
     else:body=infinity_engine_v42.render(c,user['id'],q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   if p.endswith('.json'):
    return self.respond(200,json.dumps(payload,allow_nan=False,indent=2).encode('utf-8'),'application/json; charset=utf-8',headers=[('Content-Disposition','attachment; filename="velxtria-v42-report.json"')])
   return self.respond(200,shell('Infinity Engine V42',body,user,csrf))
  if p=='/nexus-reforged':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Nexus Reforged requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=nexus_reforged_v41.render(c,user['id'],q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Nexus Reforged V41',body,user,csrf))
  if p=='/genesis-reborn':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Genesis Reborn requires local SQLite studio mode.',user,csrf)
   if user['role']!='admin':return self.fail(403,'Founder access required.',user,csrf)
   return self.respond(200,shell('Genesis Reborn V40',genesis_reborn_v40.render(DATA_ROOT),user,csrf))
  if p=='/catalyst':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Catalyst requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=catalyst_v39.render(c,user['id'],q.get('w',[''])[0],DATA_ROOT)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Catalyst V39',body,user,csrf))
  if p=='/atlas':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Atlas requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=atlas_v38.render(c,user['id'],q.get('w',[''])[0],DATA_ROOT)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Atlas V38',body,user,csrf))
  if p=='/apex':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Apex requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=apex_v37.render(c,user['id'],q.get('w',[''])[0],DATA_ROOT)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,shell('Apex V37',body,user,csrf))
  if p=='/titanium':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Titanium requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=titanium_v36.render(c,user['id'],q.get('w',[''])[0],DATA_ROOT)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Titanium V36',body,user,csrf))
  if p=='/sentinel':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sentinel requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=sentinel_v34.render(c,user['id'],csrf,q.get('w',[''])[0],DATA_ROOT,DB)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Sentinel V34',body,user,csrf))
  if p=='/evolutionary-core':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Evolutionary Core requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=evolutionary_core_v33.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Evolutionary Core V33',body,user,csrf))
  if p=='/horizon':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Horizon requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=horizon_v32.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Horizon V32',body,user,csrf))
  if p=='/first-contact':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'First Contact requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=first_contact_v31.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('First Contact V31',body,user,csrf))
  if p=='/sovereign-core':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign Core requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=sovereign_core_v30.render(c,user['id'],q.get('w',[''])[0],DB)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Sovereign Core V30',body,user,csrf))
  if p=='/integration':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Integration requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=integration_v29.render(c,user['id'],q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Integration V29',body,user,csrf))
  if p=='/ascension':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Ascension requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=ascension_v28.dashboard(c,user['id'],q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Ascension V28',body,user,csrf))
  if p=='/launchpad':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Launchpad requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=launchpad_v27.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Launchpad V27',body,user,csrf))
  if p=='/sovereign-gate':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign Gate requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','')
    with db() as c:
     sovereign_gate_v35.attach(c,user['id'],wid,fields.get('release',''),fields.get('run',''),DATA_ROOT)
     c.commit()
     body=sovereign_gate_v35.render(c,user['id'],csrf,wid,'Verified automated evidence attached.')
    return self.respond(200,shell('Sovereign Gate V35',body,user,csrf))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/evolutionary-core':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Evolutionary Core requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','');action=fields.get('action','')
    with db() as c:
     if action=='create':evolutionary_core_v33.create(c,user['id'],wid,fields.get('plan',''),fields.get('title',''),fields.get('version',''))
     elif action=='test':evolutionary_core_v33.record_test(c,user['id'],wid,fields.get('release',''),fields.get('result',''),fields.get('notes',''))
     elif action=='review':evolutionary_core_v33.review(c,user['id'],wid,fields.get('release',''),fields.get('decision',''),fields.get('note',''),DATA_ROOT)
     else:raise ValueError('Unknown Evolutionary Core action')
     c.commit()
     body=evolutionary_core_v33.render(c,user['id'],csrf,wid,'Release candidate updated successfully.')
    return self.respond(200,shell('Evolutionary Core V33',body,user,csrf))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/horizon':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Horizon requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','');action=fields.get('action','')
    with db() as c:
     if action=='create':horizon_v32.create(c,user['id'],wid,fields.get('issue',''),fields.get('priority',''),fields.get('note',''),fields.get('metric',''),fields.get('baseline',''),fields.get('target',''))
     elif action=='update':horizon_v32.update(c,user['id'],wid,fields.get('plan',''),fields.get('status',''),fields.get('result',''))
     else:raise ValueError('Unknown Horizon action')
     c.commit()
     body=horizon_v32.render(c,user['id'],csrf,wid,'Improvement plan updated successfully.')
    return self.respond(200,shell('Horizon V32',body,user,csrf))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/first-contact':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'First Contact requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','');action=fields.get('action','')
    with db() as c:
     if action=='create':first_contact_v31.create(c,user['id'],wid,fields.get('pilot',''),fields.get('title',''),fields.get('description',''),fields.get('severity',''))
     elif action=='resolve':first_contact_v31.resolve(c,user['id'],wid,fields.get('issue',''))
     else:raise ValueError('Unknown First Contact action')
     c.commit()
     body=first_contact_v31.render(c,user['id'],csrf,wid,'Issue updated successfully.')
    return self.respond(200,shell('First Contact V31',body,user,csrf))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/launchpad':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Launchpad requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','');action=fields.get('action','')
    with db() as c:
     if action=='create':launchpad_v27.create(c,user['id'],wid,fields.get('name',''))
     elif action=='feedback':launchpad_v27.feedback(c,user['id'],wid,fields.get('pilot',''),fields.get('rating',''),fields.get('comment',''))
     elif action=='finish':launchpad_v27.finish(c,user['id'],wid,fields.get('pilot',''))
     else:raise ValueError('Unknown Launchpad action')
     body=launchpad_v27.render(c,user['id'],csrf,wid,'Pilot updated successfully.')
    return self.respond(200,shell('Launchpad V27',body,user,csrf))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-lab-v57':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Decision Lab requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','');pid=fields.get('plan','')
   try:
    with db() as c:
     if action=='create':sovereign_lab_v57.plan(c,user['id'],wid,fields.get('investigation_id',''),fields.get('name',''),fields.get('metric',''),fields.get('baseline',''),fields.get('unit',''),fields.get('horizon',''),fields.get('assumptions',''))
     elif action=='option':sovereign_lab_v57.option(c,user['id'],wid,pid,fields.get('name',''),fields.get('change_pct',''),fields.get('cost',''),fields.get('risk_pct',''))
     elif action=='review':sovereign_lab_v57.review(c,user['id'],wid,pid,fields.get('decision',''),fields.get('reason',''))
     elif action=='measure':sovereign_lab_v57.measure(c,user['id'],wid,pid,fields.get('observed',''),fields.get('evidence',''))
     else:raise ValueError('Unknown Decision Lab action')
    return self.redirect('/sovereign-lab-v57?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/optimization-impact':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     optimization_impact_v40.record(c,user['id'],wid,fields.get('proposal',''),fields.get('start',''),fields.get('end',''),fields.get('spend',''),fields.get('leads',''),fields.get('conversions',''),fields.get('evidence',''))
    return self.redirect('/optimization-impact?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sales-execution':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      sales_execution_v44.create(c,user['id'],wid,fields.get('plan_id',''),fields.get('owner',''),fields.get('contact',''),fields.get('kind',''),fields.get('summary',''),fields.get('due',''))
     elif fields.get('action')=='update':
      sales_execution_v44.update(c,user['id'],wid,fields.get('id',''),fields.get('stage',''),fields.get('note',''))
     else:raise ValueError('Unknown sales action')
    return self.redirect('/sales-execution?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/growth-strategy':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      growth_strategy_v42.create(c,user['id'],wid,fields.get('owner',''),fields.get('title',''),fields.get('reason',''),fields.get('metric',''),fields.get('target',''),fields.get('due',''),fields.get('priority',''))
     elif fields.get('action')=='change':
      growth_strategy_v42.change(c,user['id'],wid,fields.get('id',''),fields.get('status',''),fields.get('note',''))
     else:raise ValueError('Unknown strategy action')
    return self.redirect('/growth-strategy?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/campaign-optimization':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='propose':
      campaign_optimization_v39.propose(c,user['id'],wid,fields.get('campaign',''),fields.get('name',''),fields.get('change',''),fields.get('hypothesis',''),fields.get('metric',''),fields.get('target',''),fields.get('budget',''))
     else:
      campaign_optimization_v39.decide(c,user['id'],wid,fields.get('id',''),fields.get('action',''),fields.get('note',''))
    return self.redirect('/campaign-optimization?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/campaign-experiments':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      campaign_experiments_v37.create(c,user['id'],wid,fields.get('name',''),fields.get('source',''),fields.get('hypothesis',''),fields.get('start',''),fields.get('end',''))
     elif fields.get('action')=='update':
      campaign_experiments_v37.update(c,user['id'],wid,fields.get('id',''),fields.get('status',''),fields.get('spend',''),fields.get('leads',''),fields.get('conversions',''),fields.get('notes',''))
     else:raise ValueError('Unknown campaign action')
    return self.redirect('/campaign-experiments?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/marketing-budget':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     marketing_budget_v36.set_budget(c,user['id'],wid,fields.get('source',''),fields.get('amount',''))
    return self.redirect('/marketing-budget?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/acquisition-intelligence':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     acquisition_intelligence_v35.add(c,user['id'],wid,fields.get('source',''),fields.get('amount',''),fields.get('note',''))
    return self.redirect('/acquisition-intelligence?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/customer-outcomes':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='add':
      customer_outcomes_v33.add(c,user['id'],wid,fields.get('lead',''),fields.get('kind',''),fields.get('amount','0'),fields.get('description',''),fields.get('evidence',''))
     elif fields.get('action')=='review':
      customer_outcomes_v33.review(c,user['id'],wid,fields.get('id',''))
     else:raise ValueError('Unknown outcome action')
    return self.redirect('/customer-outcomes?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/operations-recovery':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      operations_recovery_v31.create(c,user['id'],wid,fields.get('task',''),fields.get('diagnosis',''),fields.get('next_step',''),fields.get('due',''))
     elif fields.get('action')=='resolve':
      operations_recovery_v31.resolve(c,user['id'],wid,fields.get('id',''))
     else:raise ValueError('Unknown recovery action')
    return self.redirect('/operations-recovery?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/revenue-recovery':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      revenue_recovery_v31.create(c,user['id'],wid,fields.get('task',''),fields.get('blocker',''),fields.get('next_action',''))
     elif fields.get('action')=='resolve':
      revenue_recovery_v31.resolve(c,user['id'],wid,fields.get('id',''))
     else:raise ValueError('Unknown recovery action')
    return self.redirect('/revenue-recovery?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/revenue-execution':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      revenue_execution_v29.create(c,user['id'],wid,fields.get('lead',''),fields.get('title',''),fields.get('due',''))
     elif fields.get('action')=='status':
      revenue_execution_v29.change(c,user['id'],wid,fields.get('id',''),fields.get('status',''))
     else:raise ValueError('Unknown execution action')
    return self.redirect('/revenue-execution?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/revenue-goals':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:revenue_goals_v27.set_goal(c,user['id'],wid,fields.get('target',''))
    return self.redirect('/revenue-goals?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/revenue-followups':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='create':
      revenue_followups_v23.create(c,user['id'],wid,fields.get('lead',''),fields.get('due_date',''),fields.get('note',''))
     elif fields.get('action')=='status':
      revenue_followups_v23.change_status(c,user['id'],wid,fields.get('id',''),fields.get('status',''))
     else:raise ValueError('Unknown follow-up action')
    return self.redirect('/revenue-followups?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/revenue-priority/live':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:revenue_priority_live.propose_followup(c,user['id'],wid,fields.get('lead',''))
    return self.redirect('/revenue-priority/live?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/business-intelligence-v60':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:business_intelligence_v60.enqueue(c,user['id'],wid,fields.get('code',''))
    return self.redirect('/business-intelligence-v60?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/agent-engine-v61':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='plan':agent_engine_v61.plan(c,user['id'],wid,fields.get('objective',''))
     elif fields.get('action')=='task':agent_engine_v61.approve_as_task(c,user['id'],wid,fields.get('run',''),fields.get('role',''))
     else:raise ValueError('Unknown action')
    return self.redirect('/agent-engine-v61?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/business-collaboration-v62':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='collaborate':business_collaboration_v62.collaborate(c,user['id'],wid,fields.get('objective',''))
     elif action=='enable':business_collaboration_v62.publish(c,user['id'],wid,True)
     elif action=='disable':business_collaboration_v62.publish(c,user['id'],wid,False)
     elif action=='rotate':business_collaboration_v62.rotate(c,user['id'],wid)
     else:raise ValueError('Unknown action')
    return self.redirect('/business-collaboration-v62?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/workflow-v63':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='complete':workflow_v63.execute_internal(c,user['id'],wid,fields.get('job',''),fields.get('notes',''))
     elif action=='outcome':workflow_v63.record_outcome(c,user['id'],wid,fields.get('job',''),fields.get('kind',''),fields.get('amount',''),fields.get('notes',''))
     else:raise ValueError('Unknown action')
    return self.redirect('/workflow-v63?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/integrations-v65':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')!='dispatch':raise ValueError('Unknown action')
     integrations_v65.dispatch(c,user['id'],wid,fields.get('job',''))
    return self.redirect('/integrations-v65?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/native-integrations-v66':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')!='import':raise ValueError('Unknown action')
     native_integrations_v66.import_csv(c,user['id'],wid,fields.get('csv_data',''))
    return self.redirect('/native-integrations-v66?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/hubspot-v67':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')!='sync':raise ValueError('Unknown action')
     hubspot_v67.sync(c,user['id'],wid)
    return self.redirect('/hubspot-v67?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sync-control-v68':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='policy':sync_control_v68.set_policy(c,user['id'],wid,fields.get('cadence',''))
     elif action=='run':sync_control_v68.run(c,user['id'],wid)
     else:raise ValueError('Unknown action')
    return self.redirect('/sync-control-v68?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/hubspot-oauth-v70':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS is not enabled.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='connect':url=hubspot_oauth_v70.begin(c,user['id'],wid)
     elif action=='disconnect':hubspot_oauth_v70.disconnect(c,user['id'],wid)
     elif action=='import':integration_health_v72.import_all(c,user['id'],wid)
     else:raise ValueError('Unknown action')
    if action=='connect':return self.redirect(url)
    return self.redirect('/hubspot-oauth-v70?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p in ('/business-os-v59','/business-agents-v59'):
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1':return self.fail(403,'Business OS V59 is not enabled.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if p=='/business-os-v59':
      if action=='add':business_os_v59.add_lead(c,user['id'],wid,fields.get('name',''),fields.get('contact',''),fields.get('source',''),fields.get('value',''))
      elif action=='import_csv':business_os_v59.import_leads_csv(c,user['id'],wid,fields.get('csv_text',''))
      elif action=='edit_lead':business_os_v59.edit_lead(c,user['id'],wid,fields.get('lead',''),fields.get('name',''),fields.get('contact',''),fields.get('source',''),fields.get('value',''))
      elif action=='status':business_os_v59.update_lead(c,user['id'],wid,fields.get('lead',''),fields.get('status',''))
      elif action=='note':business_os_v59.add_note(c,user['id'],wid,fields.get('lead',''),fields.get('note',''))
      elif action=='add_task':business_os_v59.add_task(c,user['id'],wid,fields.get('lead',''),fields.get('task_title',''),fields.get('due_date',''))
      elif action=='complete_task':business_os_v59.complete_task(c,user['id'],wid,fields.get('task',''))
      elif action=='confirm_fulfillment':business_os_v59.confirm_fulfillment(c,user['id'],wid,fields.get('project',''))
      elif action=='process_business_events':business_os_v59.process_business_events(c,user['id'],wid)
      elif action=='plan_review_jobs':business_os_v59.plan_fulfillment_review_jobs(c,user['id'],wid)
      elif action=='run_review_jobs':business_os_v59.run_fulfillment_review_jobs(c,user['id'],wid)
      elif action=='create_quote':business_os_v59.create_quote(c,user['id'],wid,fields.get('lead',''),fields.get('quote_description',''),fields.get('quote_quantity',''),fields.get('quote_price',''))
      elif action=='add_service':business_os_v59.add_service(c,user['id'],wid,fields.get('service_name',''),fields.get('service_description',''),fields.get('service_price',''))
      elif action=='archive_service':business_os_v59.archive_service(c,user['id'],wid,fields.get('service',''))
      elif action=='quote_service':business_os_v59.quote_from_service(c,user['id'],wid,fields.get('lead',''),fields.get('service',''),fields.get('quantity',''))
      elif action=='quote_status':business_os_v59.update_quote(c,user['id'],wid,fields.get('quote',''),fields.get('quote_status',''))
      elif action=='propose':business_os_v59.propose(c,user['id'],wid,fields.get('lead',''),fields.get('message',''))
      elif action=='review':business_os_v59.review(c,user['id'],wid,fields.get('draft',''),fields.get('decision',''),fields.get('reason',''))
      else:raise ValueError('Unknown action')
     else:
      if action=='create':business_agents_v59.create_job(c,user['id'],wid,fields.get('agent',''),fields.get('goal',''))
      elif action=='propose':business_agents_v59.propose_job(c,user['id'],wid,fields.get('job',''),fields.get('proposal',''))
      elif action=='review':business_agents_v59.review_job(c,user['id'],wid,fields.get('job',''),fields.get('decision',''),fields.get('reason',''))
      elif action=='complete':business_agents_v59.complete_job(c,user['id'],wid,fields.get('job',''))
      elif action=='knowledge':business_agents_v59.add_knowledge(c,user['id'],wid,fields.get('kind',''),fields.get('question',''),fields.get('answer',''))
      elif action=='delete_knowledge':business_agents_v59.remove_knowledge(c,user['id'],wid,fields.get('knowledge',''))
      else:raise ValueError('Unknown action')
    return self.redirect(p+'?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-council-v57':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Council requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','');iid=fields.get('case','')
   try:
    with db() as c:
     if action=='create':sovereign_council_v57.create(c,user['id'],wid,fields.get('node_id',''),fields.get('question',''))
     elif action=='generate':sovereign_council_v57.generate(c,user['id'],wid,iid)
     elif action=='note':sovereign_council_v57.note(c,user['id'],wid,iid,fields.get('role',''),fields.get('position',''),fields.get('statement',''),fields.get('evidence',''))
     elif action=='review':sovereign_council_v57.review(c,user['id'],wid,iid,fields.get('decision',''),fields.get('reason',''))
     else:raise ValueError('Unknown council action')
    return self.redirect('/sovereign-council-v57?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-business-graph-v57':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Business Graph requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='node':sovereign_business_graph_v57.node(c,user['id'],wid,fields.get('type',''),fields.get('name',''),fields.get('description',''),fields.get('confidence',''),fields.get('source',''))
     elif action=='edge':sovereign_business_graph_v57.edge(c,user['id'],wid,fields.get('source_id',''),fields.get('target_id',''),fields.get('relation',''),fields.get('description',''))
     elif action=='archive_node':sovereign_business_graph_v57.archive(c,user['id'],wid,'node',fields.get('record',''))
     else:raise ValueError('Unknown Business Graph action')
    return self.redirect('/sovereign-business-graph-v57?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-opportunities-v57':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Opportunity Radar requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')!='review':raise ValueError('Unknown action')
     sovereign_opportunities_v57.review(c,user['id'],wid,fields.get('fingerprint',''),fields.get('decision',''),fields.get('reason',''))
    return self.redirect('/sovereign-opportunities-v57?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-omniverse-v57':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omniverse requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='enqueue':sovereign_omniverse_v57.enqueue(c,user['id'],wid,fields.get('kind',''),fields.get('key',''))
     elif action=='run':sovereign_omniverse_v57.run_one(c,user['id'],wid,fields.get('job',''))
     elif action=='cancel':sovereign_omniverse_v57.cancel(c,user['id'],wid,fields.get('job',''))
     elif action=='recover':sovereign_omniverse_v57.recover(c,user['id'],wid,fields.get('job',''))
     else:raise ValueError('Unknown Omniverse action')
    return self.redirect('/sovereign-omniverse-v57?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-nexus-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Workflow Nexus requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='rule':sovereign_nexus_v56.set_rule(c,user['id'],wid,fields.get('workflow',''),fields.get('index',''),fields.get('condition',''))
     elif action=='seen':sovereign_nexus_v56.mark_seen(c,user['id'],wid,fields.get('notification',''))
     elif action=='component':sovereign_nexus_v56.save_component(c,user['id'],wid,fields.get('name',''),fields.get('steps',''))
     elif action=='schedule':sovereign_nexus_v56.plan_schedule(c,user['id'],wid,fields.get('workflow',''),fields.get('run_at',''))
     elif action=='dispatch':sovereign_nexus_v56.dispatch_due(c,user['id'],wid,fields.get('schedule',''))
     elif action=='cancel_schedule':sovereign_nexus_v56.cancel_schedule(c,user['id'],wid,fields.get('schedule',''))
     elif action=='branch':sovereign_nexus_v56.review_branch(c,user['id'],wid,fields.get('run',''),fields.get('index',''),fields.get('outcome',''))
     else:raise ValueError('Unknown Nexus action')
    return self.redirect('/sovereign-nexus-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-workflow-runs-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Workflow Operations requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='start':sovereign_workflow_runtime_v56.start(c,user['id'],wid,fields.get('workflow',''))
     elif action in ('metadata','comment'):sovereign_workflow_runtime_v56.annotate(c,user['id'],wid,fields.get('run',''),action,fields.get('priority',''),fields.get('due_date',''),fields.get('owner_label',''),fields.get('summary',''),fields.get('note',''))
     else:sovereign_workflow_runtime_v56.change(c,user['id'],wid,fields.get('run',''),action,fields.get('task',''),fields.get('note',''))
    return self.redirect('/sovereign-workflow-runs-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-workflows-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Workflow Studio requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='create':sovereign_workflows_v56.create(c,user['id'],wid,fields.get('name',''),fields.get('template',''))
     elif action=='note':sovereign_workflows_v56.add_note(c,user['id'],wid,fields.get('workflow',''),fields.get('note',''))
     else:sovereign_workflows_v56.update(c,user['id'],wid,fields.get('workflow',''),action,fields.get('step',''))
    return self.redirect('/sovereign-workflows-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-genesis-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Genesis requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='discover':sovereign_genesis_v56.create_session(c,user['id'],wid)
     elif action=='propose':sovereign_genesis_v56.propose(c,user['id'],wid,fields.get('session',''),fields.get('hypothesis',''))
     elif action in ('approve','stop','complete'):sovereign_genesis_v56.update(c,user['id'],wid,fields.get('experiment',''),action,fields.get('observed'),fields.get('notes',''))
     else:raise ValueError('Unknown Genesis action')
    return self.redirect('/sovereign-genesis-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-guardian-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Guardian requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='scan':sovereign_guardian_v56.evaluate(c,user['id'],wid)
     elif action=='status':sovereign_guardian_v56.update_status(c,user['id'],wid,fields.get('alert_id',''),fields.get('status',''))
     else:raise ValueError('Unknown Guardian action')
    return self.redirect('/sovereign-guardian-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-connectors-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Connectors require local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='create':sovereign_connectors_v56.create_source(c,user['id'],wid,fields.get('name',''))
     elif action=='stage':sovereign_connectors_v56.ingest(c,user['id'],wid,fields.get('source_id',''),fields.get('filename',''),fields.get('csv_data','').encode('utf-8'))
     elif action=='apply':sovereign_connectors_v56.apply(c,user['id'],wid,fields.get('batch_id',''))
     else:raise ValueError('Unknown connector action')
    return self.redirect('/sovereign-connectors-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-executive-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Executive Council requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:sovereign_executive_v56.run(c,user['id'],wid,fields.get('objective','overview'))
    return self.redirect('/sovereign-executive-v56?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-future-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Future simulator requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:sovereign_future_v56.run(c,user['id'],wid,fields.get('months',''),fields.get('revenue_pct',''),fields.get('expense_pct',''),fields.get('shock_pct',''),fields.get('opening_cash',''))
    return self.redirect('/sovereign-future-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.IntegrityError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-memory-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Memory requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     sovereign_memory_v56.record(c,user['id'],wid,fields.get('kind',''),fields.get('title',''),fields.get('body',''),fields.get('result','unknown'),job_id=fields.get('job_id',''),supersedes_id=fields.get('supersedes_id',''))
    return self.redirect('/sovereign-memory-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.IntegrityError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-execution-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Execution requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');op=fields.get('action','')
   try:
    with db() as c:
     if op=='propose':sovereign_execution_v56.propose(c,user['id'],wid,fields.get('strategy_id',''),fields.get('scenario_code',''),fields.get('idempotency_key',''))
     elif op in ('approve','reject','queue','cancel'):sovereign_execution_v56.change(c,user['id'],wid,fields.get('job_id',''),op)
     elif op in ('pause','resume'):sovereign_execution_v56.set_pause(c,user['id'],wid,op=='pause')
     elif op=='dispatch':sovereign_execution_v56.dispatch_one(c,user['id'],wid)
     else:raise ValueError('Unknown execution action')
    return self.redirect('/sovereign-execution-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.IntegrityError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-strategies-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Strategy simulation requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');key=fields.get('opportunity_key','')
   try:
    with db() as c:sovereign_strategy_v56.run(c,user['id'],wid,key)
    return self.redirect('/sovereign-strategies-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.IntegrityError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-opportunities-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Opportunity discovery requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:sovereign_opportunities_v56.run(c,user['id'],wid)
    return self.redirect('/sovereign-opportunities-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.IntegrityError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-sync-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sync requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:sovereign_sync_v56.apply(c,user['id'],wid)
    return self.redirect('/sovereign-sync-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,sqlite3.IntegrityError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-twin-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Digital Twin requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:
     if fields.get('action')=='node':sovereign_twin_v56.add_node(c,user['id'],wid,fields.get('kind',''),fields.get('name',''),fields.get('source',''))
     elif fields.get('action')=='edge':sovereign_twin_v56.add_edge(c,user['id'],wid,fields.get('from_id',''),fields.get('to_id',''),fields.get('relation',''),fields.get('source',''))
     else:raise ValueError('Unknown graph operation')
    return self.redirect('/sovereign-twin-v56?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-council-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign Council requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:sovereign_intelligence_v56.run(c,user['id'],wid,fields.get('objective',''))
    return self.redirect('/sovereign-council-v56?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='import':
      if not uploaded:raise ValueError('Select a CSV file')
      filename,data=uploaded
      sovereign_v56.import_csv(c,user['id'],wid,filename,data)
     elif action=='propose':sovereign_v56.propose(c,user['id'],wid,fields.get('key',''))
     elif action in ('approve','reject','complete'):sovereign_v56.transition(c,user['id'],wid,fields.get('id',''),action,fields.get('outcome',''))
     else:raise ValueError('Unknown Sovereign action')
    return self.redirect('/sovereign-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,OverflowError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/foundation':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Foundation requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=foundation_v26.render(c,user['id'],csrf,q.get('w',[''])[0],db_path=DB)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Foundation V26',body,user,csrf))
  if p=='/nexus-intelligence':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Nexus requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=nexus_v25.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Nexus Intelligence V25',body,user,csrf))
  if p=='/oracle':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Oracle requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=oracle_v24.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Oracle V24',body,user,csrf))
  if p=='/sentience':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sentience requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=sentience_v23.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Sentience V23',body,user,csrf))
  if p=='/autonomy':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Autonomy requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=autonomy_v22.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Autonomy V22',body,user,csrf))
  if p=='/architect':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Architect requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=architect_v21.render(c,user['id'],csrf,q.get('w',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Architect V21',body,user,csrf))
  if p=='/site-studio' and os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE:
   with db() as c: body=site_studio.studio(c,user['id'],csrf)
   body+='<section class="panel"><a href="/site-agent">Open Business Agent Workspace</a></section>'
   return self.respond(200,shell('Site Studio',body,user,csrf))
  if p=='/site-agent' and os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE:
   with db() as c: body=site_studio.agent_workspace(c,user['id'],csrf)
   return self.respond(200,shell('Business Agent',body,user,csrf))
  if p=='/site-preview' and os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE:
   company_id=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
   with db() as c: body=site_studio.preview(c,user['id'],company_id)
   return self.respond(200,body) if body else self.fail(404,'Draft not found',user,csrf)
  if p=='/workspace':
   with db() as c: body=intelligence_v45.render(c,user['id'])+business_v4.render(c,user['id'],csrf)+business_v3.render(c,user['id'],csrf)
   shortcuts=('''<section class="panel" aria-label="Workspace quick navigation"><h2>Business Workspace</h2><p>Pick up where you left off or jump straight to the tools you already use.</p><nav class="workspace-shortcuts" aria-label="Business tools"><a href="/business-os-v59">Leads &amp; customers</a><a href="/business-agents-v59">Business agents</a><a href="/sovereign-opportunities-v57">Opportunities</a><a href="/sovereign-workflows-v56">Workflows</a><a href="/">Sales reports</a><a href="/account">Account &amp; access</a></nav></section>''')
   body=shortcuts+body
   return self.respond(200,shell('Business Workspace',body,user,csrf))
  if p=='/agents':
   if user['role']!='admin':return self.fail(403,'Founder access required.',user,csrf)
   return self.respond(200,shell('Founder Agent Control',render_agents(csrf),user,csrf))
  if p=='/sovereign':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign requires local studio mode.',user,csrf)
   with db() as c:body=sovereign_v8.render(c,user['id'],csrf,urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0])
   return self.respond(200,shell('Sovereign V8',body,user,csrf))
  if p=='/infinity/export':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Infinity requires local SQLite studio mode.',user,csrf)
   aid=(query.get('app') or [''])[0]
   try:
    with db() as c:payload=infinity_v18.package(c,user['id'],aid)
   except (ValueError,KeyError,TypeError) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,payload,'application/zip',[('Content-Disposition','attachment; filename="infinity-validation-workbench.zip"'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
  if p=='/infinity':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Infinity requires local SQLite studio mode.',user,csrf)
   with db() as c:body=infinity_v18.render(c,user['id'])
   return self.respond(200,shell('Infinity V18',body,user,csrf))
  if p=='/phoenix/export':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Phoenix requires local SQLite studio mode.',user,csrf)
   aid=(query.get('app') or [''])[0]
   try:
    with db() as c:payload=phoenix_v17.package(c,user['id'],aid)
   except (ValueError,KeyError,TypeError) as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,payload,'application/zip',[('Content-Disposition','attachment; filename="phoenix-repair-workbench.zip"'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
  if p=='/phoenix':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Phoenix requires local SQLite studio mode.',user,csrf)
   with db() as c:body=phoenix_v17.render(c,user['id'])
   return self.respond(200,shell('Phoenix V17',body,user,csrf))
  if p=='/evolution/export':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Evolution requires local SQLite studio mode.',user,csrf)
   aid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('app',[''])[0]
   try:
    with db() as c:payload=evolution_v16.package(c,user['id'],aid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,payload,'application/zip',[('Content-Disposition','attachment; filename="evolution-inspected-app.zip"'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
  if p=='/evolution':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Evolution requires local SQLite studio mode.',user,csrf)
   with db() as c:body=evolution_v16.render(c,user['id'])
   return self.respond(200,shell('Evolution V16',body,user,csrf))
  if p=='/genesis-prime':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Genesis Prime requires local SQLite studio mode.',user,csrf)
   q=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   try:
    with db() as c:body=genesis_prime_v20.render(c,user['id'],csrf,q.get('w',[''])[0],q.get('app',[''])[0])
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Genesis Prime V20',body,user,csrf))
  if p=='/omega/export':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omega requires local SQLite studio mode.',user,csrf)
   aid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('app',[''])[0]
   try:
    with db() as c:payload=omega_v15.package(c,user['id'],aid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.respond(200,payload,'application/zip',[('Content-Disposition','attachment; filename="omega-local-app.zip"'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
  if p=='/empire':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1' and (os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE):return self.fail(403,'Business workspace is not enabled.',user,csrf)
   wid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('w',[''])[0]
   try:
    with db() as c:body=empire_v19.render(c,user['id'],csrf,wid)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Empire V19',body,user,csrf))
  if p=='/omega':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omega requires local SQLite studio mode.',user,csrf)
   with db() as c:body=omega_v15.render(c,user['id'],'')
   return self.respond(200,shell('Omega V15',body,user,csrf))
  if p=='/prometheus/manifest':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Prometheus requires local SQLite studio mode.',user,csrf)
   aid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('app',[''])[0]
   try:
    with db() as c:payload=prometheus_v14.manifest(c,user['id'],aid)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,payload,'application/json; charset=utf-8',[('Content-Disposition','attachment; filename="prometheus-manifest.json"'),('Cache-Control','no-store')])
  if p=='/prometheus':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Prometheus requires local SQLite studio mode.',user,csrf)
   aid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('app',[''])[0]
   try:
    with db() as c:body=prometheus_v14.render(c,user['id'],csrf,aid)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Prometheus V14',body,user,csrf))
  if p=='/singularity-x/export':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'V13 requires local SQLite studio mode.',user,csrf)
   aid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('app',[''])[0]
   try:
    with db() as c:payload=singularity_x_v13.export(c,user['id'],aid)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,payload,'application/json; charset=utf-8',[('Content-Disposition','attachment; filename="velxtria-app.json"'),('Cache-Control','no-store')])
  if p=='/singularity-x':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'V13 requires local SQLite studio mode.',user,csrf)
   aid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('app',[''])[0]
   try:
    with db() as c:body=singularity_x_v13.render(c,user['id'],csrf,aid)
   except ValueError as exc:return self.fail(404,str(exc),user,csrf)
   return self.respond(200,shell('Singularity X V13',body,user,csrf))
  if p=='/omnipotence':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omnipotence requires local SQLite studio mode.',user,csrf)
   with db() as c:body=omnipotence_v12.render(c,user['id'],csrf)
   return self.respond(200,shell('Omnipotence V12',body,user,csrf))
  if p=='/recovery':return self.respond(200,shell('Titan Recovery Center',recovery_v11.render(),user,csrf))
  if p=='/trinity':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Trinity requires local studio mode.',user,csrf)
   query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
   with db() as c:body=trinity_v10.render(c,user['id'],csrf,query.get('tab',['genesis'])[0],query.get('app',[''])[0])
   return self.respond(200,shell('Trinity V10',body,user,csrf))
  if p=='/constellation':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Constellation requires local studio mode.',user,csrf)
   with db() as c:body=constellation_v9.render(c,user['id'],csrf,urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0])
   return self.respond(200,shell('Constellation V9',body,user,csrf))
  if p=='/omniscience':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omniscience requires local studio mode.',user,csrf)
   with db() as c:body=omni_v7.render(c,user['id'],csrf,urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0])
   return self.respond(200,shell('Omniscience V7',body,user,csrf))
  if p=='/singularity':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Singularity requires local studio mode.',user,csrf)
   with db() as c: body=singularity_v6.render(c,user['id'],csrf,urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0])
   return self.respond(200,shell('Singularity AI',body,user,csrf))
  if p=='/mission-actions':
   with db() as c: body=mission_v53.render(c,user['id'],urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0],csrf)
   return self.respond(200,shell('Mission Actions',body,user,csrf))
  if p=='/missions':
   with db() as c: body=mission_v52.render(c,user['id'],csrf)
   return self.respond(200,shell('Mission Control',body,user,csrf))
  if p=='/operator':
   with db() as c: body=operator_v5.render(c,user['id'],csrf)
   return self.respond(200,shell('Business Operator',body,user,csrf))
  if p=='/account':
   # ?paid=1 is the return from BTCPay after a payment: a hint to look,
   # never proof. Re-verify against BTCPay first; the confirmation panel
   # below only ever shows the verified state (or that verification
   # failed). With no mainnet order at all the parameter is ignored.
   paid=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('paid',[''])[0]=='1'
   verify_failed=False
   if paid and btcpay_mainnet.configured():
    try:
     with db() as c:btcpay_mainnet.reconcile(c,user['id'])
    except RuntimeError:
     verify_failed=True
   with db() as c: licensed=c.execute('SELECT license_key FROM paid_licenses WHERE user_id=?',(user['id'],)).fetchone()
   state='No redeemed license'
   if licensed:
    try:
     license_verification.verify(licensed[0],user['email'])
     state='Payhip license verified and active'
    except license_verification.LicenseError: state='License invalid, disabled or refunded — paid access inactive'
    except license_verification.LicenseUnavailable: state='License verification unavailable — paid access temporarily inactive'
   body='<section class="panel"><h1>Account</h1><p>'+escape(user['email'])+'</p><p>Payhip license status: '+escape(state)+'</p><p>Existing demo reporting remains available. License redemption does not change your demo quota.</p><form method="post" action="/redeem-license"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><label>Payhip license key<input name="license_key" maxlength="120" autocomplete="off" required></label><button>Verify and redeem license</button></form></section>' 
   with db() as c:
    ent=subscriptions.entitlement(c,user['id'])
    mainnet_orders=c.execute("SELECT order_id,status,checkout_url,created_at,settled_at FROM btcpay_orders WHERE user_id=? AND network='mainnet' ORDER BY created_at DESC LIMIT 30",(user['id'],)).fetchall()
    orders=c.execute("SELECT order_id,status,created_at,settled_at FROM btcpay_orders WHERE user_id=? AND network='testnet' ORDER BY created_at DESC LIMIT 30",(user['id'],)).fetchall()
   datefmt=lambda ts: datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if ts else '—'
   confirm=''
   if paid and mainnet_orders:
    if verify_failed:
     confirm='<section class="panel"><h2>Checking your payment</h2><p>We could not reach BTCPay to verify your payment just now. Nothing has been confirmed on your VELXTRIA account yet — use Check payment status below to try again.</p></section>'
    elif ent['plan']=='pro':
     confirm='<section class="panel"><h2>Payment received — PRO is active</h2><p>Your $49 Bitcoin payment settled and PRO is active through '+escape(datefmt(ent['end']))+'. You have 50 reports per billing cycle.</p></section>'
    else:
     confirm='<section class="panel"><h2>Thanks — your payment is being confirmed</h2><p>BTCPay has your payment and the Bitcoin network is confirming it. PRO activates automatically once it settles — usually within a few minutes. Use Check payment status below to refresh.</p></section>'
   billing='<section class="panel" id="billing"><h2>Bitcoin billing</h2><p>PRO: '+('Active through '+escape(datefmt(ent['end'])) if ent['plan']=='pro' else 'Not currently active')+'. Payments are Bitcoin only and verified automatically against BTCPay; a browser redirect alone never activates PRO.</p>'
   pending_acct=next(({'order_id':o[0],'checkout_url':o[2]} for o in mainnet_orders if o[1]=='pending'),None)
   billing+=renewal_html(user,csrf,ent,pending_acct)
   if btcpay_mainnet.checkout_enabled() and ent['plan']!='pro':
    billing+='<form method="post" action="/btcpay/mainnet/checkout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button>Pay $49 with Bitcoin — PRO · 30 days · 50 reports</button></form>'
   if any(o[1]=='pending' for o in mainnet_orders):
    billing+='<form method="post" action="/btcpay/mainnet/check-status"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button>Check payment status</button></form>'
   billing+='<div class="scroll"><table><thead><tr><th>Order</th><th>Created (UTC)</th><th>Status</th><th>Settled (UTC)</th><th>Checkout</th></tr></thead><tbody>'
   for oid,status,checkout_url,created,settled in mainnet_orders:
    link='<a href="'+escape(checkout_url)+'">Pay</a>' if status=='pending' and checkout_url else '—'
    billing+='<tr><td>'+escape(oid)+'</td><td>'+escape(datefmt(created))+'</td><td>'+escape(status)+'</td><td>'+escape(datefmt(settled))+'</td><td>'+link+'</td></tr>'
   billing+='</tbody></table></div></section>'
   billing+='<section class="panel"><h2>Legacy testnet billing history</h2><p>Test payments only; no real funds. Payments are manual; no automatic charges.</p><div class="scroll"><table><thead><tr><th>Order</th><th>Created (UTC)</th><th>Status</th><th>Settled (UTC)</th></tr></thead><tbody>'
   for oid,status,created,settled in orders:
    billing+='<tr><td>'+escape(oid)+'</td><td>'+escape(datefmt(created))+'</td><td>'+escape(status)+'</td><td>'+escape(datefmt(settled))+'</td></tr>'
   billing+='</tbody></table></div></section>'
   return self.respond(200,shell('Account',confirm+body+billing,user,csrf))
  if p=='/report':
   ident=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
   with db() as c:row=c.execute("SELECT id,filename,created,status,accepted,rejected,digest FROM reports WHERE id=? AND user_id=? AND status='ready'",(ident,user['id'])).fetchone()
   if not row:return self.fail(404,'Report not found.',user,csrf)
   try: report_bytes=persistent.retrieve(user['id'],ident,REPORTS)
   except (OSError,RuntimeError):return self.fail(503,'Report file temporarily unavailable.',user,csrf)
   if not hmac.compare_digest(hashlib.sha256(report_bytes).hexdigest(),row[6]):
    return self.fail(503,'Report integrity verification failed. Please contact support.',user,csrf)
   try:monthly_rows,product_rows,stats=read_report_summaries(report_bytes)
   except ValueError:return self.fail(503,'Report file temporarily unavailable.',user,csrf)
   return self.respond(200,shell('Report',report_view_html(row[:6],monthly_rows,product_rows,stats),user,csrf),headers=[('Cache-Control','no-store')])
  if p=='/download':
   ident=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
   with db() as c:row=c.execute("SELECT id,digest FROM reports WHERE id=? AND user_id=? AND status='ready'",(ident,user['id'])).fetchone()
   if not row:return self.fail(404,'Report not found.',user,csrf)
   try: report_bytes=persistent.retrieve(user['id'],ident,REPORTS)
   except (OSError,RuntimeError):return self.fail(503,'Report file temporarily unavailable.',user,csrf)
   if not hmac.compare_digest(hashlib.sha256(report_bytes).hexdigest(),row[1]):
    return self.fail(503,'Report integrity verification failed. Please contact support.',user,csrf)
   return self.respond(200,report_bytes,'application/zip',[('Content-Disposition','attachment; filename="VELXTRIA_Report.zip"')])
  return self.fail(404,'Page not found.',user,csrf)
 def redirect(self,path,headers=()):return self.respond(303,b'','text/plain',[('Location',path),*headers])
 def post_data(self):
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ValueError('Invalid request size')
  if n<=0:raise ValueError('Empty request — no form data received.')
  if n>MAX_BYTES+65536:raise ValueError('Upload too large (maximum 5 MB)')
  raw=self.rfile.read(n);ct=self.headers.get('Content-Type','')
  if ct.startswith('application/x-www-form-urlencoded'):
   return {k:v[0] for k,v in urllib.parse.parse_qs(raw.decode('utf-8'),keep_blank_values=True).items()},None
  if ct.startswith('multipart/form-data'):
   # Minimal bounded multipart parser: one file and a CSRF field; no external dependencies.
   from email.parser import BytesParser
   from email.policy import default
   msg=BytesParser(policy=default).parsebytes(b'MIME-Version: 1.0\r\nContent-Type: '+ct.encode()+b'\r\n\r\n'+raw)
   if not msg.is_multipart():raise ValueError('Invalid upload')
   fields={};uploaded=None
   for part in msg.iter_parts():
    name=part.get_param('name',header='content-disposition')
    if name=='csrf':fields['csrf']=part.get_content().strip()
    elif name in ('email_report','workspace','action','opportunity_key','strategy_id','scenario_code','idempotency_key','job_id','kind','title','body','result','supersedes_id'):
     value=part.get_content()
     if not isinstance(value,str) or len(value)>(4000 if name=='body' else 256):raise ValueError('Invalid form field')
     fields[name]=value.strip()
    elif name=='file':
     if uploaded is not None:raise ValueError('Only one file allowed')
     uploaded=(part.get_filename() or '',part.get_payload(decode=True) or b'')
   return fields,uploaded
  raise ValueError('Unsupported form type')
 def do_POST(self):
  secure='; Secure' if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview' else ''
  if self.preview_guard(): return
  p=urllib.parse.urlsplit(self.path).path
  if p=='/webhooks/payhip':
   # A staging endpoint: never grants access or changes the user's account.
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<=0 or n>65536:return self.respond(413,'Invalid webhook size','text/plain')
    raw=self.rfile.read(n)
    with db() as c:
     status,message=payhip_integration.accept_event(c,raw)
     if status==200 and message=='Received for review (no access granted)':
      record=json.loads(raw)
      kind=record.get('type','')
      email=record.get('customer_email','') if kind.startswith('subscription.') else record.get('email','')
      ref=record.get('subscription_id','') if kind.startswith('subscription.') else record.get('id','')
      subscriptions.observe_webhook(c,email,kind,ref)
    return self.respond(status,message,'text/plain')
   except (ValueError,UnicodeError):return self.respond(400,'Invalid webhook','text/plain')
  if p=='/webhooks/btcpay':
   # Production BTCPay webhook: the signature is verified first, and the
   # delivery is only a trigger to re-verify the invoice against BTCPay.
   # A webhook payload alone never grants access.
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<=0 or n>65536:return self.respond(413,'Invalid webhook size','text/plain')
    raw=self.rfile.read(n)
    with db() as c:
     status,message=btcpay_mainnet.handle_webhook(c,raw,self.headers.get('BTCPay-Sig',''))
    return self.respond(status,message,'text/plain')
   except Exception as exc:
    print('BTCPay webhook error:',type(exc).__name__)
    return self.respond(503,'Webhook temporarily unavailable','text/plain')
  try:fields,uploaded=self.post_data()
  except Exception as e:return self.fail(400,str(e))
  if p=='/forgot':
   # The reply never reveals whether the email has an account, and when
   # SMTP is not configured no reset is promised at all.
   if not notifications.email_configured():
    return self.respond(200,shell('Reset password','<section class="panel narrow"><h1>Reset by email is not available yet</h1><p>Password reset by email is not set up on this site yet. Email <a href="/contact">support</a> and we will help you back in.</p><p><a href="/login">Back to sign in</a></p></section>'))
   email=fields.get('email','').strip().lower()
   if valid_email(email):
    with db() as c:
     row=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
     if row:password_reset.request_reset(c,row[0],email,btcpay_mainnet.site_url())
   return self.respond(200,shell('Reset password','<section class="panel narrow"><h1>Check your email</h1><p>If an account exists for that email, a reset link is on its way. It works once and expires in one hour.</p><p><a href="/login">Back to sign in</a></p></section>'))
  if p=='/reset':
   token=fields.get('token','');password=fields.get('password','')
   if len(password)<12 or len(password)>256:return self.fail(400,'Use a password of 12–256 characters.')
   with db() as c:
    uid=password_reset.consume_token(c,token)
    if uid is None:return self.fail(400,'This reset link is expired or already used.')
    password_reset.set_password(c,uid,password)
    c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
   return self.redirect('/login?reset=1')
  if p=='/register':
   email=fields.get('email','').strip().lower();password=fields.get('password','')
   if not valid_email(email) or len(password)<12 or len(password)>256:return self.fail(400,'Use a valid email and password of 12–256 characters.')
   salt=secrets.token_hex(16)
   try:
    with db() as c:
     c.execute('INSERT INTO users(email,salt,pw_hash,role,access,created) VALUES (?,?,?,?,?,?)',(email,salt,pw_hash(password,salt),'customer','demo',now()))
     site_stats.record(c,'signup')
     uid=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()[0]
     ref=fields.get('ref','').strip()
     if not ref:
      cookie=SimpleCookie()
      try:cookie.load(self.headers.get('Cookie',''))
      except Exception:pass
      morsel=cookie.get(referrals.COOKIE_NAME)
      ref=morsel.value if morsel else ''
     if referrals.record_signup(c,uid,ref) is not None:
      site_stats.record(c,'referral_signup')
   except (sqlite3.IntegrityError, persistent_integrity_error()):return self.fail(409,'Account already exists.')
   nxt=safe_next(fields.get('next',''))
   dest='/login?registered=1'
   if nxt!='/':dest+='&next='+urllib.parse.quote(nxt,safe='')
   return self.redirect(dest)
  if p=='/login':
   email=fields.get('email','').strip().lower();password=fields.get('password','')
   with db() as c:row=c.execute('SELECT id,salt,pw_hash FROM users WHERE email=?',(email,)).fetchone()
   if not row or not hmac.compare_digest(pw_hash(password,row[1]),row[2]):return self.fail(401,'Invalid email or password.')
   token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
   with db() as c:c.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row[0],now()+86400,csrf))
   secure='; Secure' if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview' else ''
   return self.redirect(safe_next(fields.get('next','')),[('Set-Cookie','velxtria_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+secure)])
  if p=='/try':
   # Instant demo: no account, no session, no CSRF token. The POST changes
   # no state (no user, no report row, no stored file — the ZIP lives in
   # memory for 10 minutes), so there is nothing a forged request could
   # alter; the same CPU exposure already exists on the public sample report.
   if not uploaded:return self.demo_fail('Choose a CSV file.')
   filename,data=uploaded
   try:
    validate_csv_upload(filename,data,columns_hint='Check the required column headers below the demo form and try again.')
    report=run_report_engine(data)
   except ValueError as exc:return self.demo_fail(str(exc))
   except Exception as exc:return self.demo_fail('Could not process this file: '+str(exc)[:240])
   token=store_demo_zip(report['zip_bytes'],report['accepted'],report['rejected'],filename)
   with db() as c:
    site_stats.record(c,'demo_run','accepted=%d rejected=%d'%(report['accepted'],report['rejected']))
    share_token=demo_shares.create(c,report)
   user,csrf,_=self.identity()
   headers=[('Set-Cookie',DEMO_COOKIE+'='+token+'; Path=/; Max-Age=600; SameSite=Lax')]
   return self.respond(200,shell('Your demo report',demo_result_html(report,token,share_token,user,csrf)),headers=headers)
  if p=='/demo/email':
   # Anonymous demo lead capture: email the demo report to the runner.
   # No account, no session, no CSRF token — like /try, the request
   # changes no account state, and the send itself is bounded (one email
   # per address+demo ever, at most 3 demo emails per address per day),
   # so a forged or abusive request can at most send one report email.
   email=fields.get('email','').strip().lower()
   share_token=fields.get('share_token','').strip()
   if not valid_email(email):
    return self.respond(400,shell('Email this report','<section class="panel narrow"><h1>Enter a valid email address</h1><p>We need a valid email to send your demo report to.</p><p><a href="/#try">Back to the demo</a></p></section>'))
   if not share_token or '/' in share_token:
    return self.respond(404,'This shared demo has expired or does not exist.','text/plain')
   with db() as c:
    shared=demo_shares.get(c,share_token)
    if not shared:
     return self.respond(404,'This shared demo has expired or does not exist.','text/plain')
    site_url=btcpay_mainnet.site_url()
    share_link=site_url.rstrip('/')+'/demo/'+share_token
    if demo_leads.record(c,email,share_token):
     notifications.queue(
      c, email, 'Your VELXTRIA demo report',
      demo_leads.format_email_body(shared,share_link,site_url),
      'demo_report', dedupe_key='demo-email:'+email+':'+share_token)
     site_stats.record(c,'demo_email_sent',share_token)
   return self.respond(200,shell('Report on its way','<section class="panel narrow"><h1>Check your email</h1><p>Your demo report is on its way to '+escape(email)+'. It includes the summaries, a link to view it online, and a link to create your free account.</p><p><a href="'+escape(share_link)+'">View the report online</a> · <a href="/register">Create your free account</a></p></section>'))
  ident=self.require()
  if not ident:return
  user,csrf,token=ident
  if not hmac.compare_digest(fields.get('csrf',''),csrf):return self.fail(403,'Session verification failed.',user,csrf)
  if p=='/ascension-workflow-create':
   try:
    with db() as c:ascension_workflows.create(c,user['id'],fields.get('action_id',''))
    return self.redirect('/ascension-workflows')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/ascension-workflow-transition':
   try:
    with db() as c:ascension_workflows.transition(c,user['id'],fields.get('workflow_id',''),fields.get('decision',''),fields.get('note',''))
    return self.redirect('/ascension-workflows')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/ascension-followup-prepare':
   try:
    with db() as c:ascension_followups.prepare(c,user['id'],fields.get('action_id',''))
    return self.redirect('/ascension-followups')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/ascension-followup-revise':
   try:
    with db() as c:ascension_followups.revise(c,user['id'],fields.get('draft_id',''),fields.get('subject',''),fields.get('body',''))
    return self.redirect('/ascension-followups')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/ascension-outcome':
   try:
    with db() as c:ascension_recovery.record(c,user['id'],fields.get('action_id',''),fields.get('outcome',''),fields.get('amount','0'),fields.get('evidence',''))
    return self.redirect('/ascension-recovery')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/ascension-action':
   try:
    with db() as c:sovereign_ascension.action(c,user['id'],fields.get('lead_id',''),fields.get('kind',''),fields.get('decision',''),fields.get('note',''))
    return self.redirect('/ascension')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/outreach-gmail-import':
   try:
    with db() as c:sales_pipeline.import_gmail_notices(c,user['id'],fields.get('notices',''))
    return self.redirect('/sales-pipeline')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/outreach-bounce-import':
   try:
    with db() as c:sales_pipeline.import_bounce_lines(c,user['id'],fields.get('bounce_lines',''))
    return self.redirect('/sales-pipeline')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/outreach-suppression':
   try:
    with db() as c:
     sales_pipeline.set_suppression(c,user['id'],fields.get('email',''),fields.get('status',''),fields.get('reason',''))
    return self.redirect('/sales-pipeline')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sales-pipeline':
   try:
    with db() as c:sales_pipeline.save(c,user['id'],fields)
    return self.redirect('/sales-pipeline')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/logout':
   with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
   secure='; Secure' if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview' else ''
   return self.redirect('/login',[('Set-Cookie','velxtria_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+secure)])
  if p=='/sovereign-council-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign Council requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','')
   try:
    with db() as c:sovereign_intelligence_v56.run(c,user['id'],wid,fields.get('objective',''))
    return self.redirect('/sovereign-council-v56?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sovereign-v56':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign requires local SQLite studio mode.',user,csrf)
   wid=fields.get('workspace','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='import':
      if not uploaded:raise ValueError('Select a CSV file')
      filename,data=uploaded
      sovereign_v56.import_csv(c,user['id'],wid,filename,data)
     elif action=='propose':sovereign_v56.propose(c,user['id'],wid,fields.get('key',''))
     elif action in ('approve','reject','complete'):sovereign_v56.transition(c,user['id'],wid,fields.get('id',''),action,fields.get('outcome',''))
     else:raise ValueError('Unknown Sovereign action')
    return self.redirect('/sovereign-v56?w='+urllib.parse.quote(wid,safe=''))
   except (ValueError,OverflowError) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/foundation':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Foundation requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','')
    with db() as c:
     if empire_v19.role(c,user['id'],wid)!='owner':raise ValueError('Only workspace owners can create backups')
     if fields.get('action')!='backup':raise ValueError('Unknown Foundation action')
     info=foundation_v26.backup(DB,user['id'],DATA_ROOT/'foundation_backups')
     body=foundation_v26.render(c,user['id'],csrf,wid,'Verified backup created: '+info['file']+' · SHA-256 '+info['sha256'],DB)
    return self.respond(200,shell('Foundation V26',body,user,csrf))
   except (ValueError,OSError,sqlite3.Error) as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/omniscience':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omniscience requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','')
    with db() as c:
     if fields.get('action')=='log':omniscience_v49.log_effort(c,user['id'],wid,fields.get('step',''),fields.get('hours',''),fields.get('date',''),fields.get('note',''))
     else:raise ValueError('Unknown Omniscience action')
    return self.redirect('/omniscience?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/quantum-command':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Quantum Command requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','')
    with db() as c:
     action=fields.get('action','')
     if action=='capacity':quantum_command_v48.set_capacity(c,user['id'],wid,fields.get('hours',''))
     elif action=='estimate':quantum_command_v48.set_estimate(c,user['id'],wid,fields.get('step',''),fields.get('hours',''))
     else:raise ValueError('Unknown Quantum Command action')
    return self.redirect('/quantum-command?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/hyperion':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Hyperion requires local SQLite studio mode.',user,csrf)
   try:
    wid=fields.get('workspace','');action=fields.get('action','')
    with db() as c:
     if action=='create':hyperion_v47.create_plan(c,user['id'],wid,fields.get('experiment',''),fields.get('title',''),fields.get('due',''))
     elif action=='add':hyperion_v47.add_step(c,user['id'],wid,fields.get('plan',''),fields.get('title',''),fields.get('description',''),fields.get('due',''),fields.get('depends',''))
     elif action=='transition':hyperion_v47.transition(c,user['id'],wid,fields.get('step',''),fields.get('status',''),fields.get('proof',''))
     elif action=='close':hyperion_v47.close_plan(c,user['id'],wid,fields.get('plan',''))
     else:raise ValueError('Unknown Hyperion action')
    return self.redirect('/hyperion?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/evolution-engine':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Evolution Engine requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     wid=fields.get('workspace','');action=fields.get('action','')
     if action=='generate':evolution_engine_v46.generate(c,user['id'],wid)
     elif action in ('submit','dismiss'):evolution_engine_v46.decide(c,user['id'],wid,fields.get('proposal',''),action)
     else:raise ValueError('Unknown Evolution Engine action')
    return self.redirect('/evolution-engine?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/synapse':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Synapse requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     wid=fields.get('workspace','');action=fields.get('action','');eid=fields.get('experiment','')
     if action=='task-create':synapse_v44.create_task(c,user['id'],wid,eid,fields.get('title',''),fields.get('description',''))
     elif action=='task-status':synapse_v44.update_task(c,user['id'],wid,fields.get('task',''),fields.get('status',''),fields.get('proof',''))
     elif action=='snapshot':synapse_v44.snapshot(c,user['id'],wid,eid,fields.get('note',''))
     elif action=='finalize':synapse_v44.finalize(c,user['id'],wid,eid,fields.get('notes',''))
     else:raise ValueError('Unknown Synapse action')
    return self.redirect('/synapse?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/autonomous-core':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Autonomous Core requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     wid=fields.get('workspace','');action=fields.get('action','');eid=fields.get('experiment','')
     if action=='propose':autonomous_core_v43.propose(c,user['id'],wid,fields.get('goal',''),fields.get('title',''),fields.get('hypothesis',''),fields.get('planned_action',''),fields.get('direction',''))
     elif action in ('approve','reject'):autonomous_core_v43.decision(c,user['id'],wid,eid,action=='approve')
     elif action=='complete':synapse_v44.finalize(c,user['id'],wid,eid,fields.get('notes',''))
     elif action=='cancel':autonomous_core_v43.cancel(c,user['id'],wid,eid)
     else:raise ValueError('Unknown Autonomous Core action')
    return self.redirect('/autonomous-core?w='+urllib.parse.quote(wid,safe=''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/nexus-intelligence':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Nexus requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     wid=fields.get('workspace','');action=fields.get('action','')
     if action=='create':nexus_v25.create_goal(c,user['id'],wid,fields.get('app',''),fields.get('title',''),fields.get('metric',''),fields.get('field',''),fields.get('target',''),fields.get('threshold',''))
     elif action=='snapshot':nexus_v25.measure(c,user['id'],wid,fields.get('goal',''),True)
     elif action=='propose':nexus_v25.propose(c,user['id'],wid,fields.get('goal',''),fields.get('ai','')=='yes')
     elif action in ('approve','reject'):nexus_v25.decide(c,user['id'],wid,fields.get('strategy',''),action=='approve')
     else:raise ValueError('Unknown Nexus action')
     body=nexus_v25.render(c,user['id'],csrf,wid,'Action completed')
    return self.respond(200,shell('Nexus Intelligence V25',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/oracle':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Oracle requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     wid=fields.get('workspace','')
     result=oracle_v24.answer(c,user['id'],wid,fields.get('question',''),fields.get('ai','')=='yes')
     body=oracle_v24.render(c,user['id'],csrf,wid,result)
    return self.respond(200,shell('Oracle V24',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/sentience':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sentience requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     action=fields.get('action','');wid=fields.get('workspace','')
     if action=='recommend':sentience_v23.recommend(c,user['id'],wid,fields.get('app',''),fields.get('field',''),fields.get('threshold',''))
     elif action in ('approve','reject'):sentience_v23.decide(c,user['id'],wid,fields.get('rec',''),action=='approve')
     else:raise ValueError('Invalid action')
     body=sentience_v23.render(c,user['id'],csrf,wid,'Action completed')
    return self.respond(200,shell('Sentience V23',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/autonomy':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Autonomy requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     action=fields.get('action','');wid=fields.get('workspace','');rid=fields.get('rule','')
     if action=='create':autonomy_v22.create(c,user['id'],wid,fields.get('app',''),fields.get('name',''),fields.get('field',''),fields.get('threshold',''))
     elif action=='activate':autonomy_v22.activate(c,user['id'],wid,rid)
     elif action=='disable':autonomy_v22.disable(c,user['id'],wid,rid)
     elif action=='run':autonomy_v22.evaluate(c,user['id'],wid,rid,fields.get('record',''),True)
     else:raise ValueError('Invalid action')
     body=autonomy_v22.render(c,user['id'],csrf,wid,'Action completed')
    return self.respond(200,shell('Autonomy V22',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/architect':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Architect requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     action=fields.get('action','');wid=fields.get('workspace','');pid=fields.get('proposal','')
     if action=='propose':architect_v21.propose(c,user['id'],wid,fields.get('prompt',''),fields.get('app',''))
     elif action=='approve':architect_v21.approve(c,user['id'],wid,pid)
     elif action=='reject':architect_v21.reject(c,user['id'],wid,pid)
     else:raise ValueError('Invalid action')
     body=architect_v21.render(c,user['id'],csrf,wid,'Action completed')
    return self.respond(200,shell('Architect V21',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/genesis-prime':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Genesis Prime requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     action=fields.get('action','');wid=fields.get('workspace','');aid=fields.get('app','')
     if action=='create':aid=genesis_prime_v20.create(c,user['id'],wid,fields.get('name',''),fields.get('template',''))
     elif action=='field':genesis_prime_v20.add_field(c,user['id'],wid,aid,fields.get('name',''),fields.get('type',''),fields.get('required','')=='yes')
     elif action=='publish':genesis_prime_v20.publish(c,user['id'],wid,aid)
     elif action=='record':
      row=genesis_prime_v20.app(c,user['id'],wid,aid,True)
      schema=json.loads(row[2]);data={f['name']:(fields.get('f'+str(i),'')=='on' if f['type']=='checkbox' else fields.get('f'+str(i),'')) for i,f in enumerate(schema)}
      new_record_id=genesis_prime_v20.add_record(c,user['id'],wid,aid,data)
      autonomy_v22.on_record_created(c,user['id'],wid,aid,new_record_id)
     elif action=='delete':genesis_prime_v20.delete_record(c,user['id'],wid,aid,fields.get('record',''))
     else:raise ValueError('Invalid action')
     body=genesis_prime_v20.render(c,user['id'],csrf,wid,aid,'Action completed')
    return self.respond(200,shell('Genesis Prime V20',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/empire':
   if os.getenv('VELXTRIA_ENABLE_BUSINESS_OS_V59','0')!='1' and (os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE):return self.fail(403,'Business workspace is not enabled.',user,csrf)
   try:
    with db() as c:
     action=fields.get('action','');wid=fields.get('workspace','');code=''
     if action=='create':wid=empire_v19.create(c,user['id'],fields.get('name',''))
     elif action=='accept':wid=empire_v19.accept(c,user['id'],fields.get('code',''))
     elif action=='invite':code=empire_v19.invite(c,user['id'],wid,fields.get('role',''))
     elif action=='add':empire_v19.add_record(c,user['id'],wid,fields.get('title',''),fields.get('detail',''))
     elif action=='delete':empire_v19.delete_record(c,user['id'],wid,fields.get('record',''))
     else:raise ValueError('Invalid workspace action')
     body=empire_v19.render(c,user['id'],csrf,wid,'Action completed',code)
    return self.respond(200,shell('Empire V19',body,user,csrf))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
  if p=='/site-studio' and os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE:
   try:
    with db() as c:
     if fields.get('action')=='create':site_studio.create(c,user['id'],fields.get('name',''),fields.get('description',''))
     elif fields.get('action')=='update':site_studio.update(c,user['id'],fields.get('company_id',''),fields.get('headline',''),fields.get('body',''),fields.get('theme',''))
     elif fields.get('action') in ('save_section','remove_section'):site_studio.section_action(c,user['id'],fields.get('company_id',''),fields.get('action'),fields)
     else:raise ValueError('Unknown action')
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/site-studio')
  if p=='/site-agent' and os.getenv('VELXTRIA_LOCAL_STUDIO','0')=='1' and not persistent.REMOTE:
   try:
    with db() as c:site_studio.agent_action(c,user['id'],fields.get('company_id',''),fields.get('action',''),fields)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/site-agent')
  if p=='/sovereign':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Sovereign requires local studio mode.',user,csrf)
   mid=fields.get('mission_id','')
   try:
    with db() as c:
     sovereign_v8.run(c,user['id'],mid,fields.get('tool',''))
     c.commit()
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/sovereign?id='+urllib.parse.quote(mid))
  if p=='/prometheus':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Prometheus requires local SQLite studio mode.',user,csrf)
   aid=fields.get('app_id','');action=fields.get('action','')
   try:
    with db() as c:
     if action=='design':prometheus_v14.design(c,user['id'],aid,fields.get('mode','rules'),fields.get('model','llama3.2'))
     elif action=='review':prometheus_v14.review(c,user['id'],aid)
     elif action=='restore':prometheus_v14.restore(c,user['id'],aid,fields.get('version_id',''))
     else:raise ValueError('Unknown Prometheus action')
     c.commit()
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/prometheus?app='+urllib.parse.quote(aid))
  if p=='/singularity-x':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'V13 requires local SQLite studio mode.',user,csrf)
   action=fields.get('action','');aid=fields.get('app_id','')
   try:
    with db() as c:
     if action=='create':aid=singularity_x_v13.create(c,user['id'],fields.get('title',''),fields.get('goal',''))
     elif action=='simulate':singularity_x_v13.simulate(c,user['id'],aid)
     elif action=='publish':singularity_x_v13.publish(c,user['id'],aid)
     elif action=='add_record':singularity_x_v13.add_record(c,user['id'],aid,fields)
     elif action=='delete_record':singularity_x_v13.delete_record(c,user['id'],aid,fields.get('record_id',''))
     else:raise ValueError('Unknown V13 action')
     c.commit()
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/singularity-x?app='+urllib.parse.quote(aid))
  if p=='/omnipotence':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omnipotence requires local SQLite studio mode.',user,csrf)
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='create':omnipotence_v12.create(c,user['id'],fields.get('title',''),fields.get('steps',''))
     elif action=='inspect':omnipotence_v12.inspect(c,user['id'],fields.get('flow_id',''))
     elif action=='approve':omnipotence_v12.approve(c,user['id'],fields.get('run_id',''))
     elif action=='reject':omnipotence_v12.reject(c,user['id'],fields.get('run_id',''))
     else:raise ValueError('Unknown action')
     c.commit()
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/omnipotence')
  if p=='/trinity':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Trinity requires local studio mode.',user,csrf)
   action=fields.get('action','');app_id=fields.get('app_id','');tab='genesis'
   try:
    with db() as c:
     if action=='create_app':app_id=trinity_v10.app_create(c,user['id'],fields.get('name',''),fields.get('description',''),fields.get('fields',''))
     elif action=='add_record':trinity_v10.record_create(c,user['id'],app_id,fields)
     elif action=='delete_record':trinity_v10.record_delete(c,user['id'],app_id,fields.get('record_id',''))
     elif action=='create_nexus':trinity_v10.nexus_create(c,user['id'],fields.get('title',''),fields.get('partner',''),fields.get('details',''));tab='nexus'
     elif action=='nexus_status':trinity_v10.nexus_status(c,user['id'],fields.get('proposal_id',''),fields.get('status',''));tab='nexus'
     else:raise ValueError('Unknown action')
     c.commit()
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/trinity?tab='+tab+('&app='+urllib.parse.quote(app_id) if app_id else ''))
  if p=='/constellation':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Constellation requires local studio mode.',user,csrf)
   mid=fields.get('mission_id','')
   try:
    with db() as c:constellation_v9.build(c,user['id'],mid)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/constellation?id='+urllib.parse.quote(mid))
  if p=='/omniscience':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Omniscience requires local studio mode.',user,csrf)
   mid=fields.get('mission_id','')
   try:
    with db() as c:
     if fields.get('action')=='create':omni_v7.create(c,user['id'],fields.get('plan_id',''))
     else:omni_v7.act(c,user['id'],fields.get('run_id',''),fields.get('task_id',''),fields.get('action',''),fields.get('note',''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/omniscience?id='+urllib.parse.quote(mid))
  if p=='/singularity':
   if os.getenv('VELXTRIA_LOCAL_STUDIO')!='1' or persistent.REMOTE:return self.fail(403,'Singularity requires local studio mode.',user,csrf)
   mid=fields.get('mission_id','')
   try:
    with db() as c:singularity_v6.generate(c,user['id'],mid,fields.get('goal',''),fields.get('model',''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/singularity?id='+urllib.parse.quote(mid))
  if p=='/mission-actions':
   mid=fields.get('mission_id','')
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='record_outcome': mission_v55.record(c,user['id'],mid,fields.get('proposal_id',''),fields.get('outcome',''),fields.get('evidence',''))
     elif action=='save_guidance': mission_v55.save_preferences(c,user['id'],fields.get('notes',''))
     elif action=='scan': mission_v53.scan(c,user['id'],mid)
     elif action=='edit_draft': mission_v53.edit_draft(c,user['id'],mid,fields.get('proposal_id',''),fields.get('draft_text',''))
     elif action=='restore': mission_v53.restore(c,user['id'],mid,fields.get('proposal_id',''))
     else: mission_v53.act(c,user['id'],mid,fields.get('proposal_id',''),action)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/mission-actions?id='+mid)
  if p=='/missions':
   try:
    with db() as c:
     if fields.get('action')=='create': mission_v52.create(c,user['id'],fields.get('title',''),fields.get('objective',''))
     else: mission_v52.action(c,user['id'],fields.get('mission_id',''),fields.get('action',''))
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/missions')
  if p=='/operator':
   try:
    with db() as c:
     action=fields.get('action','')
     if action=='scan': operator_v5.scan(c,user['id'])
     elif action in ('approve','reject'): operator_v5.decide(c,user['id'],fields.get('proposal_id',''),action)
     elif action=='execute': operator_v5.execute(c,user['id'],fields.get('proposal_id',''))
     else: raise ValueError('Unknown operator action')
   except ValueError as exc: return self.fail(400,str(exc),user,csrf)
   return self.redirect('/operator')
  if p=='/workspace':
   try:
    with db() as c:
      if fields.get('action','').startswith('invoice_'): business_v4.process(c,user['id'],fields)
      else: business_v3.process(c,user['id'],fields)
   except ValueError as exc:return self.fail(400,str(exc),user,csrf)
   return self.redirect('/workspace')
  if p=='/btcpay/checkout':
   if os.getenv('VELXTRIA_ENABLE_BTCPAY_TEST_CHECKOUT','0')!='1' or not btcpay_integration.configured():
    return self.fail(503,'Bitcoin test checkout is disabled.',user,csrf)
   with db() as c:
    ent,_,_=subscriptions.usage(c,user['id'])
    if ent['plan']=='pro':return self.redirect('/')
    recent=c.execute('SELECT checkout_url FROM btcpay_orders WHERE user_id=? AND status=? ORDER BY created_at DESC LIMIT 1',(user['id'],'pending')).fetchone()
    if recent:return self.redirect('/')
    order_id=btcpay_integration.create_order(c,user['id'])
   try:
    invoice_id,checkout_url=btcpay_integration.issue_invoice(order_id)
   except RuntimeError:
    with db() as c:c.execute("UPDATE btcpay_orders SET status='failed' WHERE order_id=?",(order_id,))
    return self.fail(503,'Unable to create test invoice. Check BTCPay API permissions.',user,csrf)
   with db() as c:
    c.execute("UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,status='pending' WHERE order_id=? AND status='creating'",(invoice_id,checkout_url,order_id))
   return self.redirect('/')
  if p=='/claim-demo':
   # Save an instant demo report into this account: the demo ZIP is moved
   # out of memory into persistent storage and recorded as a report, so it
   # counts against the same free allowance as an upload. The claim is
   # one-time — the in-memory entry is popped — and the free-limit check
   # runs first, so a paywalled user keeps their demo download.
   demo_token=fields.get('token','')
   if not peek_demo_zip(demo_token):
    return self.fail(400,'That demo report has expired or was already claimed — run the demo again to generate a new report.',user,csrf)
   with db() as c:
    ent,count,remaining=subscriptions.usage(c,user['id'])
    if remaining<=0:
     pending_mainnet=btcpay_mainnet.pending_order(c,user['id'])
     site_stats.record(c,'paywall_shown','used='+str(count))
     return self.respond(429,shell('Go PRO — VELXTRIA',paywall_html(user,csrf,count,pending_mainnet),user,csrf))
   entry=claim_demo_zip(demo_token)
   if not entry:
    return self.fail(400,'That demo report has expired or was already claimed — run the demo again to generate a new report.',user,csrf)
   zip_bytes,_exp,accepted,rejected,filename=entry
   ident=secrets.token_hex(16);digest=hashlib.sha256(zip_bytes).hexdigest()
   try:
    begin_report_write(user['id'],ident)
    store_verified_report(user['id'],ident,zip_bytes)
    with db() as c:
     c.execute('INSERT INTO reports(id,user_id,filename,created,status,accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',(ident,user['id'],Path(filename).name[:120],now(),'ready',accepted,rejected,digest))
     site_stats.record(c,'report_generated','accepted=%d rejected=%d'%(accepted,rejected))
     complete_report_write(c,ident,user['id'])
   except Exception:
    # A failed database insert or object-store write must not consume the
    # visitor's one-time demo. Restore it until its original TTL expires.
    restore_demo_zip(demo_token,entry)
    abandon_report_write(user['id'],ident)
    return self.fail(503,'Could not save this report right now. Your demo remains available for retry until its original expiry.',user,csrf)
   return self.redirect('/report?id='+ident,[('Set-Cookie',DEMO_COOKIE+'=; Path=/; Max-Age=0; SameSite=Lax')])
  if p=='/btcpay/mainnet/checkout':
   if not btcpay_mainnet.checkout_enabled():
    return self.fail(503,'Bitcoin checkout is not available.',user,csrf)
   with db() as c:
    recent=btcpay_mainnet.pending_order(c,user['id'])
    if recent:return self.redirect('/account')
    order_id=btcpay_mainnet.create_order(c,user['id'])
   try:
    invoice_id,checkout_url=btcpay_mainnet.issue_invoice(order_id)
   except RuntimeError:
    with db() as c:c.execute("UPDATE btcpay_orders SET status='failed' WHERE order_id=? AND network='mainnet'",(order_id,))
    return self.fail(503,'Unable to create Bitcoin invoice. Try again later.',user,csrf)
   with db() as c:
    c.execute("UPDATE btcpay_orders SET invoice_id=?,checkout_url=?,status='pending' WHERE order_id=? AND network='mainnet' AND status='creating'",(invoice_id,checkout_url,order_id))
    site_stats.record(c,'checkout_started',order_id)
   return self.redirect(checkout_url)
  if p=='/btcpay/mainnet/check-status':
   if not btcpay_mainnet.configured():
    return self.fail(503,'Bitcoin checkout is not available.',user,csrf)
   try:
    with db() as c:btcpay_mainnet.reconcile(c,user['id'])
   except RuntimeError:
    return self.fail(503,'Payment verification is temporarily unavailable. Try again shortly.',user,csrf)
   return self.redirect('/account')
  if p=='/redeem-license':
   key=fields.get('license_key','').strip()
   try: license_verification.verify(key,user['email'])
   except license_verification.LicenseError as exc: return self.fail(400,str(exc),user,csrf)
   except license_verification.LicenseUnavailable as exc: return self.fail(503,str(exc),user,csrf)
   fingerprint=hashlib.sha256(key.encode()).hexdigest()
   try:
    with db() as c:
     existing=c.execute('SELECT license_hash FROM paid_licenses WHERE user_id=?',(user['id'],)).fetchone()
     if existing:
      if hmac.compare_digest(existing[0],fingerprint):return self.redirect('/account')
      return self.fail(409,'This account already has a license. Contact support to change it.',user,csrf)
     c.execute('INSERT INTO paid_licenses (license_hash,license_key,user_id,redeemed_at) VALUES (?,?,?,?)',(fingerprint,key,user['id'],now()))
   except persistent_integrity_error():return self.fail(409,'This license is already assigned to an account.',user,csrf)
   return self.redirect('/account')
  if p=='/agents':
   if user['role']!='admin':return self.fail(403,'Founder access required.',user,csrf)
   action=fields.get('action','')
   try:
    with db() as c:
     if action=='pause':agent_core.set_paused(c,True)
     elif action=='resume':agent_core.set_paused(c,False)
     elif action=='create':agent_core.create(c,fields.get('title',''))
     elif action.startswith('advance:'):agent_core.tick(c,action.split(':',1)[1])
     elif action.startswith('approve:'):agent_core.decide(c,action.split(':',1)[1],True)
     elif action.startswith('reject:'):agent_core.decide(c,action.split(':',1)[1],False)
     else:raise ValueError('Unknown action')
   except ValueError as e:return self.fail(400,str(e),user,csrf)
   return self.redirect('/')
  if p!='/upload':return self.fail(404,'Page not found.',user,csrf)
  if not uploaded:return self.fail(400,'Choose a CSV file.',user,csrf)
  filename,data=uploaded
  try:validate_csv_upload(filename,data)
  except ValueError as e:return self.fail(400,str(e),user,csrf)
  with LOCK:
   with db() as c:
    ent,count,remaining=subscriptions.usage(c,user['id'])
    if remaining<=0:
     pending_mainnet=btcpay_mainnet.pending_order(c,user['id'])
     site_stats.record(c,'paywall_shown','used='+str(count))
     return self.respond(429,shell('Go PRO — VELXTRIA',paywall_html(user,csrf,count,pending_mainnet),user,csrf))
   ident=secrets.token_hex(16)
   try:
    report=run_report_engine(data)
    digest=hashlib.sha256(report['zip_bytes']).hexdigest()
    begin_report_write(user['id'],ident)
    store_verified_report(user['id'],ident,report['zip_bytes'])
    with db() as c:
     c.execute('INSERT INTO reports(id,user_id,filename,created,status,accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',(ident,user['id'],Path(filename).name[:120],now(),'ready',report['accepted'],report['rejected'],digest))
     site_stats.record(c,'report_generated','accepted=%d rejected=%d'%(report['accepted'],report['rejected']))
     complete_report_write(c,ident,user['id'])
     if fields.get('email_report')=='yes':
      c.execute('INSERT INTO deliveries(report_id,user_id,recipient,status,next_attempt) VALUES (?,?,?,?,?)',(ident,user['id'],user['email'],'queued' if DELIVERY_ENABLED else 'not_configured',now()))
      c.execute('UPDATE reports SET email_status=? WHERE id=?',('queued' if DELIVERY_ENABLED else 'not_configured',ident))
   except ValueError as e:
    # Invalid CSV is a client error. Storage cleanup must never mask the
    # original error or expose infrastructure details to the customer.
    abandon_report_write(user['id'],ident)
    return self.fail(422,'Could not process this CSV: '+str(e)[:180],user,csrf)
   except Exception:
    # A failed object upload or database transaction is a service failure,
    # not an invalid customer file. Keep provider errors and secrets private.
    abandon_report_write(user['id'],ident)
    return self.fail(503,'Your report could not be saved right now. Please try again later.',user,csrf)
  return self.redirect('/report?id='+ident)

def begin_report_write(user_id, report_id):
 """Durably record intent before writing to object storage."""
 with db() as c:
  c.execute("INSERT INTO report_write_journal(report_id,user_id,created,state) VALUES (?,?,?,?)",(report_id,user_id,now(),'pending'))

def complete_report_write(c, report_id, user_id):
 """Finalize the journal in the same transaction as the ready report row."""
 updated=c.execute("UPDATE report_write_journal SET state='committed' WHERE report_id=? AND user_id=? AND state='pending'",(report_id,user_id))
 if updated.rowcount != 1:
  raise RuntimeError('Report write is no longer pending; refusing to publish ready report')

def abandon_report_write(user_id, report_id):
 """Claim an uncommitted orphan before cleanup; never delete a ready report.

 An upload exception can occur after a DB commit. A conditional journal
 transition prevents a late exception from deleting a customer's valid ZIP.
 """
 try:
  with db() as c:
   claim=c.execute(
    "UPDATE report_write_journal SET state='recovering' "
    "WHERE report_id=? AND user_id=? AND state='pending' "
    "AND NOT EXISTS (SELECT 1 FROM reports WHERE id=?)",
    (report_id,user_id,report_id))
   if claim.rowcount != 1:
    return False
  try:
   persistent.remove(user_id,report_id)
   # A remote delete acknowledgment is insufficient: require authenticated
   # read-back proving the object is absent before marking it cleaned.
   if persistent.REMOTE:
    try:
     persistent.retrieve(user_id,report_id,REPORTS)
    except persistent.StorageObjectNotFound:
     pass
    else:
     raise RuntimeError('Report object still exists after deletion')
   else:
    raise RuntimeError('Local report deletion is not implemented')
  except Exception:
   with db() as c:
    c.execute("UPDATE report_write_journal SET state='pending' WHERE report_id=? AND user_id=? AND state='recovering'",(report_id,user_id))
   return False
  with db() as c:
   done=c.execute("UPDATE report_write_journal SET state='cleaned' WHERE report_id=? AND user_id=? AND state='recovering'",(report_id,user_id))
   return done.rowcount == 1
 except Exception:
  return False

def store_verified_report(user_id, report_id, payload):
 """Persist report ZIP and verify the exact stored bytes before publishing DB metadata.

 This prevents a ready report row from being created when remote storage
 acknowledges an upload but fails to return intact report content.
 """
 persistent.store(user_id,report_id,payload,REPORTS)
 actual=persistent.retrieve(user_id,report_id,REPORTS)
 expected_digest=hashlib.sha256(payload).hexdigest()
 if not hmac.compare_digest(hashlib.sha256(actual).hexdigest(),expected_digest):
  raise RuntimeError('Report storage integrity verification failed')
 return expected_digest

def delivery_worker():
 """Local background queue; SMTP only when explicitly configured and user opted in."""
 last_reminder_scan=0
 while not STOP.wait(5):
  if not DELIVERY_ENABLED:continue
  # A row marked 'sending' when the process was killed mid-send (a redeploy,
  # a spin-down) would otherwise sit stuck forever: neither queue picks
  # 'sending' rows. Return abandoned rows to the queue first.
  try:
   with db() as c:
    notifications.reclaim_stale(c)
    c.execute("UPDATE deliveries SET status=CASE WHEN attempts<3 THEN 'retry'"
              " ELSE 'failed' END, next_attempt=? WHERE status='sending'"
              " AND next_attempt<=?",
              (now(), now()-notifications.STALE_SENDING_SECONDS))
  except Exception as exc:
   print('Email reclaim error:', type(exc).__name__ + ':', str(exc)[:200])
  try:
   with db() as c:
    row=c.execute("SELECT report_id,user_id,recipient,attempts FROM deliveries WHERE status IN ('queued','retry') AND next_attempt<=? AND attempts<3 ORDER BY next_attempt LIMIT 1",(now(),)).fetchone()
    if row:
     report_id,user_id,recipient,attempts=row
     c.execute("UPDATE deliveries SET status='sending', attempts=attempts+1 WHERE report_id=?",(report_id,))
   if row:
    report_bytes=persistent.retrieve(user_id,report_id,REPORTS)
    with db() as c:
     stored=c.execute("SELECT digest FROM reports WHERE id=? AND user_id=? AND status='ready'",(report_id,user_id)).fetchone()
    if not stored or not hmac.compare_digest(hashlib.sha256(report_bytes).hexdigest(),stored[0]):
     raise RuntimeError('Report integrity verification failed; email attachment withheld')
    notifications.send_mail(recipient, 'Your VELXTRIA report is ready',
     'Your requested VELXTRIA report is attached. This is a local demonstration. Do not send sensitive business information.',
     attachment=('VELXTRIA_Report.zip', report_bytes, 'application/zip'))
    with db() as c:
     c.execute("UPDATE deliveries SET status='sent',last_error='' WHERE report_id=?",(report_id,))
     c.execute("UPDATE reports SET email_status='sent' WHERE id=?",(report_id,))
  except Exception as exc:
   if 'report_id' in locals():
    retry=(attempts+1)<3
    with db() as c:
     c.execute('UPDATE deliveries SET status=?,last_error=?,next_attempt=? WHERE report_id=?',('retry' if retry else 'failed',str(exc)[:160],now()+min(3600,60*2**attempts),report_id))
     c.execute('UPDATE reports SET email_status=? WHERE id=?',('retry' if retry else 'failed',report_id))
   print('Email delivery error:', type(exc).__name__ + ':', str(exc)[:200])
  # Notifications (PRO confirmations, password resets, renewal reminders)
  # are best-effort: a failure here must never break report delivery.
  try:
   with db() as c:
    if now()-last_reminder_scan>=3600:
     notifications.scan_renewal_reminders(c)
     last_reminder_scan=now()
    while notifications.process_one(c):pass
  except Exception as exc:
   print('Email notification error:', type(exc).__name__ + ':', str(exc)[:200])

def month_start():
 d=datetime.now(timezone.utc)
 return int(datetime(d.year,d.month,1,tzinfo=timezone.utc).timestamp())

if __name__=='__main__':
 # Runtime guard: Render build checks alone cannot guarantee that the running
 # service has durable storage. Never serve paid accounts with missing config.
 if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview':
  if not persistent.REQUIRE or not persistent.REMOTE:
   raise SystemExit('Render requires persistent PostgreSQL; configure VELXTRIA_REQUIRE_PERSISTENCE=1 and VELXTRIA_DATABASE_URL')
  if not persistent.URL or not persistent.KEY:
   raise SystemExit('Render requires private report storage; configure VELXTRIA_SUPABASE_URL and VELXTRIA_SUPABASE_SERVICE_KEY')
 db().close()
 mode=os.getenv('VELXTRIA_DEPLOYMENT_MODE','local')
 if mode == 'render-preview' and not os.getenv('VELXTRIA_PREVIEW_PASSWORD'):
  raise SystemExit('Set VELXTRIA_PREVIEW_PASSWORD before starting Render preview')
 host='0.0.0.0' if mode == 'render-preview' else '127.0.0.1'
 port=int(os.getenv('PORT','8878'))
 print(f'VELXTRIA V4 {mode} portal on {host}:{port}; database={"postgresql" if persistent.REMOTE else "sqlite-local"}; storage={"private-supabase" if persistent.REMOTE else "local"}')
 if DELIVERY_ENABLED:
  Thread(target=delivery_worker,daemon=True).start()
  print('Email delivery queue enabled (' + ('Brevo' if notifications.brevo_configured() else 'SendGrid' if notifications.sendgrid_configured() else 'SMTP') + ')')
 else:print('Email not configured: reports available for download only')
 print('PRIVATE TEST ONLY — not production ready; no real customer data or payments.')
 ThreadingHTTPServer((host,port),Handler).serve_forever()
