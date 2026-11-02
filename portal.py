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
