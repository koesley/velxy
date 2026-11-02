"""Local scheduled CSV -> reports -> email delivery. Python standard library only."""
import argparse, csv, hashlib, json, os, shutil, smtplib, sqlite3, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

ROOT=Path(__file__).resolve().parent
INBOX=ROOT/'inbox'; DELIVERED=ROOT/'delivered'; FAILED=ROOT/'failed'; LOGS=ROOT/'logs'; DB=ROOT/'state.sqlite3'
for folder in (INBOX,DELIVERED,FAILED,LOGS): folder.mkdir(exist_ok=True)

def stamp(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def state():
    db=sqlite3.connect(DB)
    db.execute('CREATE TABLE IF NOT EXISTS jobs (digest TEXT PRIMARY KEY, filename TEXT, status TEXT, updated TEXT, details TEXT)')
    db.commit(); return db

def write_log(event,**fields):
    with (LOGS/'events.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps({'time':stamp(),'event':event,**fields})+'\n')

def process(source,send=False):
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    with state() as db:
        prior=db.execute('SELECT status FROM jobs WHERE digest=?',(digest,)).fetchone()
        if prior and prior[0] in ('delivered','ready','send_unknown'):
            print(f'SKIP {source.name}: already {prior[0]} (same content)');return
        if prior and prior[0]=='failed':
            print(f'SKIP {source.name}: previously failed; inspect logs before retrying');return
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?)',(digest,source.name,'processing',stamp(),''));db.commit()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            shutil.copy2(ROOT/'automate.py',work/'automate.py')
            shutil.copy2(source,work/'messy_sales_input.csv')
            run=subprocess.run([sys.executable,str(work/'automate.py')],cwd=work,capture_output=True,text=True,timeout=90)
            if run.returncode: raise ValueError((run.stderr or run.stdout)[-1000:])
            report=work/'output'
            required=['cleaned_sales.csv','rejected_rows.csv','monthly_summary.csv','product_summary.csv','run_summary.txt']
            if not all((report/n).exists() for n in required): raise RuntimeError('Missing expected report files')
            # Separate immutable output per input content; no overwriting old customer results.
            destination=DELIVERED/(source.stem[:45]+'_'+digest[:12]);destination.mkdir(exist_ok=True)
            archive=destination/'VELXTRIA_Report.zip'
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                for n in required:z.write(report/n,arcname=n)
            (destination/'summary.txt').write_text((report/'run_summary.txt').read_text(encoding='utf-8'),encoding='utf-8')
            (destination/'source_sha256.txt').write_text(digest+'\n',encoding='utf-8')
            if send:
                recipient=os.getenv('VELXTRIA_RECIPIENT','').strip()
                host=os.getenv('VELXTRIA_SMTP_HOST','').strip()
                user=os.getenv('VELXTRIA_SMTP_USER','').strip()
                password=os.getenv('VELXTRIA_SMTP_PASSWORD','')
                sender=os.getenv('VELXTRIA_SMTP_FROM',user)
                port=int(os.getenv('VELXTRIA_SMTP_PORT','587'))
                if not all((recipient,host,user,password,sender)): raise RuntimeError('Email not configured. Set VELXTRIA_RECIPIENT and SMTP environment variables; report is saved locally.')
                if '@' not in recipient or ',' in recipient or '\n' in recipient:raise ValueError('One fixed recipient email address required')
                msg=EmailMessage();msg['From']=sender;msg['To']=recipient;msg['Subject']='VELXTRIA automated report — '+source.stem
                msg.set_content('Your processed report is attached. Please review rejected_rows.csv and the reconciliation summary before using totals for decisions.\n')
                msg.add_attachment(archive.read_bytes(),maintype='application',subtype='zip',filename='VELXTRIA_Report.zip')
                # If SMTP fails after accepting DATA, delivery may be ambiguous: never automatically resend.
                try:
                    with smtplib.SMTP(host,port,timeout=30) as smtp:
                        smtp.starttls();smtp.login(user,password);smtp.send_message(msg)
                except Exception as exc:
                    with state() as db:db.execute('UPDATE jobs SET status=?,updated=?,details=? WHERE digest=?',('send_unknown',stamp(),str(exc)[:500],digest));db.commit()
                    write_log('send_unknown',file=source.name,error=str(exc));print('Email delivery uncertain; report saved. Check inbox and logs before manual retry.');return
                status='delivered'
            else:status='ready'
            with state() as db:db.execute('UPDATE jobs SET status=?,updated=?,details=? WHERE digest=?',(status,stamp(),str(archive),digest));db.commit()
            write_log(status,file=source.name,archive=str(archive))
            print(f'{status.upper()} {source.name} -> {archive}')
    except Exception as exc:
        with state() as db:db.execute('UPDATE jobs SET status=?,updated=?,details=? WHERE digest=?',('failed',stamp(),str(exc)[:500],digest));db.commit()
        write_log('failed',file=source.name,error=str(exc));print(f'FAILED {source.name}: {exc}')

def main():
    p=argparse.ArgumentParser(description='Process all new CSVs in inbox and optionally email reports')
    p.add_argument('--send',action='store_true',help='Email to configured recipient after processing')
    args=p.parse_args()
    sources=sorted(INBOX.glob('*.csv'))
    if not sources:print('No CSV files in inbox.')
    for file in sources:process(file,send=args.send)
if __name__=='__main__':main()
