"""V62: publish-only FAQ widget and internal specialist collaboration.

The public FAQ is deterministic, never exposes private memory, and does not
call AI providers. Publishing requires the workspace owner.
"""
import html
import secrets
import time
import urllib.parse
import business_agents_v59 as agents

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS v62_widgets (
      workspace_id TEXT PRIMARY KEY,token TEXT NOT NULL UNIQUE,enabled INTEGER NOT NULL,
      created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS v62_collaborations (
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,objective TEXT NOT NULL,
      created_by INTEGER NOT NULL,created INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS v62_collaboration_tasks (
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,collaboration_id TEXT NOT NULL,
      agent TEXT NOT NULL,job_id TEXT NOT NULL,created INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS v62_collaboration_scope ON v62_collaborations(workspace_id,created)")

def publish(c,uid,wid,enabled):
    agents.core.access(c,uid,wid,write=True,owner=True)
    setup(c)
    row=c.execute("SELECT token FROM v62_widgets WHERE workspace_id=?",(wid,)).fetchone()
    token=row[0] if row else secrets.token_urlsafe(24)
    now=int(time.time())
    if row:c.execute("UPDATE v62_widgets SET enabled=?,updated=? WHERE workspace_id=?",(int(bool(enabled)),now,wid))
    else:c.execute("INSERT INTO v62_widgets VALUES(?,?,?,?,?)",(wid,token,int(bool(enabled)),now,now))
    agents.core.audit(c,uid,wid,"v62_widget_toggled","enabled" if enabled else "disabled")
    return token

def rotate(c,uid,wid):
    agents.core.access(c,uid,wid,write=True,owner=True)
    setup(c)
    token=secrets.token_urlsafe(24)
    c.execute("UPDATE v62_widgets SET token=?,updated=? WHERE workspace_id=?",(token,int(time.time()),wid))
    agents.core.audit(c,uid,wid,"v62_widget_token_rotated","")
    return token

def public_faq(c,token,question=""):
    if not isinstance(token,str) or not 25<=len(token)<=100:return None
    setup(c)
    row=c.execute("SELECT workspace_id FROM v62_widgets WHERE token=? AND enabled=1",(token,)).fetchone()
    if not row:return None
    wid=row[0]
    agents.init(c)
    # Only explicitly FAQ-tagged knowledge; internal memory and agent jobs are excluded.
    entries=c.execute("SELECT question,answer FROM bos59_knowledge WHERE workspace_id=? AND kind='faq' ORDER BY created DESC LIMIT 50",(wid,)).fetchall()
    if not question:return {"entries":entries,"answer":None}
    q=question.strip().casefold()[:200]
    if not q:return {"entries":entries,"answer":None}
    exact=next((a for k,a in entries if k.casefold()==q),None)
    if exact is not None:return {"entries":entries,"answer":exact}
    tokens=set(q.split())
    best=None;score=0
    for k,a in entries:
        words=set(k.casefold().split())
        match=len(tokens & words)
        if match>score and match>=2:score=match;best=a
    return {"entries":entries,"answer":best}

def widget_html(c,token,question=""):
    data=public_faq(c,token,question)
    if data is None:return None
    h=lambda v:html.escape(str(v),quote=True)
    out=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Business FAQ</title><style>body{font:16px system-ui;background:#101525;color:#f6f7ff;padding:18px;line-height:1.5}section{max-width:650px;margin:auto}input,button{padding:12px;border-radius:8px}input{width:70%;max-width:420px}button{cursor:pointer}article{padding:12px;margin:10px 0;border:1px solid #4c5872;border-radius:10px}</style><section><h2>Business FAQ</h2><p>Answers from business-published FAQs. No live AI chat or human support.</p>']
    out.append('<form method="get"><label for="q">Ask a question</label><p><input id="q" name="q" maxlength="200" value="'+h(question)+'"><button>Search</button></p></form>')
    if question:
        out.append('<article><strong>Answer</strong><p>'+h(data["answer"] or "No published answer matched. Please contact the business directly.")+'</p></article>')
    out.extend('<article><strong>'+h(k)+'</strong><p>'+h(a)+'</p></article>' for k,a in data["entries"])
    out.append('</section></html>')
    return ''.join(out)

def collaborate(c,uid,wid,objective):
    agents.core.access(c,uid,wid,write=True)
    if not isinstance(objective,str) or not 5<=len(objective.strip())<=500:raise ValueError("Invalid objective")
    setup(c)
    cid=secrets.token_hex(12);now=int(time.time())
    c.execute("INSERT INTO v62_collaborations VALUES(?,?,?,?,?)",(cid,wid,objective.strip(),uid,now))
    for agent in ("sales","marketing","support","operations","finance"):
        goal=("Review the objective from the "+agent+" perspective and draft a proposal for owner approval: "+objective.strip())[:1000]
        jid=agents.create_job(c,uid,wid,agent,goal)
        c.execute("INSERT INTO v62_collaboration_tasks VALUES(?,?,?,?,?,?)",(secrets.token_hex(12),wid,cid,agent,jid,now))
    agents.core.audit(c,uid,wid,"v62_collaboration_created",cid)
    return cid

def overview(c,uid,wid):
    role=agents.core.access(c,uid,wid);setup(c)
    widget=c.execute("SELECT token,enabled FROM v62_widgets WHERE workspace_id=?",(wid,)).fetchone()
    collaborations=c.execute("SELECT id,objective,created FROM v62_collaborations WHERE workspace_id=? ORDER BY created DESC LIMIT 50",(wid,)).fetchall()
    return role,widget,collaborations

def render(c,uid,wid,csrf):
    role,widget,collaborations=overview(c,uid,wid)
    h=lambda v:html.escape(str(v),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V62 · Website FAQ & Collaboration</h1><p>Publish curated FAQ answers to customers, and coordinate five specialist review queues. No automatic outbound actions.</p></section>']
    if role=="owner":
        out.append('<section class="panel"><h2>Public FAQ widget</h2><p>Status: '+('Published' if widget and widget[1] else 'Disabled')+'</p>')
        if widget:
            out.append('<p>Conversational assistant iframe (replace YOUR_DOMAIN):</p><pre>&lt;iframe src="https://YOUR_DOMAIN/assistant-v64/'+h(widget[0])+'" title="Business Assistant" loading="lazy"&gt;&lt;/iframe&gt;</pre>')
            out.append('<p>Embeddable iframe (replace YOUR_DOMAIN with your actual website domain):</p><pre>&lt;iframe src="https://YOUR_DOMAIN/faq-v62/'+h(widget[0])+'" title="Business FAQ" loading="lazy"&gt;&lt;/iframe&gt;</pre>')
        out.append('<form method="post" action="/business-collaboration-v62">'+hidden+'<button name="action" value="enable">Publish FAQ</button><button name="action" value="disable">Disable FAQ</button><button name="action" value="rotate">Rotate widget token</button></form></section>')
    if role in ("owner","editor"):
        out.append('<section class="panel"><h2>Start specialist collaboration</h2><form method="post" action="/business-collaboration-v62">'+hidden+'<label>Objective<textarea name="objective" required maxlength="500"></textarea></label><button name="action" value="collaborate">Create five agent tasks</button></form></section>')
    for cid,objective,created in collaborations:
        out.append('<section class="panel"><h3>'+h(objective)+'</h3><p>Five specialist tasks created for review. <a href="/business-agents-v59?w='+urllib.parse.quote(wid,safe='')+'">Open agent workforce</a></p></section>')
    out.append('<section class="panel"><p>Only FAQ-tagged entries are public when published. Internal business memory remains private. This is a searchable FAQ, not an AI chatbot.</p></section>')
    return ''.join(out)
