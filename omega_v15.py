"""V15 Omega: deterministic, reviewable standalone local app generator.
No AI-written code execution or production deployment.
"""
import io, zipfile, json, html, re, hashlib
import prometheus_v14 as v14
import singularity_x_v13 as v13

CSS="""\n.v15{max-width:980px;margin:auto}.v15 .panel{background:#1b142b;border:1px solid #6a5094;border-radius:16px;padding:24px;margin:16px 0}.v15 a{color:#ddc1ff}.v15 code{color:#bfa3ff}"""

# All exported applications share the same audited runtime. Only validated JSON schemas vary.
RUNTIME=r"""# VELXTRIA Omega generated LOCAL-ONLY mini app.
# Run with Python 3.10+; binds exclusively to 127.0.0.1.
# No authentication: NEVER expose this server to the public internet.
import json, sqlite3, html, re, secrets, pathlib, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

ROOT=pathlib.Path(__file__).resolve().parent
SCHEMA=json.loads((ROOT/'schema.json').read_text(encoding='utf-8'))
DB=ROOT/'app_data.sqlite3'

def validate(data):
    clean={}; errors=[]
    for f in SCHEMA['fields']:
        value=str(data.get(f['key'],'')).strip()
        if f['required'] and not value: errors.append(f['label']+' is required')
        if len(value)>500: errors.append(f['label']+' exceeds 500 characters')
        if value and f['type']=='number':
            try: float(value)
            except ValueError: errors.append(f['label']+' must be numeric')
        if value and f['type']=='email' and not re.fullmatch(r'[^\\s@]+@[^\\s@]+\\.[^\\s@]+',value):errors.append(f['label']+' must be an email')
        if value and f['type']=='date':
            try: datetime.date.fromisoformat(value)
            except ValueError: errors.append(f['label']+' must be a valid date')
        if value and f['type']=='time':
            try: datetime.time.fromisoformat(value)
            except ValueError: errors.append(f['label']+' must be a valid time')
        if value and f['type']=='choice' and value not in f['choices']:errors.append(f['label']+' must match an option')
        clean[f['key']]=value
    return clean,errors

def connection():
    c=sqlite3.connect(DB)
    c.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return c

def esc(x):return html.escape(str(x),quote=True)

class Handler(BaseHTTPRequestHandler):
    def respond(self,status,body):
        payload=body.encode('utf-8');self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(payload)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        if self.path!='/':return self.respond(404,'Not found')
        with connection() as c:rows=c.execute('SELECT id,payload FROM records ORDER BY rowid DESC LIMIT 100').fetchall()
        parts=['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Omega Local App</title><style>body{background:#141021;color:#f4edff;font:16px system-ui;max-width:800px;margin:40px auto;padding:20px}input,select,button{padding:10px;margin:6px;background:#281e3e;color:white;border:1px solid #775ba0;border-radius:8px}label{display:block}section{padding:12px;border-bottom:1px solid #55406d}</style></head><body><h1>'+esc(SCHEMA['kind'])+'</h1><p>Local-only generated app · Do not expose publicly</p><form method="post" action="/add">']
        for f in SCHEMA['fields']:
            parts.append('<label>'+esc(f['label']))
            if f['type']=='choice':
                parts.append('<select name="'+esc(f['key'])+'"><option value="">Select...</option>'+''.join('<option value="'+esc(x)+'">'+esc(x)+'</option>' for x in f['choices'])+'</select>')
            else:
                typ={'email':'email','number':'number','date':'date','time':'time'}.get(f['type'],'text')
                parts.append('<input name="'+esc(f['key'])+'" type="'+typ+'" maxlength="500" '+('required' if f['required'] else '')+'>')
            parts.append('</label>')
        parts.append('<button>Add record</button></form><h2>Saved records</h2>')
        for _,payload in rows:
            values=json.loads(payload)
            parts.append('<section>'+''.join('<p><b>'+esc(f['label'])+':</b> '+esc(values.get(f['key'],''))+'</p>' for f in SCHEMA['fields'])+'</section>')
        parts.append('</body></html>');self.respond(200,''.join(parts))
    def do_POST(self):
        if self.path!='/add':return self.respond(404,'Not found')
        try: n=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.respond(400,'Invalid length')
        if n<0 or n>16000:return self.respond(413,'Form too large')
        data=parse_qs(self.rfile.read(n).decode('utf-8'),keep_blank_values=True)
        values,errors=validate({k:v[0] for k,v in data.items() if v})
        if errors:return self.respond(400,'<h2>Invalid entry</h2><p>'+esc('; '.join(errors))+'</p><a href="/">Back</a>')
        with connection() as c:c.execute('INSERT INTO records VALUES (?,?)',(secrets.token_hex(12),json.dumps(values)))
        self.send_response(303);self.send_header('Location','/');self.end_headers()

if __name__=='__main__':
    print('Local-only app: http://127.0.0.1:8899')
    ThreadingHTTPServer(('127.0.0.1',8899),Handler).serve_forever()
"""
TESTS=r"""import unittest, tempfile, pathlib, json, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import app
class GeneratedAppTests(unittest.TestCase):
 def sample(self):
  return {f['key']: {'number':'12.5','email':'test@example.com','date':'2026-12-01','time':'12:30','choice':f['choices'][0] if f['choices'] else ''}.get(f['type'],'Example') for f in app.SCHEMA['fields']}
 def test_valid_record(self):
  _,errors=app.validate(self.sample());self.assertEqual(errors,[])
 def test_required_fields(self):
  data=self.sample();key=next(f['key'] for f in app.SCHEMA['fields'] if f['required']);data[key]='';self.assertTrue(app.validate(data)[1])
 def test_invalid_email_or_number(self):
  for f in app.SCHEMA['fields']:
   if f['type'] in ('email','number'):
    data=self.sample();data[f['key']]='invalid-value';self.assertTrue(app.validate(data)[1])
 def test_database_roundtrip(self):
  with tempfile.TemporaryDirectory() as d:
   app.DB=pathlib.Path(d)/'test.sqlite3'
   with app.connection() as c:c.execute('INSERT INTO records VALUES (?,?)',('test',json.dumps(self.sample())))
   with app.connection() as c:self.assertEqual(c.execute('SELECT count(*) FROM records').fetchone()[0],1)
if __name__=='__main__':unittest.main()
"""
README="""# VELXTRIA Omega Generated App\n\nThis is a **standalone, local-only** app generated from an approved declarative schema. It does not use AI-written executable code.\n\n## Run\n\n1. Install Python 3.10+. No pip packages are needed.\n2. Run `python -m unittest -v` in this directory.\n3. Run `python app.py`, then open http://127.0.0.1:8899.\n\n## Safety and deployment\n\n- Binds to localhost only; **NO authentication**. Never expose it directly to the internet.\n- Data is stored in `app_data.sqlite3` beside the application. Back it up regularly.\n- No production deployment, container isolation, self-modification, or AI auto-repair is performed.\n- Review all generated files before using real customer data.\n"""

