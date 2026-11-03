"""VELXTRIA V3 portal. Render preview requires VELXTRIA_PREVIEW_PASSWORD."""
import base64, csv, hashlib, hmac, html, io, json, os, secrets, shutil, smtplib, sqlite3, subprocess, sys, tempfile, time, urllib.parse, zipfile
from datetime import datetime, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread, Event
import payhip_integration

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
 c=sqlite3.connect(DB,timeout=15)
 c.execute('PRAGMA foreign_keys=ON')
 c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT "customer", access TEXT NOT NULL DEFAULT "demo", created INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires INTEGER NOT NULL, csrf TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))')
 c.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, filename TEXT NOT NULL, created INTEGER NOT NULL, status TEXT NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, digest TEXT NOT NULL, email_status TEXT NOT NULL DEFAULT "not_sent", FOREIGN KEY(user_id) REFERENCES users(id))')
 c.execute('CREATE TABLE IF NOT EXISTS deliveries (report_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, recipient TEXT NOT NULL, status TEXT NOT NULL DEFAULT "queued", attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT "", next_attempt INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(report_id) REFERENCES reports(id))')
 payhip_integration.setup(c)
 c.commit();return c

def pw_hash(password,salt): return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),250000).hex()
def escape(v): return html.escape(str(v),quote=True)
def valid_email(v):return '@' in v and '.' in v.split('@')[-1] and len(v)<255 and '\n' not in v

def shell(title,body,user=None,csrf=''):
 nav=('<a href="/">Dashboard</a> <a href="/account">Account</a> <form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="'+escape(csrf)+'"><button class="link">Sign out</button></form>') if user else '<a href="/login">Sign in</a> <a href="/register">Create demo account</a>'
 return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · VELXTRIA</title><link rel="stylesheet" href="/style.css"></head><body><header><div class="brand">✦ VELXTRIA <span>REPORT AUTOMATION</span></div><nav>{nav}</nav></header><main>{body}</main><footer>Local V3 prototype · Payhip webhook staging only · Never upload sensitive data</footer></body></html>"""

class Handler(BaseHTTPRequestHandler):
 def preview_guard(self):
  if os.getenv('VELXTRIA_DEPLOYMENT_MODE','local') != 'render-preview':
   return False
  if urllib.parse.urlsplit(self.path).path == '/healthz' and self.command == 'GET':
   return False
  # Allow Payhip POST notifications through private preview authentication.
  # The webhook handler separately checks the configured API-key signature.
  if urllib.parse.urlsplit(self.path).path == '/webhooks/payhip' and self.command == 'POST':
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
   username=password=''
  if scheme.lower() != 'basic' if 'scheme' in locals() else True:
   username=password=''
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
