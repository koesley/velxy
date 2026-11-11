"""VELXTRIA V60: six real, tenant-scoped business tools.

No network crawling, LLM calls, autonomous outbound actions or speculative claims.
All calculations are deterministic, records persist in PostgreSQL, and actions are manual.
"""
import html
import json
import secrets
import time
from decimal import Decimal, InvalidOperation

KINDS=("opportunity","knowledge","scenario","command","portal","decision")
LABELS={"opportunity":"Opportunity Radar","knowledge":"Business Brain","scenario":"Business Digital Twin","command":"Natural Language Command Center","portal":"Client Portal Generator","decision":"Decision Intelligence"}
def e(v):return html.escape(str(v),quote=True)
def check(c,u,w):
    if not w or not c.execute("SELECT 1 FROM empire_members WHERE workspace_id=? AND user_id=?",(w,u)).fetchone():
        raise ValueError("Workspace access denied")
def money(v):
    try: d=Decimal(str(v))
    except (InvalidOperation,ValueError):raise ValueError("Enter a valid amount")
    if not d.is_finite() or d<0 or d>1000000000:raise ValueError("Amount out of range")
    return int(d*100)
def save(c,w,kind,title,data):
    c.execute("INSERT INTO v60_records(id,workspace,kind,title,payload,created) VALUES (?,?,?,?,?,?)",
              (secrets.token_hex(16),w,kind,title,json.dumps(data,ensure_ascii=True),int(time.time())))
def get(c,w,kind,limit=25):
    return c.execute("SELECT id,title,payload,created FROM v60_records WHERE workspace=? AND kind=? ORDER BY created DESC LIMIT ?",(w,kind,limit)).fetchall()
def insights(c,w):
    contacts=c.execute("SELECT COUNT(*) FROM v59_contacts WHERE workspace=?",(w,)).fetchone()[0]
    open_deals=c.execute("SELECT COUNT(*),COALESCE(SUM(cents),0) FROM v59_deals WHERE workspace=? AND stage NOT IN ('won','lost')",(w,)).fetchone()
    won=c.execute("SELECT COALESCE(SUM(cents),0) FROM v59_deals WHERE workspace=? AND stage='won'",(w,)).fetchone()[0]
    findings=[]
    if not contacts:findings.append(("Create a customer contact list","No contacts are recorded in the CRM.","Add a contact in Smart CRM."))
    if contacts and not open_deals[0]:findings.append(("Build a sales pipeline","Contacts exist but no open deals are recorded.","Create a deal linked to a contact."))
    if open_deals[0]:findings.append(("Review open pipeline",f"{open_deals[0]} open deals totaling ${open_deals[1]/100:,.2f}.","Review deal stages and next steps."))
    audits=c.execute("SELECT findings FROM v59_audits WHERE workspace=? ORDER BY created DESC LIMIT 1",(w,)).fetchone()
    if audits:
        try: issues=json.loads(audits[0]).get("findings",[])
        except (ValueError,TypeError):issues=[]
        if issues:findings.append(("Improve supplied website HTML","; ".join(str(x) for x in issues[:3]),"Review audit findings and update page markup."))
    return {"contacts":contacts,"open_deals":open_deals[0],"pipeline_cents":open_deals[1],"won_cents":won,"opportunities":findings}
def command(c,w,question):
    q=" ".join(question.lower().split())
    stats=insights(c,w)
    if q in ("contacts","show contacts","how many contacts","count contacts"):
        return f"{stats['contacts']} CRM contacts."
    if q in ("pipeline","show pipeline","open deals","show open deals"):
        return f"{stats['open_deals']} open deals, total ${stats['pipeline_cents']/100:,.2f}."
    if q in ("revenue","won revenue","won deals"):
        return f"Recorded won deal value: ${stats['won_cents']/100:,.2f}. Not verified revenue."
    if q in ("opportunities","show opportunities"):
        return "; ".join(x[0] for x in stats["opportunities"]) or "No rule-based opportunities found."
    return "Unsupported request. Try: contacts, pipeline, revenue, opportunities."
