"""V73: durable retry queue for workspace OAuth synchronization.

A failed due run is retried up to three times with increasing delay.
No shared HubSpot credentials; each attempt resolves its own workspace OAuth.
"""
import secrets
import time
import hubspot_oauth_v70 as oauth
import integration_health_v72 as health
import sync_control_v68 as sync
import business_os_v59 as crm

DELAYS=(300,1800,7200)
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS v73_sync_retries(
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,
      attempts INTEGER NOT NULL,next_due INTEGER NOT NULL,
      state TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS v73_retry_due ON v73_sync_retries(state,next_due)")

def enqueue(c,wid,uid,now=None):
    setup(c);now=int(time.time() if now is None else now)
    # Only one outstanding retry chain per workspace.
    existing=c.execute("SELECT id FROM v73_sync_retries WHERE workspace_id=? AND state IN ('pending','running') LIMIT 1",(wid,)).fetchone()
    if existing:return existing[0]
    rid=secrets.token_hex(12)
    c.execute("INSERT INTO v73_sync_retries VALUES(?,?,?,?,?,?,?,?)",(rid,wid,uid,0,now+DELAYS[0],"pending",now,now))
    return rid

def due(c,now,limit=25):
    setup(c);oauth.setup(c)
    return c.execute("""SELECT r.id,r.workspace_id,r.actor,r.attempts,r.next_due
      FROM v73_sync_retries r
      JOIN v70_hubspot_connections h ON h.workspace_id=r.workspace_id
      WHERE r.state='pending' AND r.next_due<=?
      ORDER BY r.next_due ASC LIMIT ?""",(now,limit)).fetchall()

def claim(c,rid,wid,attempts,previous,now):
    row=c.execute("""UPDATE v73_sync_retries SET state='running',updated=?
      WHERE id=? AND workspace_id=? AND state='pending'
      AND attempts=? AND next_due=?
      AND EXISTS(SELECT 1 FROM v70_hubspot_connections WHERE workspace_id=?)
      RETURNING id""",(now,rid,wid,attempts,previous,wid)).fetchone()
    return bool(row)

def finish(c,rid,wid,attempts,success,now):
    if success:
        c.execute("UPDATE v73_sync_retries SET state='success',attempts=?,updated=? WHERE id=? AND workspace_id=?",(attempts+1,now,rid,wid))
    else:
        next_attempt=attempts+1
        if next_attempt>=len(DELAYS):
            c.execute("UPDATE v73_sync_retries SET state='exhausted',attempts=?,updated=? WHERE id=? AND workspace_id=?",(next_attempt,now,rid,wid))
        else:
            c.execute("UPDATE v73_sync_retries SET state='pending',attempts=?,next_due=?,updated=? WHERE id=? AND workspace_id=?",(next_attempt,now+DELAYS[next_attempt],now,rid,wid))

def tick(connect,fetcher=None,requester=None,now=None,limit=25):
    now=int(time.time() if now is None else now)
    if not 1<=limit<=100:raise ValueError("Invalid limit")
    with connect() as c:items=due(c,now,limit)
    results=[]
    for rid,wid,uid,attempts,previous in items:
        with connect() as c:
            if not claim(c,rid,wid,attempts,previous,now):continue
        runid=secrets.token_hex(12)
        with connect() as c:
            sync.setup(c)
            c.execute("INSERT INTO v68_sync_runs VALUES(?,?,?,?,?,?,?)",(runid,wid,uid,"started",0,now,0))
        try:
            with connect() as c:added=health.import_all(c,uid,wid,fetcher=fetcher,requester=requester)
            ok=True
        except Exception:
            added=0;ok=False
        with connect() as c:
            finish(c,rid,wid,attempts,ok,now)
            c.execute("UPDATE v68_sync_runs SET state=?,added=?,finished=? WHERE id=? AND workspace_id=?",
                      ("success" if ok else "failed",added,int(time.time()),runid,wid))
            crm.core.audit(c,uid,wid,"v73_retry_"+("success" if ok else "failed"),rid)
        results.append((wid,"success" if ok else "failed",added))
    return results

def metrics(c,uid,wid):
    crm.core.access(c,uid,wid)
    setup(c)
    return c.execute("SELECT state,COUNT(*) FROM v73_sync_retries WHERE workspace_id=? GROUP BY state",(wid,)).fetchall()
