"""V71 scheduled OAuth synchronization.

Each due workspace must have its own V70 HubSpot OAuth connection. No shared
administrator HubSpot token is read or used. Requires durable PostgreSQL.
"""
import os
import time
import sync_control_v68 as sync
import hubspot_oauth_v70 as oauth
import business_os_v59 as crm

def due(c,now,limit):
    sync.setup(c);oauth.setup(c)
    return c.execute("""SELECT p.workspace_id,p.updated_by,p.cadence,p.next_due
      FROM v68_sync_policies p
      JOIN v70_hubspot_connections h ON h.workspace_id=p.workspace_id
      WHERE p.cadence IN ('daily','weekly') AND p.next_due>0 AND p.next_due<=?
      ORDER BY p.next_due ASC LIMIT ?""",(now,limit)).fetchall()

def claim(c,wid,uid,cadence,previous,now):
    # CAS protects against duplicate scheduled claims by competing workers.
    result=c.execute("""UPDATE v68_sync_policies SET next_due=?
      WHERE workspace_id=? AND updated_by=? AND cadence=? AND next_due=?
      AND EXISTS(SELECT 1 FROM v70_hubspot_connections WHERE workspace_id=?)
      RETURNING workspace_id""",
      (now+sync.CADENCES[cadence],wid,uid,cadence,previous,wid))
    return result.fetchone() is not None

def tick(connect,fetcher=None,requester=None,now=None,limit=25):
    now=int(time.time() if now is None else now)
    if not 1<=limit<=100:raise ValueError("Invalid batch size")
    with connect() as c:candidates=due(c,now,limit)
    results=[]
    for wid,uid,cadence,previous in candidates:
        with connect() as c:
            if not claim(c,wid,uid,cadence,previous,now):continue
        # Record an attempt before making external network requests.
        import secrets
        rid=secrets.token_hex(12)
        with connect() as c:
            sync.setup(c)
            c.execute("INSERT INTO v68_sync_runs VALUES(?,?,?,?,?,?,?)",
                      (rid,wid,uid,"started",0,now,0))
        try:
            with connect() as c:
                added=oauth.import_contacts(c,uid,wid,fetcher=fetcher,requester=requester)
            with connect() as c:
                c.execute("UPDATE v68_sync_runs SET state='success',added=?,finished=? WHERE id=? AND workspace_id=?",
                          (added,int(time.time()),rid,wid))
                crm.core.audit(c,uid,wid,"v71_oauth_sync_success",rid)
            results.append((wid,"success",added))
        except Exception:
            with connect() as c:
                c.execute("UPDATE v68_sync_runs SET state='failed',finished=? WHERE id=? AND workspace_id=?",
                          (int(time.time()),rid,wid))
                crm.core.audit(c,uid,wid,"v71_oauth_sync_failed",rid)
            results.append((wid,"failed",0))
    return results

def main():
    import persistent
    if not persistent.REMOTE:raise RuntimeError("V71 scheduled sync requires PostgreSQL")
    # OAuth credentials are decrypted per workspace with the stable Fernet key.
    oauth.settings()
    from portal import db
    results=tick(db)
    print("V71 OAuth sync: processed",len(results),"succeeded",sum(r[1]=="success" for r in results),"failed",sum(r[1]=="failed" for r in results))

if __name__=="__main__":main()