def act(c,u,w,f):
    check(c,u,w)
    kind=f.get("kind","")
    if kind not in KINDS:raise ValueError("Unknown tool")
    title=str(f.get("title","")).strip()[:120]
    if kind=="opportunity":
        result=insights(c,w)
        save(c,w,kind,"CRM opportunity scan",result)
    elif kind=="knowledge":
        body=str(f.get("body","")).strip()
        if not 1<=len(title)<=120 or not 1<=len(body)<=10000:raise ValueError("Title and note required (max 10,000 characters)")
        save(c,w,kind,title,{"note":body,"source":"User-entered"})
    elif kind=="scenario":
        base=money(f.get("base",""));change=str(f.get("change","")).strip()
        try: pct=Decimal(change)
        except (InvalidOperation,ValueError):raise ValueError("Invalid percentage")
        if not pct.is_finite() or abs(pct)>1000:raise ValueError("Percentage outside allowed range")
        projected=int(Decimal(base)*(1+pct/100))
        save(c,w,kind,title or "Revenue scenario",{"base_cents":base,"change_percent":str(pct),"projected_cents":projected,"note":"Illustrative arithmetic only; not a forecast."})
    elif kind=="command":
        q=str(f.get("question","")).strip()[:300]
        if not q:raise ValueError("Enter a command")
        save(c,w,kind,q,{"answer":command(c,w,q),"scope":"Read-only CRM summary"})
    elif kind=="portal":
        name=title
        intro=str(f.get("body","")).strip()
        if not name or len(intro)>2000:raise ValueError("Portal name required; introduction max 2000 characters")
        save(c,w,kind,name,{"intro":intro,"status":"Draft","public":False,"note":"Internal preview only; no customer access or public URL."})
    elif kind=="decision":
        options=[str(f.get(k,"")).strip() for k in ("option_a","option_b")]
        if not all(options) or any(len(x)>200 for x in options):raise ValueError("Two options required")
        try:score_a=int(f.get("score_a",""));score_b=int(f.get("score_b",""))
        except (ValueError,TypeError):raise ValueError("Scores must be integers")
        if not all(0<=v<=10 for v in (score_a,score_b)):raise ValueError("Scores must be 0–10")
        save(c,w,kind,title or "Decision comparison",{"option_a":options[0],"option_b":options[1],"score_a":score_a,"score_b":score_b,"preferred":options[0] if score_a>score_b else options[1] if score_b>score_a else "Tie","note":"User-entered scores, not an AI recommendation."})
def render(c,u,w,csrf):
    check(c,u,w)
    hidden=f'<input type="hidden" name="csrf" value="{e(csrf)}"><input type="hidden" name="workspace" value="{e(w)}">'
    def form(kind,fields):
        return f'<form method="post" action="/intelligence-v60">{hidden}<input type="hidden" name="kind" value="{kind}">{fields}<button>Save / Run</button></form>'
    out=['<section class="hero"><h1>VELXTRIA V60 · Business Intelligence</h1><p>Six tenant-scoped tools with saved results. All actions are manual; simulations are illustrative.</p></section>']
    forms={
      "opportunity":form("opportunity","<p>Scan existing CRM deals and supplied HTML audit findings.</p>"),
      "knowledge":form("knowledge",'<label>Title<input name="title" maxlength="120" required></label><label>Knowledge note<textarea name="body" maxlength="10000" required></textarea></label>'),
      "scenario":form("scenario",'<label>Scenario name<input name="title" maxlength="120"></label><label>Starting amount ($)<input name="base" type="number" step=".01" min="0" required></label><label>Change (%)<input name="change" type="number" step=".01" min="-100" max="1000" required></label>'),
      "command":form("command",'<label>Read-only command<input name="question" placeholder="contacts, pipeline, revenue, opportunities" maxlength="300" required></label>'),
      "portal":form("portal",'<label>Portal name<input name="title" maxlength="120" required></label><label>Welcome message<textarea name="body" maxlength="2000"></textarea></label><p>Creates an internal draft, not a public customer portal.</p>'),
      "decision":form("decision",'<label>Decision title<input name="title" maxlength="120"></label><label>Option A<input name="option_a" maxlength="200" required></label><label>Option A score (0–10)<input name="score_a" type="number" min="0" max="10" required></label><label>Option B<input name="option_b" maxlength="200" required></label><label>Option B score (0–10)<input name="score_b" type="number" min="0" max="10" required></label>')
    }
    for kind in KINDS:
        out.append(f'<section class="panel"><h2>{LABELS[kind]}</h2>{forms[kind]}')
        for _,title,payload,_ in get(c,w,kind):
            try: data=json.loads(payload)
            except (ValueError,TypeError):data={"error":"Invalid saved record"}
            if kind=="knowledge":detail=data.get("note","")
            elif kind=="command":detail=data.get("answer","")
            elif kind=="portal":detail=f"Internal draft: {data.get('intro','')}"
            elif kind=="opportunity":detail="; ".join(x[0]+": "+x[1] for x in data.get("opportunities",[])) or "No rule-based opportunities"
            elif kind=="scenario":detail=f"Projected value: ${data.get('projected_cents',0)/100:,.2f} (illustrative)"
            else:detail=f"Preference based on supplied scores: {data.get('preferred','')}"
            out.append(f'<p><strong>{e(title)}</strong> — {e(detail)}</p>')
        out.append("</section>")
    return "".join(out)
