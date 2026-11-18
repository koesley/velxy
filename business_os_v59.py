"""VELXTRIA Business OS: scoped, approval-first revenue recovery and command metrics.

No outbound messages, autonomous spending, or unsupported revenue claims.
"""
import csv
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

def overview(c,uid,wid):
    role=core.access(c,uid,wid)
    init(c)
    leads=[dict(zip(("id","name","contact","source","value","status","created"),
                    row)) for row in c.execute("SELECT id,name,contact,source,value,status,created FROM bos59_leads WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 300",(wid,))]
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
    if d["role"] in ("owner","editor"):
        out.append('<section class="ov-panel"><h2>Add a lead</h2><form method="post" action="'+url+'">'+hidden+'<label>Name<input name="name" required maxlength="120"></label><label>Contact<input name="contact" required maxlength="200"></label><label>Source<input name="source" required maxlength="100"></label><label>Potential value<input name="value" type="number" min="0" max="1000000000" step="0.01" required></label><button name="action" value="add">Add lead</button></form></section>')
    for lead in d["leads"]:
        out.append('<section class="ov-panel"><h2>'+h(lead["name"])+'</h2><p>'+h(lead["source"])+' · '+h(lead["status"])+' · potential value '+h(lead["value"])+'</p>')
        if d["role"] in ("owner","editor"):
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Status<select name="status">'+''.join('<option value="'+s+'"'+(' selected' if lead["status"]==s else '')+'>'+s+'</option>' for s in STATES)+'</select></label><button name="action" value="status">Update</button></form>')
            out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="lead" value="'+h(lead["id"])+'"><label>Follow-up draft<textarea name="message" required maxlength="2000"></textarea></label><button name="action" value="propose">Request approval</button></form>')
        for action in (x for x in d["actions"] if x["lead_id"]==lead["id"]):
            out.append('<article class="ov-job"><strong>Draft · '+h(action["decision"])+'</strong><p>'+h(action["message"])+'</p><small>'+h(action["reason"])+'</small>')
            if action["decision"]=="pending" and d["role"]=="owner":
                out.append('<form method="post" action="'+url+'">'+hidden+'<input type="hidden" name="draft" value="'+h(action["id"])+'"><label>Review reason<input name="reason" required maxlength="500"></label><button name="decision" value="approved">Approve draft</button><button name="decision" value="rejected">Reject draft</button><input type="hidden" name="action" value="review"></form>')
            out.append('</article>')
        out.append('</section>')
    out.append('<p><a href="/business-os-v59.csv?w='+urllib.parse.quote(wid,safe='')+'">Export lead CSV</a></p><p><small>Manual records only. No email is sent, no money is moved, and outcomes are not guaranteed.</small></p>')
    return ''.join(out)
