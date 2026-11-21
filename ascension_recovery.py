"""Revenue recovery ledger: measured outcomes, not inferred or promised revenue.

Records user-attested evidence, separate from verified payment receipts.
"""
import html
import secrets
import time
import sales_pipeline
import sovereign_ascension

def esc(value):
    return html.escape(str(value),quote=True)

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS ascension_recovery_outcomes (
        id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, action_id TEXT NOT NULL,
        outcome TEXT NOT NULL, amount_cents INTEGER NOT NULL DEFAULT 0,
        evidence TEXT NOT NULL, created_at INTEGER NOT NULL,
        UNIQUE(owner_id,action_id))""")
    c.execute("CREATE INDEX IF NOT EXISTS ascension_recovery_owner ON ascension_recovery_outcomes(owner_id,created_at)")

def record(c,owner,action_id,outcome,amount,evidence):
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    setup(c)
    if outcome not in ("no_response","responded","meeting_booked","deal_won_unverified","payment_reported"):
        raise ValueError("Invalid outcome")
    action=c.execute("""SELECT id FROM ascension_actions WHERE id=? AND owner_id=?
        AND status='completed'""",(action_id,owner)).fetchone()
    if not action:
        raise ValueError("Complete an approved action before recording its outcome")
    try:
        from decimal import Decimal, InvalidOperation
        money=Decimal(str(amount or "0"))
        if not money.is_finite() or money<0 or money>100000000 or money.as_tuple().exponent < -2:
            raise ValueError("Amount must be a nonnegative value with at most two decimal places")
        cents=int(money*100)
    except (InvalidOperation,TypeError):
        raise ValueError("Invalid amount")
    if outcome!="payment_reported" and cents:
        raise ValueError("Only a reported payment can have a received amount")
    if outcome=="payment_reported" and (cents<=0 or len(evidence.strip())<12):
        raise ValueError("Reported payments require an amount and evidence")
    if len(evidence)>500:
        raise ValueError("Evidence too long")
    ident=secrets.token_hex(12)
    try:
        c.execute("""INSERT INTO ascension_recovery_outcomes
            VALUES (?,?,?,?,?,?,?)""",(ident,owner,action_id,outcome,cents,evidence.strip(),int(time.time())))
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError("An outcome has already been recorded for this action")
        raise
    return ident

def dashboard(c,owner,csrf):
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    setup(c)
    rows=c.execute("""SELECT o.outcome,o.amount_cents,o.evidence,l.business
        FROM ascension_recovery_outcomes o
        JOIN ascension_actions a ON a.id=o.action_id AND a.owner_id=o.owner_id
        JOIN sales_pipeline_leads l ON l.id=a.lead_id AND l.owner_id=a.owner_id
        WHERE o.owner_id=? ORDER BY o.created_at DESC LIMIT 100""",(owner,)).fetchall()
    pending=c.execute("""SELECT a.id,l.business,a.kind
        FROM ascension_actions a JOIN sales_pipeline_leads l
        ON l.id=a.lead_id AND l.owner_id=a.owner_id
        WHERE a.owner_id=? AND a.status='completed'
        AND NOT EXISTS (SELECT 1 FROM ascension_recovery_outcomes o
                        WHERE o.action_id=a.id AND o.owner_id=a.owner_id)
        ORDER BY a.updated_at DESC LIMIT 100""",(owner,)).fetchall()
    # Aggregate the complete owner's ledger; the history preview is limited to 100.
    summary=c.execute("""SELECT COUNT(*),
      COALESCE(SUM(CASE WHEN outcome='payment_reported' THEN amount_cents ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN outcome='meeting_booked' THEN 1 ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN outcome='responded' THEN 1 ELSE 0 END),0)
      FROM ascension_recovery_outcomes WHERE owner_id=?""",(owner,)).fetchone()
    total_outcomes,reported,meetings,responses=(int(v or 0) for v in summary)
    reported_display=f"{reported//100:,}.{reported%100:02d}"
    parts=['<section class="hero"><h1>Revenue Recovery Outcomes</h1><p>Track what happened after approved CRM follow-ups. No outbound messages or financial transactions occur here.</p></section>']
    parts.append('<section class="panel"><h2>Outcome summary</h2><p>'+str(total_outcomes)+' recorded outcomes · $'+reported_display+' user-reported payments · '+str(meetings)+' meetings booked · '+str(responses)+' responses recorded</p><p>These amounts are self-reported and are NOT verified payment receipts, independently proven incremental revenue, or guaranteed VELXTRIA attribution.</p></section>')
    parts.append('<section class="panel"><h2>Completed actions awaiting outcomes</h2>')
    if not pending:
        parts.append('<p>No completed actions awaiting outcome entry.</p>')
    for action_id,business,kind in pending:
        parts.append('<article><h3>'+esc(business)+'</h3><p>'+esc(kind.replace('_',' '))+'</p><form method="post" action="/ascension-outcome"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action_id" value="'+esc(action_id)+'"><label>Outcome<select name="outcome"><option value="no_response">No response</option><option value="responded">Responded</option><option value="meeting_booked">Meeting booked</option><option value="deal_won_unverified">Deal won (unverified)</option><option value="payment_reported">Payment reported (unverified)</option></select></label><label>Reported payment USD (only for payment reported)<input name="amount" value="0"></label><label>Evidence / notes<input name="evidence" maxlength="500"></label><button type="submit">Record outcome</button></form></article>')
    parts.append('</section><section class="panel"><h2>Recent outcome history (latest 100)</h2>')
    for outcome,amount,evidence,business in rows:
        parts.append('<article><strong>'+esc(business)+'</strong> — '+esc(outcome.replace('_',' '))+' · $'+f"{amount//100:,}.{amount%100:02d}"+' reported<p>'+esc(evidence)+'</p></article>')
    parts.append('</section>')
    return ''.join(parts)
