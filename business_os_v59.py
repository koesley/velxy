"""VELXTRIA Business OS: scoped, approval-first revenue recovery and command metrics.

No outbound messages, autonomous spending, or unsupported revenue claims.
"""
import csv
import datetime
import html
import io
import secrets
import time
import urllib.parse
import sovereign_v56 as core

STATES = ("new", "contacted", "won", "lost")
DECISIONS = ("pending", "approved", "rejected")

def init(c):
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_leads (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL,
        contact TEXT NOT NULL, source TEXT NOT NULL, value REAL NOT NULL,
        status TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_actions (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
        message TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL,
        created_by INTEGER NOT NULL, reviewed_by INTEGER, created INTEGER NOT NULL,
        reviewed INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_lead_notes (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
        author_id INTEGER NOT NULL, body TEXT NOT NULL, created INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_tasks (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
        title TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL,
        created_by INTEGER NOT NULL, created INTEGER NOT NULL, completed INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_quotes (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
        description TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL,
        status TEXT NOT NULL, created_by INTEGER NOT NULL, created INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bos59_services (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL,
        description TEXT NOT NULL, unit_price REAL NOT NULL, active INTEGER NOT NULL,
        created INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_services_scope ON bos59_services(workspace_id,active)")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_quotes_lead ON bos59_quotes(workspace_id,lead_id,created)")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_tasks_due ON bos59_tasks(workspace_id,status,due_date)")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_notes_lead ON bos59_lead_notes(workspace_id,lead_id,created)")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_leads_scope ON bos59_leads(workspace_id,status)")
    c.execute("CREATE INDEX IF NOT EXISTS bos59_actions_scope ON bos59_actions(workspace_id,decision)")

def _text(value, limit):
    if not isinstance(value,str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError("Invalid text field")
    return value.strip()

def add_lead(c, uid, wid, name, contact, source, value):
    core.access(c,uid,wid,write=True)
    init(c)
    name,contact,source=(_text(name,120),_text(contact,200),_text(source,100))
    try:
        amount=float(value)
    except (TypeError,ValueError,OverflowError):
        raise ValueError("Invalid value")
    import math
    if not math.isfinite(amount) or amount < 0 or amount > 1000000000:
        raise ValueError("Invalid value")
    lid=secrets.token_hex(12)
    if True:
        c.execute("INSERT INTO bos59_leads VALUES(?,?,?,?,?,?,?,?,?)",
                  (lid,wid,name,contact,source,amount,"new",int(time.time()),int(time.time())))
        core.audit(c,uid,wid,"bos_lead_created",lid)
    return lid

def import_leads_csv(c,uid,wid,csv_text):
    """Import up to 100 leads from pasted CSV with strict validation and deduplication."""
    core.access(c,uid,wid,write=True)
    init(c)
    if not isinstance(csv_text,str) or not csv_text.strip() or len(csv_text)>40000:
        raise ValueError("CSV must contain 1–40000 characters")
    try:
        reader=csv.DictReader(io.StringIO(csv_text,newline=""))
        required={"name","contact","source","value"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV headers must include name,contact,source,value")
        if len(reader.fieldnames)>12 or any(not h or len(h)>80 for h in reader.fieldnames):
            raise ValueError("Invalid CSV headers")
        parsed=[]
        import math
        for row in reader:
            if len(parsed)>=100:
                raise ValueError("Maximum 100 leads per import")
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV row")
            name=_text(row["name"],120)
            contact=_text(row["contact"],200)
            source=_text(row["source"],100)
            try:
                value=float(row["value"])
            except (ValueError,TypeError,OverflowError):
                raise ValueError("Invalid lead value")
            if not math.isfinite(value) or not 0<=value<=1000000000:
                raise ValueError("Invalid lead value")
            parsed.append((name,contact,source,value))
    except csv.Error:
        raise ValueError("Invalid CSV formatting")
    if not parsed:
        raise ValueError("No leads found in CSV")
    existing={(str(name).casefold(),str(contact).casefold()) for name,contact in c.execute(
        "SELECT name,contact FROM bos59_leads WHERE workspace_id=?",(wid,))}
    seen=set()
    unique=[]
    for name,contact,source,value in parsed:
        key=(name.casefold(),contact.casefold())
        if key in existing or key in seen:
            continue
        seen.add(key)
        unique.append((name,contact,source,value))
    now=int(time.time())
    for name,contact,source,value in unique:
        c.execute("INSERT INTO bos59_leads VALUES(?,?,?,?,?,?,?,?,?)",
                  (secrets.token_hex(12),wid,name,contact,source,value,"new",now,now))
    core.audit(c,uid,wid,"bos_leads_csv_imported",str(len(unique)))
    return {"imported":len(unique),"duplicates_skipped":len(parsed)-len(unique)}

def edit_lead(c,uid,wid,lid,name,contact,source,value):
    """Update customer details without replacing its notes, tasks, or quotes."""
    core.access(c,uid,wid,write=True)
    init(c)
    name,contact,source=(_text(name,120),_text(contact,200),_text(source,100))
    import math
    try:
        amount=float(value)
    except (TypeError,ValueError,OverflowError):
        raise ValueError("Invalid value")
    if not math.isfinite(amount) or not 0<=amount<=1000000000:
        raise ValueError("Invalid value")
    row=c.execute("SELECT 1 FROM bos59_leads WHERE id=? AND workspace_id=?",(lid,wid)).fetchone()
    if not row:
        raise ValueError("Lead not found")
    duplicate=c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND id<>? AND lower(name)=lower(?) AND lower(contact)=lower(?)",(wid,lid,name,contact)).fetchone()
    if duplicate:
        raise ValueError("Another customer already has this name and contact")
    c.execute("UPDATE bos59_leads SET name=?,contact=?,source=?,value=?,updated=? WHERE workspace_id=? AND id=?",
              (name,contact,source,amount,int(time.time()),wid,lid))
    core.audit(c,uid,wid,"bos_lead_edited",lid)

def update_lead(c,uid,wid,lid,status):
    core.access(c,uid,wid,write=True)
    init(c)
    if status not in STATES:
        raise ValueError("Invalid lead status")
    if True:
        row=c.execute("SELECT status FROM bos59_leads WHERE id=? AND workspace_id=?",(lid,wid)).fetchone()
        if not row:
            raise ValueError("Lead not found")
        c.execute("UPDATE bos59_leads SET status=?,updated=? WHERE id=? AND workspace_id=?",
                  (status,int(time.time()),lid,wid))
        core.audit(c,uid,wid,"bos_lead_status",lid+":"+status)

def propose(c,uid,wid,lid,message):
    core.access(c,uid,wid,write=True)
    init(c)
    message=_text(message,2000)
    if not c.execute("SELECT 1 FROM bos59_leads WHERE id=? AND workspace_id=?",(lid,wid)).fetchone():
        raise ValueError("Lead not found")
    aid=secrets.token_hex(12)
    if True:
        c.execute("INSERT INTO bos59_actions VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (aid,wid,lid,message,"pending","",uid,None,int(time.time()),None))
        core.audit(c,uid,wid,"bos_message_proposed",aid)
    return aid

def review(c,uid,wid,aid,decision,reason):
    core.access(c,uid,wid,write=True,owner=True)
    init(c)
    if decision not in ("approved","rejected"):
        raise ValueError("Invalid decision")
    reason=_text(reason,500)
    if True:
        row=c.execute("SELECT decision FROM bos59_actions WHERE id=? AND workspace_id=?",(aid,wid)).fetchone()
        if not row or row[0] != "pending":
            raise ValueError("Action not pending")
        c.execute("UPDATE bos59_actions SET decision=?,reason=?,reviewed_by=?,reviewed=? WHERE id=? AND workspace_id=?",
                  (decision,reason,uid,int(time.time()),aid,wid))
        core.audit(c,uid,wid,"bos_message_"+decision,aid)

def add_note(c,uid,wid,lid,body):
    """Persist a dated internal note on an existing lead; no external messaging."""
    core.access(c,uid,wid,write=True)
    init(c)
    body=_text(body,2000)
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND id=?",(wid,lid)).fetchone():
        raise ValueError("Lead not found")
    nid=secrets.token_hex(12)
    c.execute("INSERT INTO bos59_lead_notes(id,workspace_id,lead_id,author_id,body,created) VALUES(?,?,?,?,?,?)",
              (nid,wid,lid,uid,body,int(time.time())))
    core.audit(c,uid,wid,"bos_lead_note_created",lid)
    return nid

def add_task(c,uid,wid,lid,title,due_date):
    core.access(c,uid,wid,write=True)
    init(c)
    title=_text(title,160)
    try:
        parsed=datetime.date.fromisoformat(due_date)
        if parsed.isoformat()!=due_date:
            raise ValueError("Invalid due date")
    except (TypeError,ValueError):
        raise ValueError("Use a valid due date (YYYY-MM-DD)")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND id=?",(wid,lid)).fetchone():
        raise ValueError("Lead not found")
    tid=secrets.token_hex(12)
    c.execute("INSERT INTO bos59_tasks VALUES(?,?,?,?,?,?,?,?,?)",
              (tid,wid,lid,title,due_date,"open",uid,int(time.time()),None))
    core.audit(c,uid,wid,"bos_task_created",tid)
    return tid

def complete_task(c,uid,wid,tid):
    core.access(c,uid,wid,write=True)
    init(c)
    row=c.execute("SELECT lead_id FROM bos59_tasks WHERE workspace_id=? AND id=? AND status='open'",(wid,tid)).fetchone()
    if not row:
        raise ValueError("Open task not found")
    c.execute("UPDATE bos59_tasks SET status='done',completed=? WHERE workspace_id=? AND id=? AND status='open'",
              (int(time.time()),wid,tid))
    core.audit(c,uid,wid,"bos_task_completed",tid)

def create_quote(c,uid,wid,lid,description,quantity,unit_price):
    """Create a draft estimate. No invoice, charge or outbound delivery."""
    core.access(c,uid,wid,write=True)
    init(c)
    description=_text(description,300)
    try:
        qty=int(quantity)
        price=float(unit_price)
    except (TypeError,ValueError,OverflowError):
        raise ValueError("Invalid quote quantity or price")
    import math
    if not 1<=qty<=100000 or not math.isfinite(price) or not 0<=price<=1000000 or qty*price>1000000000:
        raise ValueError("Quote exceeds allowed limits")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND id=?",(wid,lid)).fetchone():
        raise ValueError("Lead not found")
    qid=secrets.token_hex(12)
    c.execute("INSERT INTO bos59_quotes VALUES(?,?,?,?,?,?,?,?,?)",
              (qid,wid,lid,description,qty,round(price,2),"draft",uid,int(time.time())))
    core.audit(c,uid,wid,"bos_quote_created",qid)
    return qid

def add_service(c,uid,wid,name,description,unit_price):
    """Store a reusable price-list entry for the workspace."""
    core.access(c,uid,wid,write=True)
    init(c)
    name=_text(name,120)
    description=_text(description,300)
    try:
        price=float(unit_price)
    except (ValueError,TypeError,OverflowError):
        raise ValueError("Invalid price")
    import math
    if not math.isfinite(price) or not 0<=price<=1000000:
        raise ValueError("Invalid price")
    sid=secrets.token_hex(12)
    c.execute("INSERT INTO bos59_services VALUES(?,?,?,?,?,?,?)",
              (sid,wid,name,description,round(price,2),1,int(time.time())))
    core.audit(c,uid,wid,"bos_service_created",sid)
    return sid

def archive_service(c,uid,wid,sid):
    core.access(c,uid,wid,write=True)
    init(c)
    result=c.execute("UPDATE bos59_services SET active=0 WHERE workspace_id=? AND id=? AND active=1",(wid,sid))
    if not result.rowcount:
        raise ValueError("Active service not found")
    core.audit(c,uid,wid,"bos_service_archived",sid)

def quote_from_service(c,uid,wid,lid,sid,quantity):
    core.access(c,uid,wid,write=True)
    init(c)
    row=c.execute("SELECT description,unit_price FROM bos59_services WHERE workspace_id=? AND id=? AND active=1",(wid,sid)).fetchone()
    if not row:
        raise ValueError("Active service not found")
    return create_quote(c,uid,wid,lid,row[0],quantity,row[1])

QUOTE_STATES=("draft","presented","accepted","declined")

def update_quote(c,uid,wid,qid,new_status):
    """Record manually verified quote progress; never send or charge customers."""
    core.access(c,uid,wid,write=True)
    init(c)
    if new_status not in QUOTE_STATES:
        raise ValueError("Invalid quote status")
    row=c.execute("SELECT lead_id,status FROM bos59_quotes WHERE id=? AND workspace_id=?",(qid,wid)).fetchone()
    if not row:
        raise ValueError("Quote not found")
    lid,old_status=row
    transitions={"draft":("presented","declined"),"presented":("accepted","declined"),
                 "accepted":(),"declined":()}
    if new_status not in transitions.get(old_status,()):
        raise ValueError("Quote status transition not allowed")
    c.execute("UPDATE bos59_quotes SET status=? WHERE id=? AND workspace_id=?",(new_status,qid,wid))
    core.audit(c,uid,wid,"bos_quote_"+new_status,qid)
    if new_status=="accepted":
        existing=c.execute("SELECT 1 FROM bos59_tasks WHERE workspace_id=? AND lead_id=? AND title=? AND status='open'",
                           (wid,lid,"Fulfill accepted quote "+qid[:8])).fetchone()
        if not existing:
            now=int(time.time())
            due=(datetime.date.today()+datetime.timedelta(days=1)).isoformat()
            c.execute("INSERT INTO bos59_tasks VALUES(?,?,?,?,?,?,?,?,?)",
                      (secrets.token_hex(12),wid,lid,"Fulfill accepted quote "+qid[:8],due,"open",uid,now,None))
            core.audit(c,uid,wid,"bos_quote_fulfillment_task_created",qid)
    return new_status

def quote_workflow_summary(c,uid,wid):
    core.access(c,uid,wid)
    init(c)
    rows=c.execute("SELECT status,quantity,unit_price FROM bos59_quotes WHERE workspace_id=? ORDER BY created DESC LIMIT 500",(wid,)).fetchall()
    totals={state:{"count":0,"value":0.0} for state in QUOTE_STATES}
    for status,qty,price in rows:
        if status in totals:
            totals[status]["count"]+=1
            totals[status]["value"]+=qty*price
    for entry in totals.values():
        entry["value"]=round(entry["value"],2)
    return totals

def overview(c,uid,wid):
    role=core.access(c,uid,wid)
    init(c)
    leads=[dict(zip(("id","name","contact","source","value","status","created","updated"),
                    row)) for row in c.execute("SELECT id,name,contact,source,value,status,created,updated FROM bos59_leads WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 300",(wid,))]
    actions=[dict(zip(("id","lead_id","message","decision","reason","created"),
                      row)) for row in c.execute("SELECT id,lead_id,message,decision,reason,created FROM bos59_actions WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 300",(wid,))]
    return {"role":role,"workspace_id":wid,"leads":leads,"actions":actions,
            "metrics":{"leads":len(leads),"open_pipeline":round(sum(x["value"] for x in leads if x["status"] in ("new","contacted")),2),
                       "won_reported":round(sum(x["value"] for x in leads if x["status"]=="won"),2),
                       "pending_approvals":sum(x["decision"]=="pending" for x in actions)},
            "limitations":["Values are user-entered, not verified transactions.",
                           "Won status does not prove collected revenue.",
                           "Approving a draft never sends it externally.",
                           "Only the latest 300 records are shown."]}

def pipeline_insights(c, uid, wid):
    """New: conversion and lead-priority insights from existing workspace records."""
    core.access(c, uid, wid)
    init(c)
    rows=c.execute("SELECT id,name,value,status,created,updated FROM bos59_leads WHERE workspace_id=? ORDER BY created DESC LIMIT 300",(wid,)).fetchall()
    counts={state:0 for state in STATES}
    values={state:0.0 for state in STATES}
    stale=[]
    current=int(time.time())
    for lid,name,value,status,created,updated in rows:
        if status not in counts:
            continue
        counts[status]+=1
        values[status]+=float(value)
        if status in ("new","contacted") and current-int(updated)>=7*86400:
            stale.append({"id":lid,"name":name,"value":float(value),"days":max(0,(current-int(updated))//86400)})
    stale.sort(key=lambda x:(-x["value"],-x["days"],x["name"]))
    closed=counts["won"]+counts["lost"]
    return {"counts":counts,"values":values,"closed_conversion_pct":round(100*counts["won"]/closed,1) if closed else None,
            "stale":stale[:10],"stale_count":len(stale),"sample_limit":300}

def source_performance(c, uid, wid):
    """Compare lead sources without treating pipeline values as collected revenue."""
    core.access(c,uid,wid)
    init(c)
    rows=c.execute("SELECT source,status,value FROM bos59_leads WHERE workspace_id=? ORDER BY created DESC LIMIT 300",(wid,)).fetchall()
    groups={}
    for source,status,value in rows:
        key=(source or "Unknown").strip()[:100] or "Unknown"
        item=groups.setdefault(key,{"source":key,"leads":0,"won":0,"lost":0,"open_value":0.0})
        item["leads"]+=1
        if status=="won": item["won"]+=1
        elif status=="lost": item["lost"]+=1
        elif status in ("new","contacted"): item["open_value"]+=float(value)
    for item in groups.values():
        closed=item["won"]+item["lost"]
        item["win_rate"]=round(item["won"]*100/closed,1) if closed else None
        item["open_value"]=round(item["open_value"],2)
    return sorted(groups.values(),key=lambda x:(-x["won"],-x["leads"],x["source"].lower()))[:12]

def pipeline_forecast(c,uid,wid):
    """Scenario-based potential, not a revenue prediction or collected cash."""
    core.access(c,uid,wid)
    init(c)
    rows=c.execute("SELECT status,value FROM bos59_leads WHERE workspace_id=? ORDER BY created DESC LIMIT 300",(wid,)).fetchall()
    new_value=sum(float(v) for status,v in rows if status=="new")
    contacted_value=sum(float(v) for status,v in rows if status=="contacted")
    scenarios={"conservative":(0.05,0.15),"baseline":(0.15,0.35),"optimistic":(0.30,0.60)}
    return {"new_value":round(new_value,2),"contacted_value":round(contacted_value,2),
            "scenarios":{name:round(new_value*a+contacted_value*b,2) for name,(a,b) in scenarios.items()},
            "assumptions":scenarios,"sample_limit":300}

def followup_queue(c,uid,wid):
    """Actionable, human-controlled follow-up queue from existing lead records."""
    core.access(c,uid,wid)
    init(c)
    now=int(time.time())
    rows=c.execute("SELECT id,name,contact,source,value,status,updated FROM bos59_leads WHERE workspace_id=? AND status IN ('new','contacted') ORDER BY updated ASC LIMIT 300",(wid,)).fetchall()
    result=[]
    for lid,name,contact,source,value,status,updated in rows:
        age=max(0,(now-int(updated))//86400)
        if age<3:
            continue
        priority="High" if age>=14 else "Medium" if age>=7 else "Normal"
        result.append({"id":lid,"name":name,"contact":contact,"source":source,"value":float(value),"status":status,"days":age,"priority":priority})
    result.sort(key=lambda x:(-x["days"],-x["value"],x["name"].lower()))
    return result[:20]

def pipeline_velocity(c,uid,wid):
    """Lead aging and stage movement visibility using existing timestamps."""
    core.access(c,uid,wid)
    init(c)
    now=int(time.time())
    rows=c.execute("SELECT status,created,updated,value FROM bos59_leads WHERE workspace_id=? ORDER BY created DESC LIMIT 300",(wid,)).fetchall()
    buckets={"0-7 days":0,"8-30 days":0,"31-90 days":0,"90+ days":0}
    open_total=0
    open_days=0
    idle_value=0.0
    for status,created,updated,value in rows:
        if status not in ("new","contacted"):
            continue
        age=max(0,(now-int(created))//86400)
        idle=max(0,(now-int(updated))//86400)
        label="0-7 days" if age<=7 else "8-30 days" if age<=30 else "31-90 days" if age<=90 else "90+ days"
        buckets[label]+=1
        open_total+=1
        open_days+=age
        if idle>=14:
            idle_value+=float(value)
    return {"buckets":buckets,"average_open_age":round(open_days/open_total,1) if open_total else None,
            "idle_value":round(idle_value,2),"open_count":open_total}

def suggested_followup(name,status,days):
    """Create an editable, non-sending outreach draft from an existing lead."""
    first=(name.strip().split() or ["there"])[0]
    greeting="Hi "+first+","
    if status=="new":
        body="Thanks for your interest. I'd love to learn more about what your business needs and see whether we can help. Would a quick conversation this week work for you?"
    elif days>=14:
        body="I wanted to reconnect about our earlier conversation. If this is still a priority for you, I'd be happy to discuss the next steps. Would you like to find a time to talk?"
    else:
        body="Following up on our conversation. Do you have any questions I can help answer, or would you like to discuss the next steps?"
    return greeting+"\\n\\n"+body+"\\n\\nBest regards"

def export_csv(c,uid,wid):
    data=overview(c,uid,wid)
    f=io.StringIO()
    w=csv.writer(f)
    w.writerow(["id","name","contact","source","value","status","created"])
    for x in data["leads"]:
        w.writerow([x[k] for k in ("id","name","contact","source","value","status","created")])
    return f.getvalue()

def render(c,uid,wid,csrf):
    d=overview(c,uid,wid)
    h=lambda x:html.escape(str(x),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    url="/business-os-v59"
    out=['<section class="ov-hero"><span>VELXTRIA · BUSINESS OS V59</span><h1>Revenue recovery command center</h1><p>Manage leads, prepare follow-ups and require human approval. No automatic messages are sent.</p></section>']
    out.append('<section class="ov-metrics">'+''.join('<article class="ov-card"><strong>'+h(k.replace("_"," ").title())+'</strong><span>'+h(v)+'</span></article>' for k,v in d["metrics"].items())+'</section>')
    insights=pipeline_insights(c,uid,wid)
    conversion=("Not enough closed leads" if insights["closed_conversion_pct"] is None else str(insights["closed_conversion_pct"])+"%")
    out.append('<section class="ov-panel"><h2>Pipeline intelligence</h2><p>New: see conversion and follow-up priorities from your existing leads.</p><div class="ov-metrics"><article class="ov-card"><strong>Closed-lead win rate</strong><span>'+h(conversion)+'</span></article><article class="ov-card"><strong>Needs follow-up (7+ days)</strong><span>'+h(insights["stale_count"])+'</span></article><article class="ov-card"><strong>Contacted pipeline</strong><span>'+h(round(insights["values"]["contacted"],2))+'</span></article></div>')
    if insights["stale"]:
        out.append('<h3>Follow-up priorities</h3><ol>'+''.join('<li><strong>'+h(x["name"])+'</strong> · potential '+h(round(x["value"],2))+' · '+h(x["days"])+' days since update</li>' for x in insights["stale"])+'</ol>')
    else:
        out.append('<p>No open leads overdue for follow-up in the displayed records.</p>')
    out.append('<small>Based on up to 300 user-entered leads. Win rate is won / (won + lost), not verified revenue. No messages are sent.</small></section>')
    sources=source_performance(c,uid,wid)
    out.append('<section class="ov-panel"><h2>Lead source performance</h2><p>New: compare which channels produce won leads and where open opportunities originate.</p>')
    if sources:
        out.append('<div class="scroll"><table><thead><tr><th>Source</th><th>Leads</th><th>Won</th><th>Win rate (closed)</th><th>Open potential</th></tr></thead><tbody>')
        for item in sources:
            rate="—" if item["win_rate"] is None else str(item["win_rate"])+"%"
            out.append('<tr><td>'+h(item["source"])+'</td><td>'+h(item["leads"])+'</td><td>'+h(item["won"])+'</td><td>'+h(rate)+'</td><td>'+h(item["open_value"])+'</td></tr>')
        out.append('</tbody></table></div>')
    else:
        out.append('<p>Add leads with a source to see comparisons here.</p>')
    out.append('<small>Shows up to 12 sources from the latest 300 leads. Values are user-entered estimates, not verified revenue.</small></section>')
    forecast=pipeline_forecast(c,uid,wid)
    out.append('<section class="ov-panel"><h2>Pipeline scenario planner</h2><p>New: explore what your current open leads could be worth under three hypothetical conversion assumptions.</p><div class="ov-metrics">')
    for scenario,amount in forecast["scenarios"].items():
        new_rate,contacted_rate=forecast["assumptions"][scenario]
        out.append('<article class="ov-card"><strong>'+h(scenario.title())+'</strong><span>'+h(amount)+'</span><small>New '+h(round(new_rate*100))+'% · Contacted '+h(round(contacted_rate*100))+'%</small></article>')
    out.append('</div><small>Illustrative scenarios only, not forecasts of actual sales or guaranteed income. Based on the latest 300 user-entered leads. No payments or messages are triggered.</small></section>')
    queue=followup_queue(c,uid,wid)
    out.append('<section class="ov-panel"><h2>Follow-up action queue</h2><p>New: a prioritized list of open leads that have not been updated for at least three days. Contact is always manual.</p>')
    if queue:
        out.append('<div class="scroll"><table><thead><tr><th>Priority</th><th>Lead</th><th>Contact</th><th>Days idle</th><th>Potential value</th></tr></thead><tbody>')
        for item in queue:
            out.append('<tr><td>'+h(item["priority"])+'</td><td>'+h(item["name"])+'</td><td>'+h(item["contact"])+'</td><td>'+h(item["days"])+'</td><td>'+h(round(item["value"],2))+'</td></tr>')
        out.append('</tbody></table></div>')
    else:
        out.append('<p>No leads currently need follow-up under the three-day rule.</p>')
    out.append('<small>Based on up to 300 open leads. High: 14+ days idle; Medium: 7–13; Normal: 3–6. No emails or calls are sent automatically.</small></section>')
    velocity=pipeline_velocity(c,uid,wid)
    out.append('<section class="ov-panel"><h2>Pipeline aging intelligence</h2><p>New: understand how long opportunities stay open and where deals may be stalling.</p><div class="ov-metrics"><article class="ov-card"><strong>Average open lead age</strong><span>'+h(str(velocity["average_open_age"])+" days" if velocity["average_open_age"] is not None else "No open leads")+'</span></article><article class="ov-card"><strong>Potential value idle 14+ days</strong><span>'+h(velocity["idle_value"])+'</span></article></div><div class="scroll"><table><thead><tr><th>Age of open lead</th><th>Count</th></tr></thead><tbody>')
    for bucket,count in velocity["buckets"].items():
        out.append('<tr><td>'+h(bucket)+'</td><td>'+h(count)+'</td></tr>')
    out.append('</tbody></table></div><small>Uses existing lead creation and update timestamps. Up to 300 recent leads; potential values are estimates, not collected revenue.</small></section>')
    services=list(c.execute("SELECT id,name,description,unit_price FROM bos59_services WHERE workspace_id=? AND active=1 ORDER BY name LIMIT 100",(wid,)))
    out.append('<section class="ov-panel"><h2>Reusable service catalog</h2><p>New: maintain a workspace price list and turn services into customer estimates without retyping prices.</p>')
    for sid,name,description,price in services:
        out.append('<article class="ov-job"><strong>'+h(name)+'</strong><p>'+h(description)+' · '+h(format(price,".2f"))+'</p>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="service" value="'+h(sid)+'"><button name="action" value="archive_service">Archive service</button></form>')
        out.append('</article>')
    if d["role"] in ("owner","editor"):
        out.append('<form method="post" action="'+url+'">'+hidden+'<label>Service name<input name="service_name" maxlength="120" required></label><label>Description<input name="service_description" maxlength="300" required></label><label>Unit price<input name="service_price" type="number" min="0" max="1000000" step="0.01" required></label><button name="action" value="add_service">Add to catalog</button></form>')
    out.append('</section>')
    if d["role"] in ("owner","editor"):
        out.append('<section class="ov-panel"><h2>Bulk lead importer</h2><p>New: bring existing customer prospects into VELXTRIA in one operation. Paste CSV with columns name,contact,source,value (up to 100 rows). Existing name + contact matches are skipped.</p><form method="post" action="'+url+'">'+hidden+'<label>Lead CSV<textarea name="csv_text" maxlength="40000" rows="6" required placeholder="name,contact,source,value&#10;Example Business,contact@example.com,Referral,250"></textarea></label><button name="action" value="import_csv">Import leads</button></form><small>Import is manual and workspace-scoped. No outreach is sent.</small></section>')
    if d["role"] in ("owner","editor"):
        out.append('<section class="ov-panel"><h2>Add a lead</h2><form method="post" action="'+url+'">'+hidden+'<label>Name<input name="name" required maxlength="120"></label><label>Contact<input name="contact" required maxlength="200"></label><label>Source<input name="source" required maxlength="100"></label><label>Potential value<input name="value" type="number" min="0" max="1000000000" step="0.01" required></label><button name="action" value="add">Add lead</button></form></section>')
    notes_by_lead={}
    for lid,body,created in c.execute("SELECT lead_id,body,created FROM bos59_lead_notes WHERE workspace_id=? ORDER BY created DESC LIMIT 500",(wid,)):
        notes_by_lead.setdefault(lid,[]).append((body,created))
    tasks_by_lead={}
    today=datetime.date.today().isoformat()
    for tid,lid,title,due,status in c.execute("SELECT id,lead_id,title,due_date,status FROM bos59_tasks WHERE workspace_id=? ORDER BY due_date ASC,created ASC LIMIT 1000",(wid,)):
        tasks_by_lead.setdefault(lid,[]).append((tid,title,due,status))
    open_tasks=[(lid,tid,title,due) for lid,items in tasks_by_lead.items() for tid,title,due,status in items if status=="open"]
    due_now=sum(due<=today for lid,tid,title,due in open_tasks)
    out.append('<section class="ov-panel"><h2>Customer task manager</h2><p>New: schedule follow-up work, see upcoming deadlines, and mark tasks completed.</p><p><strong>'+h(due_now)+'</strong> tasks due or overdue · <strong>'+h(len(open_tasks))+'</strong> open tasks</p></section>')
    quotes_by_lead={}
    for qid,lid,description,qty,price,status in c.execute("SELECT id,lead_id,description,quantity,unit_price,status FROM bos59_quotes WHERE workspace_id=? ORDER BY created DESC LIMIT 500",(wid,)):
        quotes_by_lead.setdefault(lid,[]).append((qid,description,qty,price,status))
    quote_totals=quote_workflow_summary(c,uid,wid)
    out.append('<section class="ov-panel"><h2>Quote-to-work workflow</h2><p>New: track estimates through presentation, customer acceptance or decline, then automatically create an internal fulfillment task when acceptance is recorded.</p><div class="ov-metrics">')
    for state,summary in quote_totals.items():
        out.append('<article class="ov-card"><strong>'+h(state.title())+' quotes</strong><span>'+h(summary["count"])+'</span><small>Estimated value '+h(format(summary["value"],".2f"))+'</small></article>')
    out.append('</div><small>All statuses are manually recorded. Accepted quotes do not prove payment. No messages or charges are sent.</small></section>')
    for lead in d["leads"]:
        out.append('<section class="ov-panel"><h2>'+h(lead["name"])+'</h2><p>'+h(lead["source"])+' · '+h(lead["status"])+' · potential value '+h(lead["value"])+'</p>')
        if services and d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Quote from service catalog<select name="service">'+''.join('<option value="'+h(sid)+'">'+h(name)+' — '+h(format(price,".2f"))+'</option>' for sid,name,description,price in services)+'</select></label><label>Quantity<input type="number" name="quantity" min="1" max="100000" value="1" required></label><button name="action" value="quote_service">Create catalog quote</button></form>')
        out.append('<h3>Estimates &amp; quotes</h3>')
        for qid,description,qty,price,status in quotes_by_lead.get(lead["id"],[])[:10]:
            out.append('<article class="ov-job"><strong>'+h(description)+'</strong><p>'+h(qty)+' × '+h(format(price,".2f"))+' = '+h(format(qty*price,".2f"))+' · '+h(status)+'</p>')
            next_states={"draft":("presented","declined"),"presented":("accepted","declined")}
            if d["role"] in ("owner","editor") and status in next_states:
                out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="quote" value="'+h(qid)+'"><label>Record quote outcome<select name="quote_status">'+''.join('<option value="'+h(state)+'">'+h(state.title())+'</option>' for state in next_states[status])+'</select></label><button name="action" value="quote_status">Update quote</button></form>')
            out.append('</article>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Quote item / service<input name="quote_description" maxlength="300" required placeholder="Website setup"></label><label>Quantity<input name="quote_quantity" type="number" min="1" max="100000" value="1" required></label><label>Unit price<input name="quote_price" type="number" min="0" max="1000000" step="0.01" required></label><button name="action" value="create_quote">Save draft estimate</button></form>')
        out.append('<details><summary>Edit customer details</summary>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Customer name<input name="name" maxlength="120" required value="'+h(lead["name"])+'"></label><label>Contact<input name="contact" maxlength="200" required value="'+h(lead["contact"])+'"></label><label>Source<input name="source" maxlength="100" required value="'+h(lead["source"])+'"></label><label>Potential value<input name="value" type="number" min="0" max="1000000000" step="0.01" required value="'+h(lead["value"])+'"></label><button name="action" value="edit_lead">Save customer changes</button></form>')
        else:
            out.append('<p>Contact: '+h(lead["contact"])+'</p>')
        out.append('</details>')
        timeline=[]
        for body,created in notes_by_lead.get(lead["id"],[]):
            timeline.append((created,"Interaction",body))
        for tid,task_title,due,status in tasks_by_lead.get(lead["id"],[]):
            timeline.append((int(time.mktime(datetime.date.fromisoformat(due).timetuple())),"Task "+status,task_title+" (due "+due+")"))
        for action in d["actions"]:
            if action["lead_id"]==lead["id"]:
                timeline.append((action["created"],"Message draft "+action["decision"],action["message"]))
        timeline.sort(key=lambda x:x[0],reverse=True)
        out.append('<details><summary>Unified customer activity ('+h(len(timeline))+')</summary>')
        for when,kind,detail in timeline[:30]:
            out.append('<article class="ov-job"><small>'+h(time.strftime("%Y-%m-%d",time.gmtime(when)))+' · '+h(kind)+'</small><p>'+h(detail)+'</p></article>')
        out.append('</details>')
        out.append('<h3>Customer tasks</h3>')
        for tid,task_title,due,status in tasks_by_lead.get(lead["id"],[])[:15]:
            label="Overdue" if status=="open" and due<today else "Due today" if status=="open" and due==today else status.title()
            out.append('<article class="ov-job"><strong>'+h(task_title)+'</strong><p>Due '+h(due)+' · '+h(label)+'</p>')
            if status=="open" and d["role"] in ("owner","editor"):
                out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="task" value="'+h(tid)+'"><button name="action" value="complete_task">Mark completed</button></form>')
            out.append('</article>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>New task<input name="task_title" maxlength="160" required placeholder="Call customer about quote"></label><label>Due date<input type="date" name="due_date" required></label><button name="action" value="add_task">Schedule task</button></form>')
        out.append('<h3>Customer interaction history</h3>')
        for note_body,note_created in notes_by_lead.get(lead["id"],[])[:20]:
            out.append('<article class="ov-job"><small>'+h(time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime(note_created)))+'</small><p>'+h(note_body)+'</p></article>')
        if not notes_by_lead.get(lead["id"]):
            out.append('<p><small>No interaction notes yet.</small></p>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Add private interaction note<textarea name="note" maxlength="2000" required placeholder="What happened on the call? What did the customer ask for?"></textarea></label><button name="action" value="note">Save interaction note</button></form>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Status<select name="status">'+''.join('<option value="'+s+'"'+(' selected' if lead["status"]==s else '')+'>'+s+'</option>' for s in STATES)+'</select></label><button name="action" value="status">Update</button></form>')
            days_idle=max(0,(int(time.time())-int(lead["updated"]))//86400)
            draft=suggested_followup(lead["name"],lead["status"],days_idle)
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Suggested follow-up — edit before approval<textarea name="message" required maxlength="2000" rows="6">'+h(draft)+'</textarea></label><small>New: a personalized starting draft. Nothing is sent automatically.</small><button name="action" value="propose">Request approval</button></form>')
        for action in (x for x in d["actions"] if x["lead_id"]==lead["id"]):
            out.append('<article class="ov-job"><strong>Draft · '+h(action["decision"])+'</strong><p>'+h(action["message"])+'</p><small>'+h(action["reason"])+'</small>')
            if action["decision"]=="pending" and d["role"]=="owner":
                out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="draft" value="'+h(action["id"])+'"><label>Review reason<input name="reason" required maxlength="500"></label><button name="decision" value="approved">Approve draft</button><button name="decision" value="rejected">Reject draft</button><input type="hidden" name="action" value="review"></form>')
            out.append('</article>')
        out.append('</section>')
    out.append('<p><a href="/business-os-v59.csv?w='+urllib.parse.quote(wid,safe='')+'">Export lead CSV</a></p><p><small>Manual records only. No email is sent, no money is moved, and outcomes are not guaranteed.</small></p>')
    return ''.join(out)
