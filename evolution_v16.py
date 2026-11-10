"""Evolution V16: static inspection and opt-in offline container testing of Omega exports.
Never executes generated applications inside the portal process.
"""
import ast,hashlib,html,io,json,zipfile
import omega_v15

CSS="""\n.v16{max-width:960px;margin:auto}.v16 .panel{background:#1b142b;border:1px solid #6a5094;border-radius:16px;padding:24px;margin:16px 0}.v16 a{color:#ddc1ff}"""
DOCKERFILE="""FROM python:3.12-slim
WORKDIR /app
COPY app.py test_app.py schema.json ./
RUN useradd -m -u 10001 runner && chown -R runner:runner /app
USER runner
CMD ["python", "-m", "unittest", "-v", "test_app"]
"""
COMPOSE="""services:
  evolution-tests:
    build: .
    network_mode: none
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=16m
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    pids_limit: 64
    mem_limit: 256m
    cpus: 1.0
"""
SCRIPT="""#!/usr/bin/env python3
# Requires Docker. This script runs ONLY the generated unit tests, not the web server.
import subprocess,sys
command=['docker','compose','-f','compose.evolution.yml','run','--build','--rm','--no-deps','evolution-tests']
print('Running isolated unit tests (network disabled; resource limits applied).')
try: result=subprocess.run(command,timeout=180,check=False)
except (FileNotFoundError,subprocess.TimeoutExpired) as exc:
 print('Docker unavailable or test timed out:',exc,file=sys.stderr);sys.exit(2)
sys.exit(result.returncode)
"""
REVIEW="""# Evolution V16 — Manual release review

- [ ] Confirm generated fields and data rules match business requirements.
- [ ] Review source, including `app.py`, and inspect `INSPECTION.json`.
- [ ] Run `python run_isolated_tests.py` with Docker installed.
- [ ] Confirm tests pass; review any warnings.
- [ ] Add authentication, authorization, CSRF protection and operational safeguards before internet exposure.
- [ ] Create a separate deployment plan, backup policy and rollback procedure.

This export does NOT deploy, run patches, or repair code automatically.
Docker isolation reduces risk but is not a perfect security boundary for hostile code.
Never mount secrets or your live database into the test container.
"""

def inspect_files(files):
    findings=[]
    for name in ('app.py','test_app.py'):
        try: ast.parse(files[name].decode('utf-8'),filename=name)
        except (SyntaxError,UnicodeError) as exc:findings.append({'severity':'error','file':name,'message':'Python parse failed: '+str(exc)})
    try:
        schema=json.loads(files['schema.json'])
        if not isinstance(schema.get('fields'),list) or not schema['fields']:raise ValueError('No fields')
    except (ValueError,KeyError,TypeError) as exc:findings.append({'severity':'error','file':'schema.json','message':str(exc)})
    runtime=files['app.py'].decode('utf-8',errors='replace')
    if "('127.0.0.1',8899)" not in runtime:findings.append({'severity':'error','file':'app.py','message':'Expected localhost-only binding missing'})
    if 'ThreadingHTTPServer' in runtime:findings.append({'severity':'warning','file':'app.py','message':'Unauthenticated local HTTP service; never expose publicly'})
    if 'csrf' not in runtime.lower():findings.append({'severity':'warning','file':'app.py','message':'CSRF protection not present; local-only use'})
    return {'version':'16.1','mode':'static-inspection','passed':not any(f['severity']=='error' for f in findings),'findings':findings,'limitations':['No automatic code execution','No AI auto-repair','No deployment','Docker tests require user action']}

def package(c,user_id,app_id):
    base=omega_v15.package(c,user_id,app_id)
    with zipfile.ZipFile(io.BytesIO(base)) as z:
        files={n:z.read(n) for n in z.namelist()}
    report=inspect_files(files)
    if not report['passed']:raise ValueError('Generated source did not pass static inspection')
    files.pop('SHA256SUMS.txt',None)
    files.update({'INSPECTION.json':json.dumps(report,indent=2).encode(),'Dockerfile':DOCKERFILE.encode(),'compose.evolution.yml':COMPOSE.encode(),'run_isolated_tests.py':SCRIPT.encode(),'RELEASE_REVIEW.md':REVIEW.encode()})
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return out.getvalue()

def render(c,user_id):
    apps=c.execute('SELECT id,title,state FROM v13_apps WHERE user_id=? ORDER BY created DESC LIMIT 100',(user_id,)).fetchall()
    result=['<div class="v16"><div class="panel"><h1>◈ EVOLUTION V16 — Software Inspection Laboratory</h1><p>Download approved Omega apps with static inspection results, offline Docker test tooling and a manual release review.</p><p><strong>Safety:</strong> VELXTRIA never runs exported code on the portal server. Docker testing is optional and must be launched manually.</p><p>AI repair, automatic deployment and live health monitoring are not implemented in this milestone.</p></div>']
    for aid,title,state in apps:
        result.append('<div class="panel"><h3>'+html.escape(title)+'</h3><p>Status: '+html.escape(state)+'</p>')
        if state=='published':result.append('<a href="/evolution/export?app='+html.escape(aid,quote=True)+'">Download inspected app + isolated test harness (.zip)</a>')
        else:result.append('<p>Publish and approve this app in Singularity X to enable export.</p>')
        result.append('</div>')
    if not apps:result.append('<div class="panel">No apps yet. <a href="/singularity-x">Create an app</a>.</div>')
    return ''.join(result)+'</div>'
