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
 def do_GET(self):
  if urllib.parse.urlsplit(self.path).path == '/healthz': return self.respond(200,'ok','text/plain')
  if self.preview_guard(): return
  p=urllib.parse.urlsplit(self.path).path
  if p=='/style.css':return self.respond(200,(ROOT/'style.css').read_bytes(),'text/css; charset=utf-8')
  user,csrf,_=self.identity()
  if p=='/login':return self.respond(200,shell('Sign in','<section class="panel narrow"><h1>Welcome back</h1><form method="post" action="/login"><label>Email<input name="email" type="email" required></label><label>Password<input name="password" type="password" required></label><button>Sign in</button></form></section>'))
  if p=='/register':return self.respond(200,shell('Register','<section class="panel narrow"><h1>Create a local demo account</h1><p>This account does not verify Payhip payments.</p><form method="post" action="/register"><label>Email<input name="email" type="email" required></label><label>Password (12+ characters)<input name="password" type="password" minlength="12" required></label><button>Create account</button></form></section>'))
  if not user:return self.redirect('/login')
  if p=='/':
   with db() as c:
    reports=c.execute('SELECT id,filename,created,status,accepted,rejected,email_status FROM reports WHERE user_id=? ORDER BY created DESC LIMIT 30',(user['id'],)).fetchall()
    count=c.execute('SELECT count(*) FROM reports WHERE user_id=? AND created>=?',(user['id'],month_start())).fetchone()[0]
   rows=''.join('<tr><td>'+escape(r[1])+'</td><td>'+escape(datetime.fromtimestamp(r[2],timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+'</td><td>'+escape(r[3])+'</td><td>'+str(r[4])+' / '+str(r[5])+'</td><td><a href="/download?id='+escape(r[0])+'">Download ZIP</a></td><td>'+escape(r[6])+'</td></tr>' for r in reports)
   access='Local demo access' if user['access']=='demo' else 'Founder-granted access (not Payhip-verified)'
   body=f"""<section class="hero"><p class="eyebrow">CUSTOMER PORTAL</p><h1>Your reports, handled.</h1><p>Upload a supported sales CSV. VELXTRIA cleans records, flags errors, and creates downloadable reports automatically.</p></section><div class="stats"><div><b>{count}</b><small>Reports this month</small></div><div><b>{MAX_MONTHLY-count}</b><small>Remaining demo allowance</small></div><div><b>{escape(access)}</b><small>Access status</small></div></div><section class="panel"><h2>Process a CSV</h2><p>5 MB maximum · 50 reports/month · Supported sales-export schema only</p><form method="post" action="/upload" enctype="multipart/form-data"><input type="hidden" name="csrf" value="{escape(csrf)}"><label>Choose CSV<input type="file" name="file" accept=".csv,text/csv" required></label><label><input type="checkbox" name="email_report" value="yes"> Email the completed report to my account address (requires configured SMTP)</label><button>Generate report</button></form><details><summary>Required column headers</summary><code>{escape(', '.join(REQUIRED))}</code></details></section><section class="panel"><h2>Your reports</h2><div class="scroll"><table><thead><tr><th>File</th><th>Processed</th><th>Status</th><th>Accepted / flagged</th><th>Result</th><th>Email</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No reports yet.</td></tr>'}</tbody></table></div></section>"""
   if user['role']=='admin':
    with db() as c:
     users=c.execute('SELECT email,role,access FROM users ORDER BY created DESC').fetchall();errors=c.execute('SELECT count(*) FROM reports WHERE status != "ready"').fetchone()[0]
    body+='<section class="panel"><h2>Founder overview</h2><p>Accounts: '+str(len(users))+' · Failed reports: '+str(errors)+'</p><p>Payhip verification: <strong>STAGING ONLY — manual review; no automatic access</strong>. SMTP: <strong>'+('configured' if DELIVERY_ENABLED else 'not configured')+'</strong>. Do not use this prototype to enforce paid access.</p></section>'
   return self.respond(200,shell('Dashboard',body,user,csrf))
  if p=='/account':
   body='<section class="panel"><h1>Account</h1><p>'+escape(user['email'])+'</p><p>Access: '+escape(user['access'])+'</p><p>Payhip subscriptions are not linked in this local prototype. Reports are available in demo mode.</p></section>'
   return self.respond(200,shell('Account',body,user,csrf))
  if p=='/download':
   ident=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('id',[''])[0]
   with db() as c:row=c.execute('SELECT id FROM reports WHERE id=? AND user_id=? AND status="ready"',(ident,user['id'])).fetchone()
   if not row:return self.fail(404,'Report not found.',user,csrf)
   path=REPORTS/str(user['id'])/(ident+'.zip')
   if not path.is_file():return self.fail(404,'Report file unavailable.',user,csrf)
   return self.respond(200,path.read_bytes(),'application/zip',[('Content-Disposition','attachment; filename="VELXTRIA_Report.zip"')])
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
   except sqlite3.IntegrityError:return self.fail(409,'Account already exists.')
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
     target=REPORTS/str(user['id']);target.mkdir(parents=True,exist_ok=True)
     with zipfile.ZipFile(target/(ident+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
      for f in files:z.write(out/f,arcname=f)
    with db() as c:
     c.execute('INSERT INTO reports(id,user_id,filename,created,status,accepted,rejected,digest) VALUES (?,?,?,?,?,?,?,?)',(ident,user['id'],Path(filename).name[:120],now(),'ready',accepted,rejected,digest))
     if fields.get('email_report')=='yes':
      c.execute('INSERT INTO deliveries(report_id,user_id,recipient,status,next_attempt) VALUES (?,?,?,?,?)',(ident,user['id'],user['email'],'queued' if DELIVERY_ENABLED else 'not_configured',now()))
      c.execute('UPDATE reports SET email_status=? WHERE id=?',('queued' if DELIVERY_ENABLED else 'not_configured',ident))
   except Exception as e:return self.fail(422,'Could not process this file: '+str(e)[:240],user,csrf)
  return self.redirect('/?done=1')

def delivery_worker():
 """Local background queue; SMTP only when explicitly configured and user opted in."""
 while not STOP.wait(5):
  if not DELIVERY_ENABLED:continue
  try:
   with db() as c:
    row=c.execute('SELECT report_id,user_id,recipient,attempts FROM deliveries WHERE status IN ("queued","retry") AND next_attempt<=? AND attempts<3 ORDER BY next_attempt LIMIT 1',(now(),)).fetchone()
    if not row:continue
    report_id,user_id,recipient,attempts=row
    c.execute('UPDATE deliveries SET status="sending", attempts=attempts+1 WHERE report_id=?',(report_id,))
   path=REPORTS/str(user_id)/(report_id+'.zip')
   if not path.is_file():raise RuntimeError('Report archive missing')
   msg=EmailMessage();msg['Subject']='Your VELXTRIA report is ready';msg['From']=os.environ['VELXTRIA_SMTP_FROM'];msg['To']=recipient
   msg.set_content('Your requested VELXTRIA report is attached. This is a local demonstration. Do not send sensitive business information.')
   msg.add_attachment(path.read_bytes(),maintype='application',subtype='zip',filename='VELXTRIA_Report.zip')
   host=os.environ['VELXTRIA_SMTP_HOST'];port=int(os.getenv('VELXTRIA_SMTP_PORT','587'))
   with smtplib.SMTP(host,port,timeout=20) as smtp:
    smtp.starttls()
    smtp.login(os.environ['VELXTRIA_SMTP_USER'],os.environ['VELXTRIA_SMTP_PASSWORD'])
    smtp.send_message(msg)
   with db() as c:
    c.execute('UPDATE deliveries SET status="sent",last_error="" WHERE report_id=?',(report_id,))
    c.execute('UPDATE reports SET email_status="sent" WHERE id=?',(report_id,))
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
 print(f'VELXTRIA V3 {mode} portal on {host}:{port}')
 if DELIVERY_ENABLED:
  Thread(target=delivery_worker,daemon=True).start()
  print('SMTP delivery queue enabled')
 else:print('SMTP not configured: reports available for download only')
 print('PRIVATE TEST ONLY — not production ready; no real customer data or payments.')
 ThreadingHTTPServer((host,port),Handler).serve_forever()
