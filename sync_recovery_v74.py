"""V74: recover interrupted sync retries and provide scoped monitoring.

A lease-expired running retry is reclaimed using compare-and-swap. Its attempt
is counted toward the bounded retry budget. Recovery is idempotent.
"""
import time
import sync_retries_v73 as retry
import sync_control_v68 as sync
import hubspot_oauth_v70 as oauth
import business_os_v59 as crm

LEASE_SECONDS=1800

def recover(c,now=None,limit=100):
    now=int(time.time() if now is None else now)
    if not 1<=limit<=500:raise ValueError("Invalid recovery limit")
    retry.setup(c)
    stale=c.execute("""SELECT id,workspace_id,attempts,updated
      FROM v73_sync_retries WHERE state='running' AND updated<=?
      ORDER BY updated LIMIT ?""",(now-LEASE_SECONDS,limit)).fetchall()
    recovered=0
    for rid,wid,attempts,updated in stale:
        next_attempt=attempts+1
        if next_attempt>=len(retry.DELAYS):
            state="exhausted";due=now
        else:
            state="pending";due=now+retry.DELAYS[next_attempt]
        result=c.execute("""UPDATE v73_sync_retries
          SET state=?,attempts=?,next_due=?,updated=?
          WHERE id=? AND workspace_id=? AND state='running'
          AND attempts=? AND updated=? RETURNING id""",
          (state,next_attempt,due,now,rid,wid,attempts,updated))
        if result.fetchone():recovered+=1
    return recovered

def monitoring(c,uid,wid,now=None):
    crm.core.access(c,uid,wid)
    retry.setup(c);sync.setup(c);oauth.setup(c)
    now=int(time.time() if now is None else now)
    rows=c.execute("""SELECT state,COUNT(*) FROM v73_sync_retries
      WHERE workspace_id=? GROUP BY state""",(wid,)).fetchall()
    counts=dict(rows)
    stale=c.execute("""SELECT COUNT(*) FROM v73_sync_retries
      WHERE workspace_id=? AND state='running' AND updated<=?""",
      (wid,now-LEASE_SECONDS)).fetchone()[0]
    runs=c.execute("""SELECT state,COUNT(*) FROM (
      SELECT state FROM v68_sync_runs WHERE workspace_id=?
      ORDER BY started DESC LIMIT 30) r GROUP BY state""",(wid,)).fetchall()
    return {"retry_counts":counts,"stale_running":stale,"recent_runs":dict(runs)}

def render(c,uid,wid):
    import html
    m=monitoring(c,uid,wid)
    h=lambda v:html.escape(str(v),quote=True)
    counts=m["retry_counts"];runs=m["recent_runs"]
    return ('<section class="panel"><h2>V74 · Sync reliability</h2>'
      '<p>Pending retries: '+h(counts.get("pending",0))+
      ' · Running: '+h(counts.get("running",0))+
      ' · Exhausted: '+h(counts.get("exhausted",0))+'</p>'
      '<p>Interrupted jobs awaiting recovery: '+h(m["stale_running"])+'</p>'
      '<p>Last 30 runs · Successful: '+h(runs.get("success",0))+
      ' · Failed: '+h(runs.get("failed",0))+'</p>'
      '<p>Recovery checks run with the scheduled worker. Stale jobs count toward retry limits.</p></section>')
