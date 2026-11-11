"""V59 Ascension: tenant-scoped PostgreSQL business suite (manual, deterministic)."""
import html, json, re, secrets, time
from html.parser import HTMLParser
AGENTS={"sales":"Sales Intelligence","website":"Website Optimization","revenue":"Revenue Analyst","operations":"Customer Operations"}
STAGES=("lead","contacted","qualified","proposal","won","lost")
def esc(x): return html.escape(str(x),quote=True)
def authorize(c,u,w):
    if not w or not c.execute("SELECT 1 FROM empire_members WHERE workspace_id=? AND user_id=?",(w,u)).fetchone(): raise ValueError("Workspace access denied")
def analyze(raw):
    if len(raw)>250000: raise ValueError("HTML exceeds 250 KB")
    class Parser(HTMLParser):
        def __init__(self): super().__init__();self.title=False;self.titles=[];self.h1=0;self.description=0;self.missing_alt=0
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if tag=="title":self.title=True
            if tag=="h1":self.h1+=1
            if tag=="meta" and a.get("name","").lower()=="description" and a.get("content","").strip():self.description+=1
            if tag=="img" and not a.get("alt","").strip():self.missing_alt+=1
        def handle_endtag(self,tag):
            if tag=="title":self.title=False
        def handle_data(self,data):
            if self.title:self.titles.append(data)
    p=Parser();p.feed(raw)
    return {"findings":([ "Missing document title" ] if not "".join(p.titles).strip() else [])+ (["Missing meta description"] if not p.description else [])+(["Missing H1"] if not p.h1 else [])+([f"{p.missing_alt} images without alt text"] if p.missing_alt else []),"scope":"Supplied HTML only; no live crawl or AI"}
def act(c,u,w,f):
    authorize(c,u,w);a=f.get("action","");now=int(time.time());new=lambda:secrets.token_hex(16)
    if a=="contact":
        name=f.get("name","").strip();email=f.get("email","").strip()
        if not 1<=len(name)<=120 or len(email)>254 or (email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email)):raise ValueError("Invalid contact")
        c.execute("INSERT INTO v59_contacts VALUES (?,?,?,?,?)",(new(),w,name,email,now))
    elif a=="deal":
        contact=f.get("contact","");title=f.get("title","").strip()
        if not c.execute("SELECT 1 FROM v59_contacts WHERE workspace=? AND id=?",(w,contact)).fetchone():raise ValueError("Contact not found")
        try:cents=int(f.get("cents",""))
        except (TypeError,ValueError):raise ValueError("Invalid amount")
        if not 1<=len(title)<=120 or not 0<=cents<=10**12:raise ValueError("Invalid deal")
        c.execute("INSERT INTO v59_deals VALUES (?,?,?,?,?,?,?)",(new(),w,contact,title,cents,"lead",now))
    elif a=="stage":
        if f.get("stage") not in STAGES:raise ValueError("Invalid stage")
        c.execute("UPDATE v59_deals SET stage=? WHERE workspace=? AND id=?",(f["stage"],w,f.get("id","")))
    elif a=="audit":
        url=f.get("url","").strip();raw=f.get("html","")
        if not url.startswith(("https://","http://")) or len(url)>300:raise ValueError("Invalid URL label")
        c.execute("INSERT INTO v59_audits VALUES (?,?,?,?,?)",(new(),w,url,json.dumps(analyze(raw)),now))
    elif a=="workflow":
        name=f.get("name","").strip()
        if not 1<=len(name)<=100:raise ValueError("Invalid name")
        c.execute("INSERT INTO v59_workflows VALUES (?,?,?,?,?,?)",(new(),w,name,"manual","crm_summary",0))
    elif a=="workflow_toggle":
        c.execute("UPDATE v59_workflows SET enabled=1-enabled WHERE workspace=? AND id=?",(w,f.get("id","")))
    elif a=="workflow_run":
        wid=f.get("id","")
        if not c.execute("SELECT 1 FROM v59_workflows WHERE workspace=? AND id=? AND enabled=1",(w,wid)).fetchone():raise ValueError("Workflow not enabled")
        count=c.execute("SELECT COUNT(*) FROM v59_contacts WHERE workspace=?",(w,)).fetchone()[0]
        c.execute("INSERT INTO v59_runs VALUES (?,?,?,?,?,?)",(new(),w,wid,"completed",f"CRM summary: {count} contacts; no external actions",now))
    elif a=="agent_install":
        k=f.get("agent","")
        if k not in AGENTS:raise ValueError("Unknown agent")
        c.execute("INSERT INTO v59_agents VALUES (?,?,1) ON CONFLICT(workspace,kind) DO UPDATE SET installed=1",(w,k))
    elif a=="agent_uninstall":
        c.execute("UPDATE v59_agents SET installed=0 WHERE workspace=? AND kind=?",(w,f.get("agent","")))
    elif a=="agent_run":
        k=f.get("agent","")
        if k not in AGENTS or not c.execute("SELECT 1 FROM v59_agents WHERE workspace=? AND kind=? AND installed=1",(w,k)).fetchone():raise ValueError("Agent not installed")
        contacts=c.execute("SELECT COUNT(*) FROM v59_contacts WHERE workspace=?",(w,)).fetchone()[0]
        won=c.execute("SELECT COALESCE(SUM(cents),0) FROM v59_deals WHERE workspace=? AND stage='won'",(w,)).fetchone()[0]
        report=f"{AGENTS[k]} deterministic analysis: {contacts} contacts; won deal value ${won/100:,.2f}. No external AI used."
        c.execute("INSERT INTO v59_agent_runs VALUES (?,?,?,?,?)",(new(),w,k,report,now))
    else:raise ValueError("Unknown action")
