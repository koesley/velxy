"""V67: Owner-controlled HubSpot CRM contact synchronization.

Uses a server-side private access token from Render environment, never stored in
the database or exposed to browser. Read-only from HubSpot; imports into VELXTRIA.
"""
import html
import json
import os
import urllib.request
import urllib.error
import urllib.parse
import business_os_v59 as crm

API="https://api.hubapi.com/crm/v3/objects/contacts"
MAX_CONTACTS=100

def fetch_contacts(fetcher=None):
    token=os.getenv("VELXTRIA_V67_HUBSPOT_TOKEN","")
    if len(token)<12:raise ValueError("HubSpot is not configured")
    contacts=[];cursor=None
    for _ in range(2):
        url=API+"?"+urllib.parse.urlencode({"limit":"50","properties":"firstname,lastname,email"})
        if cursor:url+="&after="+urllib.parse.quote(cursor,safe="")
        if fetcher is not None:data=fetcher(url,token)
        else:
            request=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
            try:
                with urllib.request.urlopen(request,timeout=10) as response:
                    raw=response.read(131073)
                if len(raw)>131072:raise ValueError("HubSpot response too large")
                data=json.loads(raw)
            except (urllib.error.URLError,TimeoutError,ValueError):
                raise ValueError("HubSpot synchronization failed")
        if not isinstance(data,dict) or not isinstance(data.get("results"),list):
            raise ValueError("Invalid HubSpot response")
        for item in data["results"]:
            if not isinstance(item,dict):continue
            p=item.get("properties") or {}
            if not isinstance(p,dict):continue
            email=p.get("email")
            if not isinstance(email,str) or not email.strip() or len(email)>200:continue
            name=" ".join(str(p.get(k) or "").strip() for k in ("firstname","lastname")).strip() or email
            contacts.append({"name":name[:120],"contact":email.strip(),"source":"HubSpot","value":0})
            if len(contacts)>=MAX_CONTACTS:break
        if len(contacts)>=MAX_CONTACTS:break
        paging=data.get("paging") or {}
        cursor=(paging.get("next") or {}).get("after") if isinstance(paging,dict) else None
        if not isinstance(cursor,str) or not cursor or len(cursor)>200:break
    return contacts

def sync(c,uid,wid,fetcher=None):
    crm.core.access(c,uid,wid,write=True,owner=True)
    crm.init(c)
    rows=fetch_contacts(fetcher)
    existing={row[0].strip().casefold() for row in c.execute("SELECT contact FROM bos59_leads WHERE workspace_id=?",(wid,))}
    added=0
    for row in rows:
        email=row["contact"].casefold()
        if email in existing:continue
        crm.add_lead(c,uid,wid,row["name"],row["contact"],row["source"],0)
        existing.add(email);added+=1
    crm.core.audit(c,uid,wid,"v67_hubspot_contacts_imported",str(added))
    return added

def render(c,uid,wid,csrf):
    role=crm.core.access(c,uid,wid)
    h=lambda x:html.escape(str(x),quote=True)
    configured=len(os.getenv("VELXTRIA_V67_HUBSPOT_TOKEN",""))>=12
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V67 · HubSpot CRM Sync</h1><p>Import up to 100 HubSpot contacts into your workspace as leads. Existing email contacts are skipped. HubSpot is never modified.</p><p>Connection: '+('Token configured' if configured else 'Not configured')+'</p></section>']
    if role=="owner":
        out.append('<section class="panel"><h2>Read-only synchronization</h2><p>Set VELXTRIA_V67_HUBSPOT_TOKEN as a secret in Render with HubSpot crm.objects.contacts.read scope. A workspace owner must initiate every import.</p><form method="post" action="/hubspot-v67">'+hidden+'<button name="action" value="sync">Import HubSpot contacts</button></form></section>')
    return ''.join(out)
