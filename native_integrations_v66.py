"""V66 native CRM CSV import and owner-approved email handoff.

CSV imports are validated before any writes. Email handoff uses the owner's
local email application; VELXTRIA never sends or stores SMTP credentials.
"""
import csv
import html
import io
import math
import urllib.parse
import business_os_v59 as crm

FIELDS=("name","contact","source","value")
MAX_ROWS=100

def parse_csv(data):
    if not isinstance(data,str) or len(data.encode("utf-8"))>50000:
        raise ValueError("CSV must be under 50 KB")
    try:
        reader=csv.DictReader(io.StringIO(data, newline=""),strict=True)
        if not reader.fieldnames or not set(FIELDS).issubset(set(reader.fieldnames)):
            raise ValueError("CSV requires name,contact,source,value columns")
        if len(reader.fieldnames)>12:raise ValueError("Too many columns")
        rows=[]
        for row in reader:
            if len(rows)>=MAX_ROWS:raise ValueError("Maximum 100 leads per import")
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV row")
            record={k:(row[k] or "").strip() for k in FIELDS}
            if any(not record[k] or len(record[k])>limit for k,limit in (("name",120),("contact",200),("source",100))):
                raise ValueError("Invalid lead field")
            try:amount=float(record["value"])
            except (ValueError,OverflowError):raise ValueError("Invalid lead value")
            if not math.isfinite(amount) or not 0<=amount<=1e9:raise ValueError("Invalid lead value")
            record["value"]=amount
            rows.append(record)
        if not rows:raise ValueError("CSV contains no leads")
        return rows
    except csv.Error:raise ValueError("Malformed CSV")

def import_csv(c,uid,wid,data):
    crm.core.access(c,uid,wid,write=True)
    rows=parse_csv(data)
    crm.init(c)
    existing={(r[0].strip().casefold(),r[1].strip().casefold()) for r in
              c.execute("SELECT name,contact FROM bos59_leads WHERE workspace_id=?",(wid,))}
    count=0
    for row in rows:
        key=(row["name"].casefold(),row["contact"].casefold())
        if key in existing:continue
        crm.add_lead(c,uid,wid,row["name"],row["contact"],row["source"],row["value"])
        existing.add(key);count+=1
    crm.core.audit(c,uid,wid,"v66_crm_csv_import",str(count))
    return count

def approved_email(c,uid,wid,aid):
    crm.core.access(c,uid,wid,write=True,owner=True)
    crm.init(c)
    row=c.execute("""SELECT l.contact,l.name,a.message FROM bos59_actions a
       JOIN bos59_leads l ON l.id=a.lead_id AND l.workspace_id=a.workspace_id
       WHERE a.id=? AND a.workspace_id=? AND a.decision='approved'""",(aid,wid)).fetchone()
    if not row:raise ValueError("Approved message not found")
    from email.utils import parseaddr
    address=parseaddr(row[0])[1]
    if not address or address!=row[0].strip() or len(address)>254 or any(ch in address for ch in "\r\n\t") or address.count("@")!=1:
        raise ValueError("Lead contact must be a valid email address")
    subject="Follow-up"
    return "mailto:"+urllib.parse.quote(address,safe="@._+-")+"?"+urllib.parse.urlencode({"subject":subject,"body":row[2]})

def render(c,uid,wid,csrf):
    d=crm.overview(c,uid,wid)
    h=lambda v:html.escape(str(v),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V66 · CRM & Email</h1><p>Import leads from CRM CSV files and hand approved email drafts to your email app. Nothing is sent automatically.</p></section>']
    if d["role"] in ("owner","editor"):
        out.append('<section class="panel"><h2>Import CRM CSV</h2><p>Paste up to 100 rows with columns name,contact,source,value. Existing name/contact pairs are skipped.</p><form method="post" action="/native-integrations-v66">'+hidden+'<textarea name="csv_data" rows="8" maxlength="50000" required placeholder="name,contact,source,value"></textarea><button name="action" value="import">Validate & import</button></form></section>')
    if d["role"]=="owner":
        out.append('<section class="panel"><h2>Approved email drafts</h2>')
        for a in d["actions"]:
            if a["decision"]!="approved":continue
            try:link=approved_email(c,uid,wid,a["id"])
            except ValueError:continue
            out.append('<p>'+h(a["message"][:180])+' · <a href="'+h(link)+'">Open in email app</a></p>')
        out.append('</section>')
    return ''.join(out)