def render(c,u,w,csrf):
    authorize(c,u,w)
    def rows(sql,args):return c.execute(sql,args).fetchall()
    contacts=rows("SELECT id,name,email FROM v59_contacts WHERE workspace=? ORDER BY created DESC LIMIT 50",(w,))
    deals=rows("SELECT id,title,cents,stage FROM v59_deals WHERE workspace=? ORDER BY created DESC LIMIT 50",(w,))
    audits=rows("SELECT url,findings FROM v59_audits WHERE workspace=? ORDER BY created DESC LIMIT 10",(w,))
    workflows=rows("SELECT id,name,enabled FROM v59_workflows WHERE workspace=?",(w,))
    installed={x[0] for x in rows("SELECT kind FROM v59_agents WHERE workspace=? AND installed=1",(w,))}
    won=c.execute("SELECT COALESCE(SUM(cents),0) FROM v59_deals WHERE workspace=? AND stage='won'",(w,)).fetchone()[0]
    pipeline=c.execute("SELECT COALESCE(SUM(cents),0) FROM v59_deals WHERE workspace=? AND stage NOT IN ('won','lost')",(w,)).fetchone()[0]
    hidden=f'<input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="workspace" value="{esc(w)}">'
    def form(x):return '<form method="post" action="/ascension-v59">'+hidden+x+'</form>'
    out=['<section class="hero"><h1>VELXTRIA V59 · Ascension</h1><p>Real workspace records, HTML inspection, CRM metrics, manual workflows and deterministic agents. No autonomous AI or live crawling.</p></section>']
    out.append(f'<section class="panel"><h2>Revenue Intelligence</h2><p>Won deal value: ${won/100:,.2f} · Open pipeline: ${pipeline/100:,.2f}</p><small>CRM deal values, not verified cash receipts.</small></section>')
    out.append('<section class="panel"><h2>Smart CRM</h2>'+form('<input type="hidden" name="action" value="contact"><label>Contact name<input name="name" required maxlength="120"></label><label>Email<input name="email" type="email"></label><button>Add contact</button>'))
    options="".join(f'<option value="{esc(i)}">{esc(n)}</option>' for i,n,_ in contacts)
    out.append(form('<input type="hidden" name="action" value="deal"><label>Contact<select name="contact">'+options+'</select></label><label>Deal title<input name="title" maxlength="120" required></label><label>Value (cents)<input type="number" name="cents" min="0" max="1000000000000" required></label><button>Add deal</button>'))
    for i,name,email in contacts:out.append(f'<p>{esc(name)} · {esc(email)}</p>')
    for i,title,cents,stage in deals:
        options="".join(f'<option value="{s}" {"selected" if s==stage else ""}>{s}</option>' for s in STAGES)
        out.append(f'<p>{esc(title)} · ${cents/100:,.2f} '+form(f'<input type="hidden" name="action" value="stage"><input type="hidden" name="id" value="{esc(i)}"><select name="stage">{options}</select><button>Update</button>')+'</p>')
    out.append('</section><section class="panel"><h2>Website Auditor · Supplied HTML</h2>'+form('<input type="hidden" name="action" value="audit"><label>Page URL (label)<input name="url" type="url" required></label><label>HTML<textarea name="html" maxlength="250000" required></textarea></label><button>Analyze</button>'))
    for url,raw in audits:out.append(f'<p>{esc(url)}: {esc("; ".join(json.loads(raw)["findings"]) or "No supported issues found")}</p>')
    out.append('</section><section class="panel"><h2>Automation Architect · Manual</h2>'+form('<input type="hidden" name="action" value="workflow"><input name="name" maxlength="100" required><button>Create workflow</button>'))
    for i,name,enabled in workflows:
        out.append('<p>'+esc(name)+' · '+('Enabled' if enabled else 'Disabled')+' '+form(f'<input type="hidden" name="action" value="workflow_toggle"><input type="hidden" name="id" value="{esc(i)}"><button>Toggle</button>')+(form(f'<input type="hidden" name="action" value="workflow_run"><input type="hidden" name="id" value="{esc(i)}"><button>Run</button>') if enabled else '')+'</p>')
    for status,details in rows("SELECT status,details FROM v59_runs WHERE workspace=? ORDER BY created DESC LIMIT 10",(w,)):out.append(f'<p>{esc(status)} · {esc(details)}</p>')
    out.append('</section><section class="panel"><h2>Agent Marketplace & Workforce</h2><p>First-party deterministic agents only.</p>')
    for k,name in AGENTS.items():
        installed_now=k in installed
        out.append('<p>'+esc(name)+' '+form(f'<input type="hidden" name="action" value="{"agent_uninstall" if installed_now else "agent_install"}"><input type="hidden" name="agent" value="{k}"><button>{"Uninstall" if installed_now else "Install"}</button>')+(form(f'<input type="hidden" name="action" value="agent_run"><input type="hidden" name="agent" value="{k}"><button>Run analysis</button>') if installed_now else '')+'</p>')
    for (report,) in rows("SELECT report FROM v59_agent_runs WHERE workspace=? ORDER BY created DESC LIMIT 10",(w,)):out.append('<p>'+esc(report)+'</p>')
    out.append('</section>')
    return "".join(out)
