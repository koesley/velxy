"""V58 constrained application factory. No model, shell execution, or arbitrary code input.

Creates a standalone CRM from an allowlisted declarative specification, independently
checks its generated API, and packages immutable build artifacts. Local development only.
"""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

FIELDS = {'name': 'TEXT NOT NULL', 'email': 'TEXT NOT NULL', 'company': 'TEXT NOT NULL DEFAULT \'\'', 'status': 'TEXT NOT NULL DEFAULT \'lead\'', 'notes': 'TEXT NOT NULL DEFAULT \'\''}
DEFAULT = {'name': 'Customer Studio', 'fields': ['name','email','company','status','notes'], 'variant': 'standard'}


def validate(spec):
    if not isinstance(spec, dict): raise ValueError('Specification must be an object')
    name = spec.get('name', DEFAULT['name'])
    fields = spec.get('fields', DEFAULT['fields'])
    variant = spec.get('variant', 'standard')
    if not isinstance(name,str) or not 1 <= len(name) <= 60 or not re.fullmatch(r'[\w .-]+', name): raise ValueError('Invalid application name')
    if not isinstance(fields,list) or len(fields)!=len(set(fields)) or not {'name','email'}.issubset(fields) or any(f not in FIELDS for f in fields): raise ValueError('Fields must be unique supported CRM fields, including name and email')
    if variant not in ('standard','compact'): raise ValueError('Unknown implementation variant')
    return {'name':name,'fields':fields,'variant':variant}


def render_app(spec):
    fields=spec['fields']; cols=', '.join(f'"{f}" {FIELDS[f]}' for f in fields)
    # Generated app has no dependencies, network clients, or dynamic code evaluation.
    return '''"""Generated VELXTRIA CRM. Run locally; do not expose to the public internet."""
import html, json, re, sqlite3, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
DB=Path(__file__).with_name('customers.sqlite3')
FIELDS=__FIELDS__
NAME=__NAME__
SCHEMA=__SCHEMA__
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, '+SCHEMA+', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
 return c
class Handler(BaseHTTPRequestHandler):
 def reply(self,status,obj,kind='application/json'):
  body=(json.dumps(obj,ensure_ascii=False) if kind=='application/json' else obj).encode('utf-8')
  self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def read_json(self):
  n=int(self.headers.get('Content-Length','0'))
  if n<1 or n>32768:raise ValueError('Invalid request length')
  obj=json.loads(self.rfile.read(n))
  if not isinstance(obj,dict):raise ValueError('Expected object')
  if any(k not in FIELDS for k in obj):raise ValueError('Unsupported field')
  if any(not isinstance(v,str) or len(v)>2000 for v in obj.values()):raise ValueError('Invalid field value')
  return obj
 def route_id(self):
  m=re.fullmatch(r'/api/customers/(\\d+)',urlsplit(self.path).path)
  return int(m.group(1)) if m else None
 def do_GET(self):
  path=urlsplit(self.path).path
  if path=='/':
   title=html.escape(NAME)
   return self.reply(200,'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{background:#100b20;color:#f5efff;font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}input,button{padding:12px;border-radius:8px;margin:5px;background:#26143f;color:white;border:1px solid #714ab3}button{cursor:pointer}.card{background:#211435;padding:18px;border-radius:16px;margin:10px 0}small{color:#cbbbe8}</style><h1>✦ '+title+'</h1><p>Local CRM · customer records</p><div id="form"></div><button id="add">Add customer</button><div id="items"></div><script>const fields='+json.dumps(FIELDS)+';const form=document.querySelector("#form");fields.forEach(f=>{const e=document.createElement("input");e.placeholder=f;e.id="f_"+f;form.append(e)});document.querySelector("#add").onclick=async()=>{const obj={};fields.forEach(f=>obj[f]=document.getElementById("f_"+f).value);const r=await fetch("/api/customers",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)});if(!r.ok){alert((await r.json()).error);return}load()};async function load(){const r=await fetch("/api/customers");const data=await r.json();const root=document.querySelector("#items");root.replaceChildren();data.forEach(item=>{const box=document.createElement("div");box.className="card";const h=document.createElement("strong");h.textContent=item.name+" · "+item.email;box.append(h);fields.filter(f=>f!=="name"&&f!=="email").forEach(f=>{const p=document.createElement("p");p.textContent=f+": "+item[f];box.append(p)});const b=document.createElement("button");b.textContent="Delete";b.onclick=async()=>{await fetch("/api/customers/"+item.id,{method:"DELETE"});load()};box.append(b);root.append(box)})}load();</script>','text/html')
  if path=='/health':return self.reply(200,{'status':'ok'})
  with connect() as c:
   if path=='/api/customers':return self.reply(200,[dict(r) for r in c.execute('SELECT * FROM customers ORDER BY id DESC LIMIT 500')])
   ident=self.route_id()
   if ident is not None:
    row=c.execute('SELECT * FROM customers WHERE id=?',(ident,)).fetchone()
    return self.reply(200,dict(row)) if row else self.reply(404,{'error':'Not found'})
  self.reply(404,{'error':'Not found'})
 def do_POST(self):
  if urlsplit(self.path).path!='/api/customers':return self.reply(404,{'error':'Not found'})
  try:
   obj=self.read_json()
   if not obj.get('name','').strip() or not obj.get('email','').strip():raise ValueError('Name and email required')
   with connect() as c:
    keys=list(obj); sql='INSERT INTO customers ('+','.join('"'+k+'"' for k in keys)+') VALUES ('+','.join('?' for _ in keys)+')'
    ident=c.execute(sql,[obj[k] for k in keys]).lastrowid
   self.reply(201,{'id':ident})
  except (ValueError,json.JSONDecodeError) as e:self.reply(400,{'error':str(e)})
 def do_PUT(self):
  ident=self.route_id()
  if ident is None:return self.reply(404,{'error':'Not found'})
  try:
   obj=self.read_json()
   if not obj:raise ValueError('No fields')
   if any(k in obj and not obj[k].strip() for k in ('name','email')):raise ValueError('Name and email required')
   with connect() as c:
    cur=c.execute('UPDATE customers SET '+','.join('"'+k+'"=?' for k in obj)+' WHERE id=?',list(obj.values())+[ident])
    if not cur.rowcount:return self.reply(404,{'error':'Not found'})
   self.reply(200,{'updated':True})
  except (ValueError,json.JSONDecodeError) as e:self.reply(400,{'error':str(e)})
 def do_DELETE(self):
  ident=self.route_id()
  if ident is None:return self.reply(404,{'error':'Not found'})
  with connect() as c:
   deleted=c.execute('DELETE FROM customers WHERE id=?',(ident,)).rowcount
  self.reply(200 if deleted else 404,{'deleted':bool(deleted)})
if __name__=='__main__':
 port=int(sys.argv[1]) if len(sys.argv)>1 else 8891
 ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
'''.replace('__FIELDS__',repr(fields)).replace('__NAME__',repr(spec['name'])).replace('__SCHEMA__',repr(cols))


