"""V68 workspace sync policy and durable HubSpot import history.

Schedules are stored and due runs can be triggered by a trusted scheduler.
This module does not start a background worker or expose a public cron endpoint.
"""
import html
import os
import secrets
import time
import urllib.parse
import hubspot_v67 as hubspot
import business_os_v59 as crm

CADENCES={"off":0,"daily":86400,"weekly":604800}

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS v68_sync_policies(
      workspace_id TEXT PRIMARY KEY,cadence TEXT NOT NULL,next_due INTEGER NOT NULL,
      updated_by INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS v68_sync_runs(
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,
      state TEXT NOT NULL,added INTEGER NOT NULL,started INTEGER NOT NULL,
      finished INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS v68_runs_scope ON v68_sync_runs(workspace_id,started)")

def set_policy(c,uid,wid,cadence,now=None):
    crm.core.access(c,uid,wid,write=True,owner=True)
    if cadence not in CADENCES:raise ValueError("Unknown schedule")
    setup(c);now=int(time.time() if now is None else now)
    due=now+CADENCES[cadence] if CADENCES[cadence] else 0
    if c.execute("SELECT 1 FROM v68_sync_policies WHERE workspace_id=?",(wid,)).fetchone():
        c.execute("UPDATE v68_sync_policies SET cadence=?,next_due=?,updated_by=?,updated=? WHERE workspace_id=?",(cadence,due,uid,now,wid))
    else:c.execute("INSERT INTO v68_sync_policies VALUES(?,?,?,?,?)",(wid,cadence,due,uid,now))
    crm.core.audit(c,uid,wid,"v68_sync_policy",cadence)
    return due

def run(c,uid,wid,fetcher=None,now=None,due_only=False):
    crm.core.access(c,uid,wid,write=True,owner=True)
    setup(c);now=int(time.time() if now is None else now)
    policy=c.execute("SELECT cadence,next_due FROM v68_sync_policies WHERE workspace_id=?",(wid,)).fetchone()
    if due_only and (not policy or policy[0]=="off" or policy[1]>now):
        raise ValueError("Sync is not due")
    rid=secrets.token_hex(12)
    c.execute("INSERT INTO v68_sync_runs VALUES(?,?,?,?,?,?,?)",(rid,wid,uid,"started",0,now,0))
    try:
        added=hubspot.sync(c,uid,wid,fetcher=fetcher)
    except Exception:
        c.execute("UPDATE v68_sync_runs SET state='failed',finished=? WHERE id=?",(int(time.time()),rid))
        crm.core.audit(c,uid,wid,"v68_sync_failed",rid)
        raise
    c.execute("UPDATE v68_sync_runs SET state='success',added=?,finished=? WHERE id=?",(added,int(time.time()),rid))
    if policy and policy[0]!="off":
        c.execute("UPDATE v68_sync_policies SET next_due=? WHERE workspace_id=?",(now+CADENCES[policy[0]],wid))
    crm.core.audit(c,uid,wid,"v68_sync_completed",rid)
    return rid,added

def overview(c,uid,wid):
    role=crm.core.access(c,uid,wid)
    setup(c)
    policy=c.execute("SELECT cadence,next_due FROM v68_sync_policies WHERE workspace_id=?",(wid,)).fetchone()
    runs=c.execute("SELECT state,added,started,finished FROM v68_sync_runs WHERE workspace_id=? ORDER BY started DESC LIMIT 30",(wid,)).fetchall()
    return role,policy,runs

def render(c,uid,wid,csrf):
    role,policy,runs=overview(c,uid,wid)
    h=lambda v:html.escape(str(v),quote=True)
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V68 · Sync Control Center</h1><p>Manage HubSpot synchronization policy and inspect import history. V69 can execute due policies hourly through GitHub Actions once repository secrets are configured. A cadence alone does not activate automation.</p><p>Current policy: '+h(policy[0] if policy else "off")+'</p></section>']
    if role=="owner":
        out.append('<section class="panel"><h2>Schedule preference</h2><form method="post" action="/sync-control-v68">'+hidden+'<select name="cadence">'+''.join('<option value="'+h(k)+'"'+(' selected' if policy and policy[0]==k else '')+'>'+h(k.title())+'</option>' for k in CADENCES)+'</select><button name="action" value="policy">Save policy</button></form><h2>Import now</h2><form method="post" action="/sync-control-v68">'+hidden+'<button name="action" value="run">Sync HubSpot now</button></form></section>')
    out.append('<section class="panel"><h2>Recent sync history</h2>')
    for state,added,started,finished in runs:
        out.append('<p>'+h(state)+' · '+h(added)+' imported · '+h(time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime(started)))+'</p>')
    out.append('</section>')
    return ''.join(out)