def package(c,u,aid):
    row=v13.get(c,u,aid)
    if row[4]!='published':raise ValueError('Publish and approve the app before generating source code')
    schema=v14.normalize(json.loads(row[3]))
    # Strictly require current schema to have passed its simulation before publishing.
    tests=json.loads(row[5]);
    if not tests or not all(t.get('pass') for t in tests):raise ValueError('Passed simulation tests required')
    files={'app.py':RUNTIME.encode(),'schema.json':json.dumps(schema,indent=2).encode(),'test_app.py':TESTS.encode(),'README.md':README.encode()}
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(content).hexdigest()+'  '+name+'\n' for name,content in sorted(files.items())).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in files.items():z.writestr(name,content)
    return out.getvalue()

def render(c,u,aid):
    apps=c.execute('SELECT id,title,state FROM v13_apps WHERE user_id=? ORDER BY created DESC LIMIT 100',(u,)).fetchall()
    h=['<div class="v15"><div class="panel"><h1>✦ OMEGA V15 — Code Foundry</h1><p>Generate standalone, reviewable Python software from approved V13/V14 designs. Source packages include a SQLite-backed local app, validation, tests, and integrity hashes.</p><p><strong>Safety:</strong> exports only; no automatic code execution, self-rewriting, or cloud deployment.</p><p><a href="/prometheus">Design in Prometheus</a> · <a href="/singularity-x">Publish in Singularity X</a></p></div>']
    for appid,title,state in apps:
        h.append('<div class="panel"><h3>'+html.escape(title)+'</h3><p>Status: '+html.escape(state)+'</p>')
        if state=='published':h.append('<p><a href="/omega/export?app='+html.escape(appid,quote=True)+'">Download standalone app + tests (.zip)</a></p>')
        else:h.append('<p>Run simulation tests and approve publication in Singularity X to unlock code export.</p>')
        h.append('</div>')
    if not apps:h.append('<div class="panel">No apps yet. Create one in Singularity X.</div>')
    return ''.join(h)+'</div>'
