"""VELXTRIA V4 portal. Render preview requires VELXTRIA_PREVIEW_PASSWORD."""
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
 agent_core.setup(c)
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
 nav=('<a href="/">Dashboard</a> <a href="/account">Account</a> <form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button class="link">Sign out</button></form>') if user else '<a href="/login">Sign in</a> <a href="/register">Create demo account</a>'
 return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · VELXTRIA</title><link rel="stylesheet" href="/style.css"></head><body><header><div class="brand">✦ VELXTRIA <span>REPORT AUTOMATION</span></div><nav>{nav}</nav></header><main>{body}</main><footer>V4 private test · Payhip webhook staging only · Never upload sensitive data</footer></body></html>"""


def landing_page():
 return """<div class="landing">
 <section class="landing-hero"><div class="landing-glow"></div><div class="landing-content"><div class="landing-kicker">✦ VELXTRIA / REPORT AUTOMATION</div><h1>Turn messy sales data into <em>clear decisions.</em></h1><p class="landing-lead">Upload a supported sales CSV. Get cleaned records, flagged rows, and organized summaries in one downloadable report package.</p><div class="landing-actions"><a class="landing-primary" href="/register">Explore the demo <span aria-hidden="true">↗</span></a><a class="landing-secondary" href="/login">Already have an account? Sign in</a></div><div class="landing-note">Private preview · Sample or non-sensitive data only · Paid access is not yet enabled</div></div><div class="landing-preview" aria-label="Example report package"><div class="preview-top"><span>REPORT OVERVIEW</span><span class="preview-dot">● PREVIEW</span></div><div class="preview-title">Your sales, organized.</div><div class="preview-metrics"><div><strong>01</strong><small>Cleaned CSV</small></div><div><strong>02</strong><small>Flagged rows</small></div><div><strong>03</strong><small>Summary files</small></div></div><div class="preview-lines"><span></span><span></span><span></span><span></span></div><div class="preview-bottom">EXAMPLE OUTPUT · NOT LIVE CUSTOMER DATA</div></div></section>
 <section class="landing-section"><div class="landing-section-heading"><span>THE WORKFLOW</span><h2>Less spreadsheet cleanup.<br>More time for the work that matters.</h2></div><div class="landing-grid"><article><span class="step-number">01 / UPLOAD</span><h3>Bring your sales CSV</h3><p>Start with a supported sales export using the required column headers.</p></article><article><span class="step-number">02 / PROCESS</span><h3>Clean and check</h3><p>VELXTRIA separates accepted records from rows that need attention.</p></article><article><span class="step-number">03 / DOWNLOAD</span><h3>Get organized outputs</h3><p>Download cleaned data, rejected rows, and monthly and product summaries together.</p></article></div></section>
 <section class="landing-cta"><div><span>READY TO EXPLORE?</span><h2>See what your sales data can become.</h2><p>Try the private demo with sample or non-sensitive data. No purchase required.</p></div><a class="landing-primary" href="/register">Create demo account ↗</a></section>
 </div>"""

LANDING_CSS = r"""
.landing{color:#f7f6ff;font-family:inherit}.landing a{text-decoration:none}.landing-hero{position:relative;isolation:isolate;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(280px,.85fr);align-items:center;gap:clamp(2rem,5vw,5rem);padding:clamp(4rem,8vw,8rem) clamp(1rem,4vw,4rem);background:radial-gradient(ellipse at 70% 15%,#302050 0%,transparent 48%),linear-gradient(125deg,#111324,#171126 65%,#10101d);border:1px solid #39324d;border-radius:24px;margin:1.5rem 0 4rem}.landing-glow{position:absolute;z-index:-1;right:12%;top:12%;height:340px;width:340px;background:#794aff;filter:blur(125px);opacity:.18}.landing-kicker,.landing-section-heading>span,.landing-cta span{font-size:.75rem;font-weight:800;letter-spacing:.18em;color:#bca6ff}.landing h1{font-size:clamp(2.8rem,5.5vw,5.8rem);line-height:1.04;letter-spacing:-.055em;margin:1.4rem 0 1.5rem;max-width:800px}.landing h1 em{font-style:normal;background:linear-gradient(95deg,#bca6ff,#e6baff);-webkit-background-clip:text;background-clip:text;color:transparent}.landing-lead{font-size:1.1rem;line-height:1.75;color:#c8c3d9;max-width:590px}.landing-actions{display:flex;flex-wrap:wrap;align-items:center;gap:1.25rem;margin-top:2rem}.landing-primary{display:inline-flex;align-items:center;justify-content:center;gap:1rem;padding:1rem 1.45rem;border-radius:12px;background:#b99aff;color:#171024!important;font-weight:800;box-shadow:0 8px 32px #6d42c533}.landing-primary:hover{background:#d2beff}.landing-secondary{color:#e3dbf8!important;font-weight:600}.landing-note{font-size:.78rem;line-height:1.6;color:#a8a0bb;margin-top:2rem}.landing-preview{border:1px solid #66527d;border-radius:18px;background:linear-gradient(145deg,#252039,#151523);padding:clamp(1.25rem,2.5vw,2.2rem);box-shadow:0 30px 80px #0006;transform:rotate(1deg)}.preview-top,.preview-bottom{font-size:.65rem;letter-spacing:.13em;color:#b8a8d2;display:flex;justify-content:space-between;gap:1rem}.preview-dot{color:#bca6ff}.preview-title{font-size:clamp(1.4rem,2.5vw,2rem);font-weight:800;letter-spacing:-.03em;margin:2.5rem 0 1.5rem}.preview-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}.preview-metrics>div{border:1px solid #51445f;background:#30283d;border-radius:12px;padding:1rem .6rem}.preview-metrics strong{display:block;font-size:1.6rem;color:#e3d7ff}.preview-metrics small{display:block;font-size:.7rem;color:#bfb5cd;margin-top:.4rem}.preview-lines{display:grid;gap:.75rem;margin:2rem 0}.preview-lines span{height:12px;border-radius:6px;background:linear-gradient(90deg,#54426b,#2b2639)}.preview-lines span:nth-child(2){width:76%}.preview-lines span:nth-child(3){width:91%}.preview-lines span:nth-child(4){width:58%}.landing-section{margin:0 0 4rem}.landing-section-heading h2{font-size:clamp(2rem,3.5vw,3.4rem);line-height:1.15;letter-spacing:-.04em;margin:1rem 0 2rem}.landing-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.landing-grid article{background:#1b1d2d;border:1px solid #38354d;border-radius:18px;padding:2rem}.step-number{font-size:.75rem;letter-spacing:.12em;color:#c3a9ff;font-weight:800}.landing-grid h3{font-size:1.3rem;margin:2rem 0 .8rem}.landing-grid p,.landing-cta p{color:#bbb5cd;line-height:1.7}.landing-cta{background:linear-gradient(105deg,#241c3d,#181728);border:1px solid #51436a;border-radius:20px;padding:clamp(1.5rem,4vw,3.5rem);display:flex;align-items:center;justify-content:space-between;gap:2rem;margin-bottom:3rem}.landing-cta h2{font-size:clamp(1.7rem,3vw,2.6rem);letter-spacing:-.035em;margin:.7rem 0}.landing-cta .landing-primary{flex-shrink:0}@media(max-width:850px){.landing-hero{grid-template-columns:1fr}.landing-preview{max-width:560px;transform:none}.landing-grid{grid-template-columns:1fr}.landing-cta{align-items:flex-start;flex-direction:column}}@media(max-width:480px){.landing-hero{padding:2rem 1.2rem}.landing-preview{padding:1rem}.preview-metrics strong{font-size:1.3rem}.landing-actions{align-items:flex-start;flex-direction:column}}
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

class Handler(BaseHTTPRequestHandler):
 def preview_guard(self):
  if os.getenv('VELXTRIA_DEPLOYMENT_MODE','local') != 'render-preview':
   return False
  path = urllib.parse.urlsplit(self.path).path
  if path == '/healthz' and self.command == 'GET':
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
  except (ValueError,UnicodeError,Exception):
