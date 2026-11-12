"""V72: bounded paginated HubSpot import and workspace connection health."""
import html
import json
import time
import urllib.parse
import urllib.request
import hubspot_oauth_v70 as oauth
import sync_control_v68 as sync
import business_os_v59 as crm

MAX_PAGES=10
PAGE_SIZE=100

def import_all(c,uid,wid,fetcher=None,requester=None):
    token=oauth.access_token(c,uid,wid,requester=requester)
    if fetcher is None:
        def fetcher(url,token):
            req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
            try:
                with urllib.request.urlopen(req,timeout=10) as resp:raw=resp.read(131073)
                if len(raw)>131072:raise ValueError("HubSpot response too large")
                return json.loads(raw)
            except Exception:raise ValueError("HubSpot import failed")
    crm.init(c)
    existing={r[0].strip().casefold() for r in c.execute("SELECT contact FROM bos59_leads WHERE workspace_id=?",(wid,))}
    cursor=None;seen=set();added=0;pages=0
    for _ in range(MAX_PAGES):
        query={"limit":str(PAGE_SIZE),"properties":"firstname,lastname,email"}
        if cursor:query["after"]=cursor
        url=oauth.CONTACTS+"?"+urllib.parse.urlencode(query)
        data=fetcher(url,token)
        if not isinstance(data,dict) or not isinstance(data.get("results"),list):
            raise ValueError("Invalid HubSpot contact response")
        pages+=1
        for item in data["results"][:PAGE_SIZE]:
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
        next_page=paging.get("next") if isinstance(paging,dict) else None
        next_cursor=next_page.get("after") if isinstance(next_page,dict) else None
        if not next_cursor:break
        if not isinstance(next_cursor,str) or len(next_cursor)>256 or next_cursor in seen:
            raise ValueError("Invalid HubSpot pagination cursor")
        seen.add(next_cursor);cursor=next_cursor
    crm.core.audit(c,uid,wid,"v72_paginated_import",str(added))
    return added

def health(c,uid,wid,now=None):
    crm.core.access(c,uid,wid)
    oauth.setup(c);sync.setup(c)
    now=int(time.time() if now is None else now)
    connection=c.execute("SELECT expires,updated FROM v70_hubspot_connections WHERE workspace_id=?",(wid,)).fetchone()
    policy=c.execute("SELECT cadence,next_due FROM v68_sync_policies WHERE workspace_id=?",(wid,)).fetchone()
    last=c.execute("SELECT state,added,started FROM v68_sync_runs WHERE workspace_id=? ORDER BY started DESC LIMIT 1",(wid,)).fetchone()
    return {"connected":bool(connection),"token_status":("not_connected" if not connection else "refresh_due" if connection[0]<=now+60 else "valid"),"cadence":policy[0] if policy else "off","next_due":policy[1] if policy else 0,"last_state":last[0] if last else "never","last_added":last[1] if last else 0,"last_run":last[2] if last else 0}

def render(c,uid,wid):
    d=health(c,uid,wid)
    h=lambda x:html.escape(str(x),quote=True)
    def stamp(value):return time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime(value)) if value else "—"
    return ('<section class="panel"><h1>VELXTRIA V72 · Integration Health</h1>'
        '<p>HubSpot: '+('Connected' if d["connected"] else 'Not connected')+'</p>'
        '<p>Token: '+h(d["token_status"])+' (refresh_due means refresh can occur at the next import)</p>'
        '<p>Schedule: '+h(d["cadence"])+' · Next due: '+h(stamp(d["next_due"]))+'</p>'
        '<p>Last sync: '+h(d["last_state"])+' · '+h(stamp(d["last_run"]))+
        ' · Imported: '+h(d["last_added"])+'</p>'
        '<p>Imports fetch up to 1,000 contacts across 10 pages per run.</p></section>')
