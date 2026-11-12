"""V75: resumable, workspace-scoped HubSpot contact pagination.

Each successful page commits its cursor alongside imported leads. Failed pages
leave the prior checkpoint intact. Once a complete scan ends, the cursor resets
so later runs can detect changed/new contacts; this is not HubSpot delta API.
"""
import json
import time
import urllib.parse
import urllib.request
import hubspot_oauth_v70 as oauth
import business_os_v59 as crm

PAGE_LIMIT=10
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS v75_contact_checkpoints(
      workspace_id TEXT PRIMARY KEY,cursor TEXT NOT NULL DEFAULT '',
      pages_done INTEGER NOT NULL DEFAULT 0,contacts_added INTEGER NOT NULL DEFAULT 0,
      cycles INTEGER NOT NULL DEFAULT 0,updated INTEGER NOT NULL DEFAULT 0)""")

def status(c,uid,wid):
    crm.core.access(c,uid,wid)
    setup(c)
    row=c.execute("SELECT cursor,pages_done,contacts_added,cycles,updated FROM v75_contact_checkpoints WHERE workspace_id=?",(wid,)).fetchone()
    return {"in_progress":bool(row and row[0]),"pages_done":row[1] if row else 0,"contacts_added":row[2] if row else 0,"cycles":row[3] if row else 0,"updated":row[4] if row else 0}

def default_fetch(url,token):
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=10) as resp:raw=resp.read(131073)
        if len(raw)>131072:raise ValueError("HubSpot response too large")
        return json.loads(raw)
    except Exception:raise ValueError("HubSpot contact page unavailable")

def import_page(c,uid,wid,fetcher=None,requester=None,now=None):
    token=oauth.access_token(c,uid,wid,requester=requester)
    setup(c);crm.init(c)
    now=int(time.time() if now is None else now)
    row=c.execute("SELECT cursor,pages_done,contacts_added,cycles FROM v75_contact_checkpoints WHERE workspace_id=?",(wid,)).fetchone()
    cursor=row[0] if row else ''
    query={"limit":"100","properties":"firstname,lastname,email"}
    if cursor:query["after"]=cursor
    data=(fetcher or default_fetch)(oauth.CONTACTS+"?"+urllib.parse.urlencode(query),token)
    if not isinstance(data,dict) or not isinstance(data.get("results"),list):raise ValueError("Invalid HubSpot page")
    existing={r[0].strip().casefold() for r in c.execute("SELECT contact FROM bos59_leads WHERE workspace_id=?",(wid,))}
    added=0
    for item in data["results"][:100]:
        if not isinstance(item,dict):continue
        p=item.get("properties") or {}
        if not isinstance(p,dict):continue
        email=p.get("email")
        if not isinstance(email,str):continue
        email=email.strip()
        if not email or len(email)>200 or email.casefold() in existing:continue
        name=" ".join(str(p.get(k) or "").strip() for k in ("firstname","lastname")).strip()[:120] or email[:120]
        crm.add_lead(c,uid,wid,name,email,"HubSpot OAuth",0)
        existing.add(email.casefold());added+=1
    paging=data.get("paging") or {}
    next_obj=paging.get("next") if isinstance(paging,dict) else None
    next_cursor=next_obj.get("after") if isinstance(next_obj,dict) else None
    if next_cursor is not None and (not isinstance(next_cursor,str) or not 1<=len(next_cursor)<=256 or next_cursor==cursor):
        raise ValueError("Invalid HubSpot cursor")
    next_cursor=next_cursor or ''
    pages=(row[1] if row else 0)+1
    total=(row[2] if row else 0)+added
    cycles=(row[3] if row else 0)+(not bool(next_cursor))
    if row:
        c.execute("UPDATE v75_contact_checkpoints SET cursor=?,pages_done=?,contacts_added=?,cycles=?,updated=? WHERE workspace_id=?",
                  (next_cursor,pages,total,cycles,now,wid))
    else:
        c.execute("INSERT INTO v75_contact_checkpoints VALUES(?,?,?,?,?,?)",(wid,next_cursor,pages,total,cycles,now))
    return added,bool(next_cursor)

def import_batch(connect,uid,wid,fetcher=None,requester=None,max_pages=PAGE_LIMIT):
    if not 1<=max_pages<=PAGE_LIMIT:raise ValueError("Invalid page limit")
    total=0
    for _ in range(max_pages):
        # Each page commits independently, preserving progress if a later page fails.
        with connect() as c:
            added,more=import_page(c,uid,wid,fetcher=fetcher,requester=requester)
        total+=added
        if not more:break
    return total