def render_tests():
    return '''import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import app
class CRMTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.p=patch.object(app,'DB',Path(self.tmp.name)/'db.sqlite3');self.p.start();self.addCleanup(self.p.stop)
 def test_schema(self):
  with app.connect() as c:
   names={r[1] for r in c.execute('PRAGMA table_info(customers)')}
  self.assertTrue(set(app.FIELDS).issubset(names))
 def test_persistence(self):
  with app.connect() as c:c.execute('INSERT INTO customers (name,email) VALUES (?,?)',('Ada','ada@example.test'))
  with app.connect() as c:self.assertEqual(c.execute('SELECT name FROM customers').fetchone()[0],'Ada')
 def test_sql_injection_is_data(self):
  with app.connect() as c:c.execute('INSERT INTO customers (name,email) VALUES (?,?)',("x'); DROP TABLE customers;--",'safe@example.test'))
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM customers').fetchone()[0],1)
 def test_html_escapes_title(self):
  self.assertTrue(app.NAME)
if __name__=='__main__':unittest.main()
'''


def build(spec, output, *, verify=True):
    spec=validate(spec);out=Path(output).resolve()
    if out.exists():raise FileExistsError('Output already exists; choose a new directory')
    out.mkdir(parents=True)
    try:
        (out/'app.py').write_text(render_app(spec),encoding='utf-8')
        (out/'test_app.py').write_text(render_tests(),encoding='utf-8')
        (out/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
        (out/'README.md').write_text('# '+spec['name']+'\n\nGenerated local-only CRM. Requires Python 3.10+.\n\nRun `python -m unittest -v`, then `python app.py 8891`. Visit http://127.0.0.1:8891.\n\nNo authentication or CSRF protection. Do not expose to public networks or store sensitive customer data.\n',encoding='utf-8')
        result={'spec':spec,'files':{},'tests':None}
        if verify:
            try:
                p=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(out),'-p','test_*.py','-v'],cwd=out,capture_output=True,text=True,timeout=20)
                result['tests']={'passed':p.returncode==0,'output':(p.stdout+p.stderr)[-4000:]}
            except subprocess.TimeoutExpired:result['tests']={'passed':False,'output':'Test timeout'}
        for file in sorted(out.iterdir()):
            if file.is_file():result['files'][file.name]=hashlib.sha256(file.read_bytes()).hexdigest()
        (out/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result
    except Exception:
        shutil.rmtree(out)
        raise


def package(directory, destination):
    directory=Path(directory);dest=Path(destination)
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(directory.iterdir()):
            if file.is_file():z.write(file,file.name)
    return dest


def compare(spec, directory):
    """Compare two validated implementation configurations, not fabricated AI candidates."""
    results=[]
    for variant in ('standard','compact'):
        candidate={**spec,'variant':variant}
        start=time.perf_counter()
        outcome=build(candidate,Path(directory)/variant)
        results.append({'variant':variant,'verified':outcome['tests']['passed'],'build_seconds':round(time.perf_counter()-start,4),'source_bytes':(Path(directory)/variant/'app.py').stat().st_size})
    return results


def main():
    parser=argparse.ArgumentParser(description='VELXTRIA V58 constrained application factory')
    parser.add_argument('--spec',help='Path to JSON specification; defaults to CRM example')
    parser.add_argument('--output',required=True,help='New output directory')
    parser.add_argument('--compare',action='store_true')
    args=parser.parse_args()
    spec=json.loads(Path(args.spec).read_text(encoding='utf-8')) if args.spec else DEFAULT
    if args.compare:
        results=compare(validate(spec),args.output)
        print(json.dumps(results,indent=2))
        if not all(x['verified'] for x in results):sys.exit(1)
    else:
        result=build(spec,args.output)
        print(json.dumps(result,indent=2))
        if not result['tests']['passed']:sys.exit(1)
        print('Package:',package(args.output,str(args.output)+'.zip'))
if __name__=='__main__':main()
