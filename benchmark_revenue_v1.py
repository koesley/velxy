"""Offline V60 baseline: synthetic inputs only; no production database or network."""
import json
import random
from unittest.mock import patch
import business_intelligence_v60 as engine

def fixture(seed=42):
    rng=random.Random(seed)
    leads=[{"id":str(i),"status":"won","value":rng.randint(100,900)} for i in range(100)]
    for i in range(5):
        leads[i]["status"]="new"
        leads[i]["age_days"]=45
    for i in range(5,10):
        leads[i]["status"]="contacted"
        leads[i]["followup_overdue"]=True
    return {
        "leads":leads,"metrics":{"pending_approvals":0},
        "invoices":[{"id":"I1","balance":2400,"days_overdue":30}],
        "customers":[{"id":"C1","prior_purchases":10,"recent_purchases":0}],
        "products":[{"id":"P1","price":20,"cost":25,"units":100}]
    }

def run(seed=42):
    data=fixture(seed)
    workforce={"knowledge":[{"kind":"faq"}],"counts":{"awaiting_review":0,"jobs":0}}
    with patch.object(engine.leads,"overview",return_value=data), patch.object(engine.agents,"overview",return_value=workforce):
        report=engine.analyze(None,1,"synthetic")
    codes={s["code"] for s in report["suggestions"]}
    # Generic signals are not proof of specific problem detection.
    expected={"neglected_leads":"new_leads","missed_followups":"contacted_leads",
              "overdue_invoices":"overdue_invoices","retention_decline":"retention_decline",
              "negative_margin":"negative_margin"}
    matches=[k for k,v in expected.items() if v in codes]
    return {"seed":seed,"generic_signal_matches":matches,
            "signal_score_out_of_40":8*len(matches),
            "missing_signals":[k for k in expected if k not in matches],
            "unexpected_codes":sorted(codes-set(expected.values())),
            "financial_accuracy":None,"decision_quality":None,"safety_score":None,
            "limitations":"Mocked data boundary; generic signals only, not validated record-level detection. No total score or production claims."}

if __name__=="__main__":
    print(json.dumps(run(),indent=2))
