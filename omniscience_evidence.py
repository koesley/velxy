"""OMNISCIENCE: tenant-scoped, append-only evidence and decision records.

No external actions, inferred payments, or model-generated permissions.
"""
import json
import secrets
import time

RELIABILITY = frozenset(("system_observed", "user_reported", "external_verified", "estimate", "inference", "unknown"))
DECISIONS = frozenset(("accept", "defer", "dismiss"))
MAX_JSON = 12000

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS omnis_evidence (
      id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, source_type TEXT NOT NULL,
      source_id TEXT NOT NULL, reliability TEXT NOT NULL, observed_at INTEGER NOT NULL,
      recorded_at INTEGER NOT NULL, payload TEXT NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS omnis_evidence_owner_source ON omnis_evidence(owner_id,source_type,source_id,recorded_at)")
    c.execute("""CREATE TABLE IF NOT EXISTS omnis_recommendations (
      id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, objective TEXT NOT NULL,
      condition TEXT NOT NULL, intervention TEXT NOT NULL, evidence_id TEXT NOT NULL,
      created_at INTEGER NOT NULL, expires_at INTEGER,
      FOREIGN KEY(evidence_id) REFERENCES omnis_evidence(id))""")
    c.execute("CREATE INDEX IF NOT EXISTS omnis_rec_owner ON omnis_recommendations(owner_id,created_at)")
    c.execute("""CREATE TABLE IF NOT EXISTS omnis_decision_events (
      id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, recommendation_id TEXT NOT NULL,
      choice TEXT NOT NULL, rationale TEXT NOT NULL, created_at INTEGER NOT NULL,
      FOREIGN KEY(recommendation_id) REFERENCES omnis_recommendations(id))""")
    c.execute("CREATE INDEX IF NOT EXISTS omnis_decision_owner ON omnis_decision_events(owner_id,recommendation_id,created_at)")

def _text(value, limit, label):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError(label+" is required and must be at most "+str(limit)+" characters")
    return value.strip()

def record_evidence(c, owner, source_type, source_id, reliability, payload, observed_at=None):
    setup(c)
    if type(owner) is not int or owner<1: raise ValueError("Invalid account")
    source_type=_text(source_type,80,"Source type")
    source_id=_text(source_id,160,"Source ID")
    if reliability not in RELIABILITY: raise ValueError("Invalid evidence reliability")
    if not isinstance(payload,dict): raise ValueError("Evidence payload must be an object")
    try:
        encoded=json.dumps(payload,sort_keys=True,allow_nan=False)
    except (TypeError,ValueError) as exc:
        raise ValueError("Evidence payload must be valid JSON") from exc
    if len(encoded)>MAX_JSON: raise ValueError("Evidence payload too large")
    now=int(time.time())
    observed_at=now if observed_at is None else observed_at
    if type(observed_at) is not int or observed_at<0 or observed_at>now+300:
        raise ValueError("Invalid observation timestamp")
    eid=secrets.token_hex(16)
    c.execute("INSERT INTO omnis_evidence VALUES (?,?,?,?,?,?,?,?)",
              (eid,owner,source_type,source_id,reliability,observed_at,now,encoded))
    return eid

def recommend(c, owner, objective, condition, intervention, evidence_id, expires_at=None):
    setup(c)
    if type(owner) is not int or owner<1: raise ValueError("Invalid account")
    objective=_text(objective,240,"Objective")
    condition=_text(condition,1000,"Condition")
    intervention=_text(intervention,1000,"Intervention")
    evidence=c.execute("SELECT 1 FROM omnis_evidence WHERE id=? AND owner_id=?",(evidence_id,owner)).fetchone()
    if not evidence: raise ValueError("Evidence unavailable for this account")
    now=int(time.time())
    if expires_at is not None and (type(expires_at) is not int or expires_at<=now):
        raise ValueError("Expiration must be in the future")
    rid=secrets.token_hex(16)
    c.execute("INSERT INTO omnis_recommendations VALUES (?,?,?,?,?,?,?,?)",
              (rid,owner,objective,condition,intervention,evidence_id,now,expires_at))
    return rid

def decide(c, owner, recommendation_id, choice, rationale):
    setup(c)
    if type(owner) is not int or owner<1: raise ValueError("Invalid account")
    if choice not in DECISIONS: raise ValueError("Invalid decision")
    rationale=_text(rationale,1000,"Rationale")
    row=c.execute("SELECT expires_at FROM omnis_recommendations WHERE id=? AND owner_id=?",
                  (recommendation_id,owner)).fetchone()
    if not row: raise ValueError("Recommendation unavailable for this account")
    now=int(time.time())
    if row[0] is not None and row[0]<=now: raise ValueError("Recommendation expired")
    eid=secrets.token_hex(16)
    c.execute("INSERT INTO omnis_decision_events VALUES (?,?,?,?,?,?)",
              (eid,owner,recommendation_id,choice,rationale,now))
    return eid

def history(c, owner, recommendation_id):
    if type(owner) is not int or owner<1: raise ValueError("Invalid account")
    setup(c)
    row=c.execute("""SELECT r.objective,r.condition,r.intervention,e.source_type,
      e.source_id,e.reliability,e.observed_at,e.payload,r.created_at,r.expires_at
      FROM omnis_recommendations r JOIN omnis_evidence e
      ON e.id=r.evidence_id AND e.owner_id=r.owner_id
      WHERE r.id=? AND r.owner_id=?""",(recommendation_id,owner)).fetchone()
    if not row: raise ValueError("Recommendation unavailable for this account")
    events=c.execute("""SELECT choice,rationale,created_at FROM omnis_decision_events
      WHERE owner_id=? AND recommendation_id=? ORDER BY created_at,id""",
      (owner,recommendation_id)).fetchall()
    return {"objective":row[0],"condition":row[1],"intervention":row[2],
            "evidence":{"source_type":row[3],"source_id":row[4],"reliability":row[5],
                        "observed_at":row[6],"payload":json.loads(row[7])},
            "created_at":row[8],"expires_at":row[9],
            "decisions":[{"choice":x[0],"rationale":x[1],"created_at":x[2]} for x in events]}
