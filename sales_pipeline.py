"""VELXTRIA manual sales pipeline. Scoped per signed-in user; no automatic outreach."""
import html
import secrets
import time

STAGES = ("new", "contacted", "replied", "meeting", "proposal", "won", "lost")
def esc(v):
    return html.escape(str(v), quote=True)
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS sales_pipeline_leads (
        id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, business TEXT NOT NULL,
        contact TEXT NOT NULL, email TEXT NOT NULL, industry TEXT NOT NULL,
        stage TEXT NOT NULL, estimated_value INTEGER NOT NULL DEFAULT 0,
        notes TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS sales_pipeline_owner ON sales_pipeline_leads(owner_id, updated_at)")
def save(c, owner, data):
    setup(c)
    business = data.get("business","").strip()
    if not 2 <= len(business) <= 120:
        raise ValueError("Business name must be 2–120 characters")
    stage = data.get("stage","new")
    if stage not in STAGES:
        raise ValueError("Invalid stage")
    try:
        value = int(data.get("value","0") or "0")
    except ValueError:
        raise ValueError("Estimated value must be a whole number")
    if not 0 <= value <= 100000000:
        raise ValueError("Estimated value out of range")
    contact=data.get("contact","").strip()[:120]
    email=data.get("email","").strip()[:254]
    industry=data.get("industry","").strip()[:80]
    notes=data.get("notes","").strip()[:1000]
    if email and ("@" not in email or "\n" in email):
        raise ValueError("Invalid email")
    lead_id=data.get("lead_id","").strip()
    if lead_id:
        result=c.execute("""UPDATE sales_pipeline_leads SET business=?,contact=?,email=?,industry=?,stage=?,estimated_value=?,notes=?,updated_at=?
                            WHERE id=? AND owner_id=?""",
                         (business,contact,email,industry,stage,value,notes,int(time.time()),lead_id,owner))
        if result.rowcount != 1:
            raise ValueError("Lead not found")
        return lead_id
    lead_id=secrets.token_hex(12)
    now=int(time.time())
    c.execute("INSERT INTO sales_pipeline_leads VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (lead_id,owner,business,contact,email,industry,stage,value,notes,now,now))
    return lead_id
def dashboard(c, owner, csrf):
    setup(c)
    rows=c.execute("""SELECT id,business,contact,email,industry,stage,estimated_value,notes
                      FROM sales_pipeline_leads WHERE owner_id=? ORDER BY updated_at DESC LIMIT 200""",(owner,)).fetchall()
    won=sum(r[6] for r in rows if r[5]=="won")
    potential=sum(r[6] for r in rows if r[5] not in ("won","lost"))
    counts={stage:sum(r[5]==stage for r in rows) for stage in STAGES}
    parts=['<section class="hero"><h1>Sales Pipeline</h1><p>Track outreach, conversations, meetings and deals. Values are manual estimates, not verified revenue.</p></section>',
           '<section class="panel"><h2>Pipeline overview</h2><p>'+str(len(rows))+' recent leads · '+str(counts["replied"])+' replied · '+str(counts["meeting"])+' meetings · '+str(counts["won"])+' won</p><p>Estimated open opportunities: $'+str(potential)+' · Self-reported won deals: $'+str(won)+'</p></section>']
    def form(lead=None):
        lead=lead or ("","","","","","new",0,"")
        fields=[("business","Business",lead[1]),("contact","Contact",lead[2]),("email","Email",lead[3]),("industry","Industry",lead[4]),("value","Estimated deal value (USD)",lead[6])]
        p='<form method="post" action="/sales-pipeline"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="lead_id" value="'+esc(lead[0])+'">'
        for key,label,value in fields:
            p+='<label>'+esc(label)+'<input name="'+key+'" maxlength="254" value="'+esc(value)+'"></label>'
        p+='<label>Stage<select name="stage">'+''.join('<option value="'+stage+'"'+(' selected' if stage==lead[5] else '')+'>'+stage.title()+'</option>' for stage in STAGES)+'</select></label>'
        p+='<label>Notes<textarea name="notes" maxlength="1000">'+esc(lead[7])+'</textarea></label><button type="submit">Save lead</button></form>'
        return p
    parts.append('<section class="panel"><h2>Add a lead</h2>'+form()+'</section>')
    for lead in rows:
        parts.append('<section class="panel"><h3>'+esc(lead[1])+'</h3><p>'+esc(lead[5].title())+' · $'+str(lead[6])+' estimated · '+esc(lead[2])+'</p><details><summary>Edit lead</summary>'+form(lead)+'</details></section>')
    return ''.join(parts)
