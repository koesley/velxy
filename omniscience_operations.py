"""OMNISCIENCE operational review: decision state, aging, and evidence freshness.

Read-only. All calculations are descriptive and scoped to one authenticated owner.
No predictions, inferred revenue, automatic decisions or external execution.
"""
import time
import html
import omniscience_evidence as ledger

def summary(c, owner, now=None):
    if type(owner) is not int or owner < 1:
        raise ValueError("Authenticated account required")
    ledger.setup(c)
    now = int(time.time()) if now is None else int(now)
    rows = c.execute("""SELECT r.id,r.objective,r.created_at,r.expires_at,
       e.source_type,e.source_id,e.reliability,e.observed_at
       FROM omnis_recommendations r JOIN omnis_evidence e
       ON e.id=r.evidence_id AND e.owner_id=r.owner_id
       WHERE r.owner_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 500""",
       (owner,)).fetchall()
    decisions = c.execute("""SELECT recommendation_id,choice,rationale,created_at,id
       FROM omnis_decision_events WHERE owner_id=?
       ORDER BY created_at DESC,id DESC""",(owner,)).fetchall()
    latest={}
    for rid,choice,rationale,created,event_id in decisions:
        if rid not in latest:
            latest[rid]=(choice,rationale,created)
    counts={"pending":0,"accepted":0,"deferred":0,"dismissed":0,
            "expired":0,"stale_evidence":0}
    records=[]
    for rid,objective,created,expires,source_type,source_id,reliability,observed in rows:
        decision=latest.get(rid)
        state=("expired" if expires is not None and expires<=now
               else {"accept":"accepted","defer":"deferred","dismiss":"dismissed"}.get(decision[0],"pending")
               if decision else "pending")
        counts[state]+=1
        age_days=max(0,(now-int(observed))//86400)
        stale=age_days>=30
        if stale:counts["stale_evidence"]+=1
        records.append({"id":rid,"objective":objective,"state":state,
                        "source_type":source_type,"source_id":source_id,
                        "reliability":reliability,"evidence_age_days":age_days,
                        "stale_evidence":stale,"last_decision":decision})
    return {"counts":counts,"records":records,"scope":"latest 500 recommendations",
            "note":"Decision counts are not conversions, completed actions, or received revenue."}

def dashboard(c,owner):
    report=summary(c,owner)
    esc=lambda v:html.escape(str(v),quote=True)
    counts=report["counts"]
    out=['<section class="hero"><h1>OMNISCIENCE Decision Operations</h1>',
         '<p>Account-scoped operational follow-through; no predicted revenue.</p></section>',
         '<section class="panel"><h2>Decision register</h2><p>']
    for label in ("pending","accepted","deferred","dismissed","expired","stale_evidence"):
        out.extend((esc(label.replace("_"," ").title()),": ",str(counts[label])," · "))
    out.extend(("</p><p>",esc(report["scope"])," · ",esc(report["note"]),"</p></section>",
                '<section class="panel"><h2>Items requiring attention</h2>'))
    for item in report["records"]:
        if item["state"] not in ("pending","deferred","expired") and not item["stale_evidence"]:
            continue
        out.extend(("<article><h3>",esc(item["objective"]),"</h3><p>Status: ",
                    esc(item["state"])," · Evidence: ",esc(item["reliability"]),
                    " · Age: ",str(item["evidence_age_days"])," days</p><p>Source: ",
                    esc(item["source_type"])," / ",esc(item["source_id"]),
                    "</p></article>"))
    out.append('</section>')
    return ''.join(out)
