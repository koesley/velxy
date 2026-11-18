"""Safe, read-only executive queue for OMNISCIENCE.

Designed for embedding behind the portal's existing authentication boundary.
No POST handlers, external actions, or client-provided account identifiers.
"""
import html
import omniscience_crm_bridge as bridge
import omniscience_evidence as ledger

def esc(value):
    return html.escape(str(value),quote=True)

def dashboard(c,owner,csrf=''):
    if type(owner) is not int or owner<1:
        raise ValueError("Authenticated account required")
    ledger.setup(c)
    items=bridge.candidates(c,owner)
    saved=c.execute("""SELECT r.id,r.objective,r.condition,r.intervention,
       e.reliability,e.source_type,e.source_id,r.created_at,r.expires_at
       FROM omnis_recommendations r JOIN omnis_evidence e
       ON e.id=r.evidence_id AND e.owner_id=r.owner_id
       WHERE r.owner_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 100""",
       (owner,)).fetchall()
    out=['<section class="hero"><h1>OMNISCIENCE Decision Workspace</h1>',
         '<p>Evidence-backed CRM signals for human review. No automatic outreach or payment actions.</p></section>',
         '<section class="panel"><h2>Current opportunities</h2>',
         '<p>Rule-based priorities are not probabilities. Pipeline values are not received revenue.</p>']
    for item in items:
        out.extend(('<article><h3>',esc(item["objective"]),'</h3><p>Priority ',
                    esc(item["priority"]),' / 100 · ',esc(item["payload"]["signal"]),
                    '</p><p>Evidence: ',esc(item["condition"]),
                    '</p><p>Recommended next step: ',esc(item["intervention"]),
                    '</p><p>Source: CRM · Reliability: inference · ',
                    esc(item["limitations"]),'</p><p><a href="',
                    esc(item["target"]),'">Review in existing workspace</a></p></article>'))
    if not items:
        out.append('<p>No actionable aging CRM records for this account.</p>')
    if csrf:
        for item in items:
            out.extend(('<form method="post" action="/omniscience-save"><input type="hidden" name="csrf" value="',
                        esc(csrf),'"><input type="hidden" name="source_id" value="',
                        esc(item["source_id"]),'"><button type="submit">Save for review</button></form>'))
    out.append('</section><section class="panel"><h2>Recorded decisions</h2>')
    for rid,objective,condition,intervention,reliability,source_type,source_id,created,expires in saved:
        events=c.execute("""SELECT choice,rationale,created_at
            FROM omnis_decision_events WHERE owner_id=? AND recommendation_id=?
            ORDER BY created_at,id""",(owner,rid)).fetchall()
        out.extend(('<article><h3>',esc(objective),'</h3><p>Evidence: ',
                    esc(source_type),' / ',esc(source_id),' · ',
                    esc(reliability),'</p><p>Condition: ',esc(condition),
                    '</p><p>Suggested intervention: ',esc(intervention),'</p>'))
        for choice,rationale,at in events:
            out.extend(('<p>Decision: ',esc(choice),' · ',esc(rationale),
                        ' · ',esc(at),'</p>'))
        if not events:
            out.append('<p>Awaiting human decision</p>')
        if csrf and (expires is None or expires > __import__('time').time()):
            out.extend(('<form method="post" action="/omniscience-decision">',
                        '<input type="hidden" name="csrf" value="',esc(csrf),
                        '"><input type="hidden" name="recommendation_id" value="',esc(rid),
                        '"><label>Decision<select name="choice">',
                        '<option value="accept">Accept for manual follow-up</option>',
                        '<option value="defer">Defer</option>',
                        '<option value="dismiss">Dismiss</option></select></label>',
                        '<label>Reason<input name="rationale" required maxlength="1000"></label>',
                        '<button type="submit">Record decision</button></form>'))
        out.append('</article>')
    if not saved:
        out.append('<p>No recorded recommendations yet.</p>')
    out.append('</section>')
    return ''.join(out)
