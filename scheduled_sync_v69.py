"""V69 scheduled HubSpot synchronization worker.

Runs from an external scheduler (for example GitHub Actions). Requires the same
persistent PostgreSQL database and server-side HubSpot token as the web app.
No customer OAuth credentials are stored or collected.
"""
import os
import time
import sync_control_v68 as sync
import business_os_v59 as crm

def due_policies(c,now=None,limit=25):
    sync.setup(c)
    now=int(time.time() if now is None else now)
    return c.execute("""SELECT workspace_id,updated_by,cadence,next_due
        FROM v68_sync_policies
        WHERE cadence IN ('daily','weekly') AND next_due>0 AND next_due<=?
        ORDER BY next_due ASC LIMIT ?""",(now,limit)).fetchall()

def claim(c,wid,uid,cadence,due,now):
    # Compare-and-swap ensures only one worker wins each due slot.
    interval=sync.CADENCES[cadence]
    result=c.execute("""UPDATE v68_sync_policies SET next_due=?
        WHERE workspace_id=? AND updated_by=? AND cadence=? AND next_due=?""",
        (now+interval,wid,uid,cadence,due))
    return result.rowcount==1

def tick(connect,fetcher=None,now=None,limit=25):
    now=int(time.time() if now is None else now)
    # Claim in a short transaction; never hold a database lock across network I/O.
    with connect() as c:
        candidates=due_policies(c,now,limit)
    results=[]
    for wid,uid,cadence,due in candidates:
        try:
            with connect() as c:
                if not claim(c,wid,uid,cadence,due,now):continue
            with connect() as c:
                rid,added=sync.run(c,uid,wid,fetcher=fetcher,now=now)
            results.append((wid,"success",added))
        except Exception:
            # Do not leak credentials, contact details or provider responses into logs.
            results.append((wid,"failed",0))
    return results

def main():
    import persistent
    if not persistent.REMOTE:
        raise RuntimeError("Scheduled synchronization requires persistent PostgreSQL")
    if not os.getenv("VELXTRIA_V67_HUBSPOT_TOKEN"):
        raise RuntimeError("HubSpot token is not configured")
    # Use the app's existing schema initialization.
    from portal import db
    result=tick(db)
    print("V69 scheduler: processed",len(result),"workspaces; succeeded",sum(r[1]=="success" for r in result),"failed",sum(r[1]=="failed" for r in result))

if __name__=="__main__":main()
