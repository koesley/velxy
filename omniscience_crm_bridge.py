"""Read-only bridge from existing CRM intelligence into OMNISCIENCE.

No automatic persistence: user review is required before recording a decision.
This adapter never upgrades inferred evidence into verified facts.
"""
import time
import ascension_next_actions
import sales_pipeline
import omniscience_evidence as ledger

def candidates(c, owner, now=None):
    if not isinstance(owner,int) or owner<1:
        raise ValueError("Invalid account")
    now=int(time.time()) if now is None else now
    sales_pipeline.setup(c)
    rows=ascension_next_actions.recommendations(c,owner,now=now)
    result=[]
    for rec in rows:
        lead_id=rec["lead_id"]
        lead=c.execute("""SELECT business,stage,estimated_value,updated_at
            FROM sales_pipeline_leads WHERE id=? AND owner_id=?""",
            (lead_id,owner)).fetchone()
        if lead is None:
            continue
        business,stage,value,updated=lead
        result.append({
            "source_type":"sales_pipeline_leads",
            "source_id":lead_id,
            "reliability":"inference",
            "observed_at":updated,
            "payload":{"business":business,"stage":stage,
                       "estimated_pipeline_value":value,
                       "source_reliability":"user_reported",
                       "signal":rec["state"],
                       "signal_evidence":rec["evidence"],
                       "calibration":"rule_based_not_calibrated"},
            "objective":"Review opportunity: "+business,
            "condition":str(rec["evidence"]),
            "intervention":str(rec["next_step"]),
            "priority":rec["priority"],
            "target":rec["target"],
            "limitations":"CRM signal only; no verified payment, customer intent or causation"
        })
    return result

def save_for_review(c, owner, candidate):
    """Persist a candidate after the caller's authenticated human review.

    The source must still exist in this account when persisted. This does not
    authorize outreach, create a workflow, or approve an external action.
    """
    if candidate.get("source_type")!="sales_pipeline_leads":
        raise ValueError("Unsupported source")
    source_id=candidate.get("source_id")
    if not c.execute("SELECT 1 FROM sales_pipeline_leads WHERE id=? AND owner_id=?",
                     (source_id,owner)).fetchone():
        raise ValueError("Source unavailable for this account")
    current=next((item for item in candidates(c,owner) if item["source_id"]==source_id),None)
    if current is None or any(candidate.get(key)!=current[key] for key in ("payload","observed_at","objective","condition","intervention","reliability")):
        raise ValueError("Recommendation is stale or does not match current account evidence")
    if candidate.get("reliability")!="inference":
        raise ValueError("Derived CRM recommendation must remain an inference")
    evidence_id=ledger.record_evidence(
        c,owner,"sales_pipeline_leads",source_id,"inference",
        current["payload"],observed_at=current["observed_at"])
    return ledger.recommend(c,owner,current["objective"],
                            current["condition"],current["intervention"],evidence_id)
