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
 return """<div class="v8">
 <div class="v8-orbit v8-orbit-a"></div><div class="v8-orbit v8-orbit-b"></div>
 <section class="v8-hero">
  <div class="v8-copy">
   <div class="v8-status"><span class="v8-live"></span> VELXTRIA / INTELLIGENT REPORTING <span class="v8-status-right">PRIVATE PREVIEW</span></div>
   <h1>DATA IS CHAOS.<br><span>MAKE IT</span><br><i>CLARITY.</i></h1>
   <p>From raw sales exports to clean, organized intelligence. Upload a supported CSV, isolate problem rows, and download your reporting package in minutes.</p>
   <div class="v8-actions"><a class="v8-primary" href="/register">ENTER THE DEMO <span>↗</span></a><a class="v8-ghost" href="#v8-process">EXPLORE THE SYSTEM <span>↓</span></a></div>
   <div class="v8-disclaimer">DEMO ENVIRONMENT <span>•</span> SAMPLE OR NON-SENSITIVE DATA ONLY <span>•</span> PAID ACCESS NOT YET VERIFIED</div>
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
 <section class="v8-bottom"><div><span>02 / YOUR NEXT MOVE</span><h2>LESS MESS.<br><em>MORE MOMENTUM.</em></h2><p>Try the private reporting demo with sample or non-sensitive data. No purchase required.</p></div><a class="v8-primary" href="/register">LAUNCH DEMO <span>↗</span></a></section>
 <div class="v8-footnote">✦ VELXTRIA <span>BUILT FOR CLEARER WORKFLOWS · PREVIEW EDITION</span></div>
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
.v8 h1 i,.v8-process h2 em,.v8-bottom h2 em{font-style:normal;background:linear-gradient(110deg,#a888ff,#d0a7ff 45%,#ffb7f1);color:transparent;background-clip:text;-webkit-background-clip:text}
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
.v8-process h2,.v8-bottom h2{font-size:clamp(2.5rem,5vw,5.7rem);line-height:1.06;letter-spacing:-.065em;margin:2.4rem 0 3.5rem;font-weight:900}
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
  except (ValueError, UnicodeError):
   scheme = ''
   username = password = ''
  if scheme.lower() != 'basic':
   username = password = ''
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
  self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'")
  for k,v in headers:self.send_header(k,v)
  self.end_headers();self.wfile.write(b)
 def fail(self,status,message,user=None,csrf=''):
  self.respond(status,shell('Notice','<section class="panel"><h2>'+escape(message)+'</h2><p><a href="/">Return to dashboard</a></p></section>',user,csrf))
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
  if p=='/style.css':return self.respond(200,(ROOT/'style.css').read_bytes()+LANDING_CSS.encode('utf-8'),'text/css; charset=utf-8')
  user,csrf,_=self.identity()
  if p=='/login':return self.respond(200,shell('Sign in','<section class="panel narrow"><h1>Welcome back</h1><form method="post" action="/login"><label>Email<input name="email" type="email" required></label><label>Password<input name="password" type="password" required></label><button>Sign in</button></form></section>'))
  if p=='/register':return self.respond(200,shell('Register','<section class="panel narrow"><h1>Create a local demo account</h1><p>This account does not verify Payhip payments.</p><form method="post" action="/register"><label>Email<input name="email" type="email" required></label><label>Password (12+ characters)<input name="password" type="password" minlength="12" required></label><button>Create account</button></form></section>'))
  if p=='/' and not user:return self.respond(200,shell('Sales reporting made simple',landing_page()))
  if not user:return self.redirect('/login')
  if p=='/':
   with db() as c:
    reports=c.execute('SELECT id,filename,created,status,accepted,rejected,email_status FROM reports WHERE user_id=? ORDER BY created DESC LIMIT 30',(user['id'],)).fetchall()
    count=c.execute('SELECT count(*) FROM reports WHERE user_id=? AND created>=?',(user['id'],month_start())).fetchone()[0]
   rows=''.join('<tr><td>'+escape(r[1])+'</td><td>'+escape(datetime.fromtimestamp(r[2],timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+'</td><td>'+escape(r[3])+'</td><td>'+str(r[4])+' / '+str(r[5])+'</td><td><a href="/download?id='+escape(r[0])+'">Download ZIP</a></td><td>'+escape(r[6])+'</td></tr>' for r in reports)
   access='Local demo access' if user['access']=='demo' else 'Founder-granted access (not Payhip-verified)'
   body=f"""<section class="hero"><p class="eyebrow">CUSTOMER PORTAL</p><h1>Your reports, handled.</h1><p>Upload a supported sales CSV. VELXTRIA cleans records, flags errors, and creates downloadable reports automatically.</p></section><div class="stats"><div><b>{count}</b><small>Reports this month</small></div><div><b>{MAX_MONTHLY-count}</b><small>Remaining demo allowance</small></div><div><b>{escape(access)}</b><small>Access status</small></div></div><section class="panel"><h2>Process a CSV</h2><p>5 MB maximum · 50 reports/month · Supported sales-export schema only</p><form method="post" action="/upload" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{escape(csrf)}"><label>Choose CSV<input type="file" name="file" accept=".csv,text/csv" required></label><label><input type="checkbox" name="email_report" value="yes"> Email the completed report to my account address (requires configured SMTP)</label><button>Generate report</button></form><details><summary>Required column headers</summary><code>{escape(', '.join(REQUIRED))}</code></details></section><section class="panel"><h2>Your reports</h2><div class="scroll"><table><thead><tr><th>File</th><th>Processed</th><th>Status</th><th>Accepted / flagged</th><th>Result</th><th>Email</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No reports yet.</td></tr>'}</tbody></table></div></section>"""
   if user['role']=='admin':
    body+='<section class="panel"><a href="/agents">Open Founder Agent Control</a></section>'
    with db() as c:
     users=c.execute('SELECT email,role,access FROM users ORDER BY created DESC').fetchall();errors=c.execute("SELECT count(*) FROM reports WHERE status != 'ready'").fetchone()[0]
    body+='<section class="panel"><h2>Founder overview</h2><p>Accounts: '+str(len(users))+' · Failed reports: '+str(errors)+'</p><p>Payhip verification: <strong>STAGING ONLY — manual review; no automatic access</strong>. SMTP: <strong>'+('configured' if DELIVERY_ENABLED else 'not configured')+'</strong>. Do not use this prototype to enforce paid access.</p></section>'
   return self.respond(200,shell('Dashboard',body,user,csrf))
  if p=='/agents':
   if user['role']!='admin':return self.fail(403,'Founder access required.',user,csrf)
   return self.respond(200,shell('Founder Agent Control',render_agents(csrf),user,csrf))
  if p=='/account':
   with db() as c: licensed=c.execute('SELECT license_key FROM paid_licenses WHERE user_id=?',(user['id'],)).fetchone()
   state='No redeemed license'
   if licensed:
    try:
     license_verification.verify(licensed[0],user['email'])
     state='Payhip license verified and active'
    except license_verification.LicenseError: state='License invalid, disabled or refunded — paid access inactive'
    except license_verification.LicenseUnavailable: state='License verification unavailable — paid access temporarily inactive'
   body='<section class="panel"><h1>Account</h1><p>'+escape(user['email'])+'</p><p>Payhip status: '+escape(state)+'</p><p>Existing demo reporting remains available. License redemption does not change your demo quota.</p><form method="post" action="/redeem-license"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><label>Payhip license key<input name="license_key" maxlength="120" autocomplete="off" required></label><button>Verify and redeem license</button></form></section>' 
   return self.respond(200,shell('Account',body,user,csrf))
  if p=='/download':
   ident=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
   with db() as c:row=c.execute("SELECT id FROM reports WHERE id=? AND user_id=? AND status='ready'",(ident,user['id'])).fetchone()
   if not row:return self.fail(404,'Report not found.',user,csrf)
   try: report_bytes=persistent.retrieve(user['id'],ident,REPORTS)
   except (OSError,RuntimeError):return self.fail(503,'Report file temporarily unavailable.',user,csrf)
   return self.respond(200,report_bytes,'application/zip',[('Content-Disposition','attachment; filename="VELXTRIA_Report.zip"')])
  return self.fail(404,'Page not found.',user,csrf)
 def redirect(self,path,headers=()):return self.respond(303,b'','text/plain',[('Location',path),*headers])
 def post_data(self):
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ValueError('Invalid request size')
  if n<=0 or n>MAX_BYTES+65536:raise ValueError('Upload too large (maximum 5 MB)')
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
    elif name=='email_report':fields['email_report']=part.get_content().strip()
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
    with db() as c:status,message=payhip_integration.accept_event(c,raw)
    return self.respond(status,message,'text/plain')
   except (ValueError,UnicodeError):return self.respond(400,'Invalid webhook','text/plain')
  try:fields,uploaded=self.post_data()
  except Exception as e:return self.fail(400,str(e))
  if p=='/register':
   email=fields.get('email','').strip().lower();password=fields.get('password','')
   if not valid_email(email) or len(password)<12 or len(password)>256:return self.fail(400,'Use a valid email and password of 12–256 characters.')
   salt=secrets.token_hex(16)
   try:
    with db() as c:c.execute('INSERT INTO users(email,salt,pw_hash,role,access,created) VALUES (?,?,?,?,?,?)',(email,salt,pw_hash(password,salt),'customer','demo',now()))
   except (sqlite3.IntegrityError, persistent_integrity_error()):return self.fail(409,'Account already exists.')
   return self.redirect('/login')
  if p=='/login':
   email=fields.get('email','').strip().lower();password=fields.get('password','')
   with db() as c:row=c.execute('SELECT id,salt,pw_hash FROM users WHERE email=?',(email,)).fetchone()
   if not row or not hmac.compare_digest(pw_hash(password,row[1]),row[2]):return self.fail(401,'Invalid email or password.')
   token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
   with db() as c:c.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row[0],now()+86400,csrf))
   secure='; Secure' if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview' else ''
   return self.redirect('/',[('Set-Cookie','velxtria_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+secure)])
  ident=self.require()
  if not ident:return
  user,csrf,token=ident
  if not hmac.compare_digest(fields.get('csrf',''),csrf):return self.fail(403,'Session verification failed.',user,csrf)
  if p=='/logout':
   with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
   secure='; Secure' if os.getenv('VELXTRIA_DEPLOYMENT_MODE') == 'render-preview' else ''
   return self.redirect('/login',[('Set-Cookie','velxtria_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+secure)])
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
  if not filename.lower().endswith('.csv') or not data or len(data)>MAX_BYTES:return self.fail(400,'Upload one nonempty CSV file up to 5 MB.',user,csrf)
  if b'\x00' in data:return self.fail(400,'Invalid CSV file.',user,csrf)
  try:
   decoded=data.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(decoded))
   if reader.fieldnames!=REQUIRED:raise ValueError('Incorrect columns. Expand the required headers on the dashboard.')
   if len(decoded.splitlines())>20001:raise ValueError('Limit is 20,000 lines per upload.')
  except (UnicodeError,csv.Error,ValueError) as e:return self.fail(400,str(e),user,csrf)
  with LOCK:
   with db() as c:
    count=c.execute('SELECT count(*) FROM reports WHERE user_id=? AND created>=?',(user['id'],month_start())).fetchone()[0]
    if count>=MAX_MONTHLY:return self.fail(429,'Monthly demo allowance reached.',user,csrf)
   ident=secrets.token_hex(16);digest=hashlib.sha256(data).hexdigest()
   try:
    with tempfile.TemporaryDirectory() as t:
     work=Path(t);shutil.copy2(ROOT/'automate.py',work/'automate.py');(work/'messy_sales_input.csv').write_bytes(data)
     result=subprocess.run([sys.executable,'-I',str(work/'automate.py')],cwd=work,timeout=30,capture_output=True,text=True)
     if result.returncode:raise ValueError('Processing failed: '+(result.stderr or result.stdout)[-300:])
     out=work/'output';files=['cleaned_sales.csv','rejected_rows.csv','monthly_summary.csv','product_summary.csv','run_summary.txt']
     if not all((out/f).exists() for f in files):raise ValueError('Missing report output')
     def rowcount(path):
      with path.open(encoding='utf-8-sig',newline='') as f:return max(0,sum(1 for _ in csv.reader(f))-1)
     accepted=rowcount(out/'cleaned_sales.csv');rejected=rowcount(out/'rejected_rows.csv')
     archive=io.BytesIO()
     with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
      for f in files:z.write(out/f,arcname=f)
     persistent.store(user['id'],ident,archive.getvalue(),REPORTS)
    with db() as c:
     c.execute('INSERT INTO reports(id,user_id,filename,created,status,accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',(ident,user['id'],Path(filename).name[:120],now(),'ready',accepted,rejected,digest))
     if fields.get('email_report')=='yes':
      c.execute('INSERT INTO deliveries(report_id,user_id,recipient,status,next_attempt) VALUES (?,?,?,?,?)',(ident,user['id'],user['email'],'queued' if DELIVERY_ENABLED else 'not_configured',now()))
      c.execute('UPDATE reports SET email_status=? WHERE id=?',('queued' if DELIVERY_ENABLED else 'not_configured',ident))
   except Exception as e:
    if 'ident' in locals(): persistent.remove(user['id'],ident)
    return self.fail(422,'Could not process this file: '+str(e)[:240],user,csrf)
  return self.redirect('/?done=1')

def delivery_worker():
 """Local background queue; SMTP only when explicitly configured and user opted in."""
 while not STOP.wait(5):
  if not DELIVERY_ENABLED:continue
  try:
   with db() as c:
    row=c.execute("SELECT report_id,user_id,recipient,attempts FROM deliveries WHERE status IN ('queued','retry') AND next_attempt<=? AND attempts<3 ORDER BY next_attempt LIMIT 1",(now(),)).fetchone()
    if not row:continue
    report_id,user_id,recipient,attempts=row
    c.execute("UPDATE deliveries SET status='sending', attempts=attempts+1 WHERE report_id=?",(report_id,))
   report_bytes=persistent.retrieve(user_id,report_id,REPORTS)
   msg=EmailMessage();msg['Subject']='Your VELXTRIA report is ready';msg['From']=os.environ['VELXTRIA_SMTP_FROM'];msg['To']=recipient
   msg.set_content('Your requested VELXTRIA report is attached. This is a local demonstration. Do not send sensitive business information.')
   msg.add_attachment(report_bytes,maintype='application',subtype='zip',filename='VELXTRIA_Report.zip')
   host=os.environ['VELXTRIA_SMTP_HOST'];port=int(os.getenv('VELXTRIA_SMTP_PORT','587'))
   with smtplib.SMTP(host,port,timeout=20) as smtp:
    smtp.starttls()
    smtp.login(os.environ['VELXTRIA_SMTP_USER'],os.environ['VELXTRIA_SMTP_PASSWORD'])
    smtp.send_message(msg)
   with db() as c:
    c.execute("UPDATE deliveries SET status='sent',last_error='' WHERE report_id=?",(report_id,))
    c.execute("UPDATE reports SET email_status='sent' WHERE id=?",(report_id,))
  except Exception as exc:
   if 'report_id' in locals():
    retry=(attempts+1)<3
    with db() as c:
     c.execute('UPDATE deliveries SET status=?,last_error=?,next_attempt=? WHERE report_id=?',('retry' if retry else 'failed',str(exc)[:160],now()+min(3600,60*2**attempts),report_id))
     c.execute('UPDATE reports SET email_status=? WHERE id=?',('retry' if retry else 'failed',report_id))
   print('Email delivery error:',type(exc).__name__)

def month_start():
 d=datetime.now(timezone.utc)
 return int(datetime(d.year,d.month,1,tzinfo=timezone.utc).timestamp())

if __name__=='__main__':
 db().close()
 mode=os.getenv('VELXTRIA_DEPLOYMENT_MODE','local')
 if mode == 'render-preview' and not os.getenv('VELXTRIA_PREVIEW_PASSWORD'):
  raise SystemExit('Set VELXTRIA_PREVIEW_PASSWORD before starting Render preview')
 host='0.0.0.0' if mode == 'render-preview' else '127.0.0.1'
 port=int(os.getenv('PORT','8878'))
 print(f'VELXTRIA V4 {mode} portal on {host}:{port}; database={"postgresql" if persistent.REMOTE else "sqlite-local"}; storage={"private-supabase" if persistent.REMOTE else "local"}')
 if DELIVERY_ENABLED:
  Thread(target=delivery_worker,daemon=True).start()
  print('SMTP delivery queue enabled')
 else:print('SMTP not configured: reports available for download only')
 print('PRIVATE TEST ONLY — not production ready; no real customer data or payments.')
 ThreadingHTTPServer((host,port),Handler).serve_forever()
