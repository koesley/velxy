"""VELXTRIA customer portal with public landing page and private preview guard."""
import base64, csv, hashlib, hmac, html, io, json, os, secrets, shutil, smtplib, sqlite3, subprocess, sys, tempfile, time, urllib.parse, zipfile
from datetime import datetime, timezone
from email.message import EmailMessage
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
import btcpay_integration
import btcpay_mainnet
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

ROOT=Path(__file__).resolve().parent
DELIVERY_ENABLED=os.getenv("VELXTRIA_SMTP_HOST","") != ""
STOP=Event()
DATA_ROOT=Path(os.getenv('VELXTRIA_DATA_DIR',str(ROOT))).resolve()
DATA_ROOT.mkdir(parents=True,exist_ok=True)
DB=DATA_ROOT/'portal.sqlite3'; REPORTS=DATA_ROOT/'customer_reports'; REPORTS.mkdir(exist_ok=True)
MAX_BYTES=5*1024*1024; MAX_MONTHLY=50; LOCK=Lock()
REQUIRED=['Order ID','Order Date','Customer','Product','Quantity','Unit Price','Status','Region']

def now(): return int(time.time())
def db():
 c=persistent.connect(DB)
 if persistent.REMOTE:
  c.execute("""CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer', access TEXT NOT NULL DEFAULT 'demo', created INTEGER NOT NULL)""")
 else:
  c.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer', access TEXT NOT NULL DEFAULT 'demo', created INTEGER NOT NULL)""")
 c.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires INTEGER NOT NULL, csrf TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))')
 c.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, filename TEXT NOT NULL, created INTEGER NOT NULL, status TEXT NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, digest TEXT NOT NULL, email_status TEXT NOT NULL DEFAULT 'not_sent', FOREIGN KEY(user_id) REFERENCES users(id))")
 c.execute("CREATE TABLE IF NOT EXISTS deliveries (report_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, recipient TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '', next_attempt INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(report_id) REFERENCES reports(id))")
 c.execute('CREATE TABLE IF NOT EXISTS paid_licenses (license_hash TEXT PRIMARY KEY, license_key TEXT NOT NULL, user_id INTEGER NOT NULL UNIQUE, redeemed_at INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))')
 payhip_integration.setup(c)
 subscriptions.setup(c)
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
 c.commit();return c

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
 nav=('<a href="/sovereign-unified-v56">✦ Unified Command</a> <a href="/sovereign-genesis-v56">✦ Project Genesis</a> <a href="/sovereign-command-v56">✦ Ask VELXTRIA</a> <a href="/sovereign-guardian-v56">✦ Guardian</a> <a href="/sovereign-connectors-v56">✦ Connectors</a> <a href="/sovereign-executive-v56">✦ Executive Council 2.0</a> <a href="/sovereign-future-v56">✦ Future Simulator</a> <a href="/sovereign-memory-v56">✦ Memory</a> <a href="/sovereign-execution-v56">✦ Execution</a> <a href="/sovereign-strategies-v56">✦ Strategies</a> <a href="/sovereign-opportunities-v56">✦ Opportunities</a> <a href="/sovereign-sync-v56">✦ Twin Sync</a> <a href="/sovereign-twin-v56">✦ Digital Twin</a> <a href="/sovereign-council-v56">✦ Sovereign Council</a> <a href="/sovereign-v56">✦ Sovereign V56</a> <a href="/omega-v55">✦ Omega V55</a> <a href="/aegis-v54">✦ Aegis V54</a> <a href="/sentinel-v53">✦ Sentinel V53</a> <a href="/titan-intelligence">✦ Titan V52</a> <a href="/ascendancy-v51">✦ Ascendancy V51</a> <a href="/singularity-v50">✦ Singularity V50</a> <a href="/nexus-reforged">Command Center</a> <a href="/infinity-engine">Intelligence</a> <a href="/autonomous-core">Experiments</a> <a href="/synapse">Synapse</a> <a href="/omniscience">Omniscience V49</a> <a href="/quantum-command">Quantum V48</a> <a href="/hyperion">Hyperion V47</a> <a href="/neural-network">Neural V45</a> <a href="/evolution-engine">Evolution V46</a> <a href="/">Reports</a> <a href="/workspace">Business</a> <a href="/genesis-prime">Apps</a> <a href="/oracle">Oracle</a> <a href="/atlas">Onboarding</a> <a href="/catalyst">Release checks</a> <a href="/account">Account</a> <form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button class="link">Sign out</button></form>') if user else '<a href="/login">Sign in</a> <a href="/register">Create demo account</a>'
 return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · VELXTRIA</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/site-studio.css"></head><body class="{'workspace-page' if title == 'Business Workspace' else ''}"><header><div class="brand">✦ VELXTRIA <span>BUSINESS PLATFORM</span></div><nav class="velx-nav"><a class="velx-primary" href="/business-os-v59">Business OS</a><a class="velx-primary" href="/revenue-priority">Revenue Priority</a><a class="velx-primary" href="/revenue-priority/live">Live Priorities</a><a class="velx-primary" href="/revenue-followups">Follow-ups</a><a class="velx-primary" href="/revenue-conversion">Conversion</a><a class="velx-primary" href="/revenue-command">Revenue Command</a><a class="velx-primary" href="/revenue-brief">Daily Brief</a><a class="velx-primary" href="/revenue-goals">Goals</a><a class="velx-primary" href="/revenue-gap">Gap Plan</a><a class="velx-primary" href="/revenue-execution">Execution</a><a class="velx-primary" href="/revenue-operations">Operations</a><a class="velx-primary" href="/revenue-recovery">Recovery</a><a class="velx-primary" href="/operations-recovery">Recovery</a><a class="velx-primary" href="/operations-performance">Performance</a><a class="velx-primary" href="/customer-outcomes">Outcomes</a><a class="velx-primary" href="/revenue-sources">Sources</a><a class="velx-primary" href="/revenue-attribution">Sources</a><a class="velx-primary" href="/acquisition-intelligence">Acquisition</a><a class="velx-primary" href="/marketing-budget">Budget Studio</a><a class="velx-primary" href="/campaign-experiments">Campaign Lab</a><a class="velx-primary" href="/experiment-decisions">Decisions</a><a class="velx-primary" href="/campaign-optimization">Optimize</a><a class="velx-primary" href="/optimization-impact">Impact</a><a class="velx-primary" href="/growth-intelligence">Growth Center</a><a class="velx-primary" href="/growth-strategy">Growth Strategy</a><a class="velx-primary" href="/business-agents-v59">Agents</a><a class="velx-primary" href="/sovereign-omniverse-v57">Omniverse</a><a class="velx-primary" href="/sovereign-business-graph-v57">Business Graph</a><a class="velx-primary" href="/sovereign-opportunities-v57">Opportunity Radar</a><a class="velx-primary" href="/sovereign-council-v57">Council</a><a class="velx-primary" href="/sovereign-lab-v57">Decision Lab</a><a class="velx-primary" href="/sovereign-unified-v56">Command</a><a class="velx-primary" href="/sovereign-workflows-v56">Workflow Studio</a><a class="velx-primary" href="/sovereign-nexus-v56">Nexus</a><a class="velx-primary" href="/sovereign-workflow-runs-v56">Operations</a><a class="velx-primary" href="/">Reports</a><a class="velx-primary" href="/sovereign-genesis-v56">Genesis</a><a class="velx-primary" href="/sovereign-command-v56">Ask VELXTRIA</a><a class="velx-primary" href="/sovereign-guardian-v56">Guardian</a><a class="velx-primary" href="/sovereign-executive-v56">Intelligence</a><a class="velx-primary" href="/sovereign-strategies-v56">Strategies</a><a class="velx-primary" href="/sovereign-execution-v56">Execution</a><details class="velx-more"><summary>Explore platform ▾</summary><div class="velx-more-panel">{nav}</div></details></nav></header><main>{body}</main><footer>VELXTRIA private preview · {btc_note} · Never upload sensitive data</footer></body></html>"""