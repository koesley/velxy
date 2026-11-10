"""Phoenix V17: export an opt-in local repair-review workbench. No server-side code execution."""
import hashlib, html, io, json, zipfile
import evolution_v16

CSS='\n.v17{max-width:960px;margin:auto}.v17 .panel{background:#1b142b;border:1px solid #6a5094;border-radius:16px;padding:24px;margin:16px 0}.v17 a{color:#ddc1ff}'
WORKBENCH=r'''#!/usr/bin/env python3
"""Offline, review-first repair proposal helper. No patches are applied automatically."""
import argparse, ast, difflib, hashlib, json, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
ALLOWED={'app.py','test_app.py'}
def digest(data):return hashlib.sha256(data).hexdigest()
def propose(filename, candidate_path):
    if filename not in ALLOWED:raise ValueError('Only app.py and test_app.py are reviewable')
    original=(ROOT/filename).read_bytes()
    candidate=pathlib.Path(candidate_path).read_bytes()
    if len(candidate)>250_000:raise ValueError('Patch too large')
    ast.parse(candidate.decode('utf-8'),filename=filename)
    diff=''.join(difflib.unified_diff(original.decode().splitlines(True),candidate.decode().splitlines(True),fromfile='original/'+filename,tofile='proposed/'+filename))
    if not diff:raise ValueError('No change detected')
    proposals=ROOT/'phoenix_proposals';proposals.mkdir(exist_ok=True)
    ref=digest(original)[:12]+'-'+digest(candidate)[:12]
    (proposals/(ref+'.diff')).write_text(diff,encoding='utf-8')
    (proposals/(ref+'.json')).write_text(json.dumps({'target':filename,'original_sha256':digest(original),'candidate_sha256':digest(candidate),'status':'PROPOSED_NOT_APPLIED','test_status':'NOT_RUN','deployment_status':'NOT_DEPLOYED'},indent=2),encoding='utf-8')
    print('Proposal saved:',ref,'\nReview:',proposals/(ref+'.diff'))
    print('NOT APPLIED. After manual review, test in a separate copy with Docker.')
def diagnose(report_path, model):
    report=pathlib.Path(report_path).read_text(encoding='utf-8')[:12000]
    prompt='Analyze this local Python application test failure. Suggest a minimal fix and tests, but do not claim changes were made. Never request secrets or deployment.\n'+report
    data=json.dumps({'model':model,'prompt':prompt,'stream':False,'options':{'temperature':0.1}}).encode()
    req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=90) as response:
        answer=json.load(response).get('response','')
    path=ROOT/'phoenix_diagnosis.txt';path.write_text(answer,encoding='utf-8')
    print('Local Ollama analysis saved:',path,'\nNo files were modified.')
def main():
    p=argparse.ArgumentParser(description='Phoenix offline review-only workbench')
    s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('propose');a.add_argument('target',choices=sorted(ALLOWED));a.add_argument('candidate')
    d=s.add_parser('diagnose');d.add_argument('report');d.add_argument('--model',default='llama3.2')
    args=p.parse_args()
    if args.action=='propose':propose(args.target,args.candidate)
    else:diagnose(args.report,args.model)
if __name__=='__main__':main()
'''
README='''# PHOENIX V17 — Repair Proposal Workbench

This is an **opt-in, offline, review-first** workflow. Nothing is automatically patched, executed, approved, or deployed.

1. Run the generated tests in the V16 Docker harness: `python run_isolated_tests.py`. Save any failure output to `failure.txt`.
2. Optional local Ollama diagnosis (requires Ollama and `ollama pull llama3.2`): `python phoenix_workbench.py diagnose failure.txt`. Only send reports without secrets; Ollama must be running locally.
3. Prepare a candidate `candidate_app.py` yourself or using your editor. Then run: `python phoenix_workbench.py propose app.py candidate_app.py`.
4. Inspect `phoenix_proposals/*.diff` and the SHA-256 metadata. No source is changed by the command.
5. **Manually** create a disposable copy of the exported project, apply the reviewed candidate there, and rerun the Docker tests. Do not expose the generated web server publicly.
6. Only after independent review and testing, create a release candidate manually. This tool does not publish or deploy.

Ollama diagnosis is advisory, not an independent security review. Docker reduces risk but does not guarantee containment of hostile code. Never run arbitrary patches with access to production secrets or databases.
'''
def package(c,user_id,app_id):
    base=evolution_v16.package(c,user_id,app_id)
    with zipfile.ZipFile(io.BytesIO(base)) as z: files={name:z.read(name) for name in z.namelist()}
    files.pop('SHA256SUMS.txt',None)
    files['phoenix_workbench.py']=WORKBENCH.encode()
    files['PHOENIX_REPAIR_GUIDE.md']=README.encode()
    files['PHOENIX_STATUS.json']=json.dumps({'version':'17.1','repair':'review-only','ai':'optional local Ollama diagnosis','automatic_patch':False,'automatic_deploy':False},indent=2).encode()
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return out.getvalue()
def render(c,user_id):
    apps=c.execute('SELECT id,title,state FROM v13_apps WHERE user_id=? ORDER BY created DESC LIMIT 100',(user_id,)).fetchall()
    result=['<div class="v17"><div class="panel"><h1>✦ PHOENIX V17 — Repair Review Workbench</h1><p>Download published apps with optional local Ollama diagnosis, a safe diff proposal tool, and offline Docker test instructions.</p><p><strong>Review first:</strong> No AI patch is applied automatically. No code is executed in the portal. No automatic release or deployment.</p></div>']
    for aid,title,state in apps:
        result.append('<div class="panel"><h3>'+html.escape(title)+'</h3><p>Status: '+html.escape(state)+'</p>')
        if state=='published':result.append('<a href="/phoenix/export?app='+html.escape(aid,quote=True)+'">Download Phoenix repair workbench (.zip)</a>')
        else:result.append('<p>Publish this app through Singularity X first.</p>')
        result.append('</div>')
    if not apps:result.append('<div class="panel">No apps yet. <a href="/singularity-x">Create an app</a>.</div>')
    return ''.join(result)+'</div>'
