"""V5.5 Ascendancy: owner-entered evidence and auditable local-first mission plans."""
import html, secrets, time
import mission_v52, mission_v53

def e(value):return html.escape(str(value),quote=True)
def setup(c):
    c.execute('''CREATE TABLE IF NOT EXISTS vx55_outcomes (id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, user_id INTEGER NOT NULL, action_id TEXT NOT NULL, outcome TEXT NOT NULL, evidence TEXT NOT NULL, created_at INTEGER NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS vx55_outcomes_scope ON vx55_outcomes(user_id,mission_id,created_at)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx55_preferences (user_id INTEGER PRIMARY KEY, notes TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL)''')

def record(c,uid,mid,aid,outcome,evidence):
    _,_,status=mission_v53.mission(c,uid,mid)
    if status!='active':raise ValueError('Mission must be active to record an outcome.')
    action=c.execute("SELECT kind,status FROM vx53_actions WHERE id=? AND mission_id=? AND user_id=?",(aid,mid,uid)).fetchone()
    if not action or action[1]!='executed':raise ValueError('Select an executed action belonging to this mission.')
    allowed={'draft_prepared','contacted','replied','objective_achieved','no_response','needs_followup'}
    if outcome not in allowed:raise ValueError('Select a valid outcome.')
    evidence=evidence.strip()
    if not 8<=len(evidence)<=1000:raise ValueError('Enter 8–1000 characters describing the evidence or observation.')
    if c.execute('SELECT 1 FROM vx55_outcomes WHERE user_id=? AND mission_id=? AND action_id=? AND outcome=? AND evidence=?',(uid,mid,aid,outcome,evidence)).fetchone():return False
    c.execute('INSERT INTO vx55_outcomes VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(16),mid,uid,aid,outcome,evidence,int(time.time())))
    mission_v52.event(c,uid,mid,'outcome_recorded','Owner recorded '+outcome.replace('_',' ')+' for an executed action. Evidence is owner-entered, not independently validated.')
    return True

def save_preferences(c,uid,notes):
    notes=notes.strip()
    if len(notes)>1200:raise ValueError('Business guidance must be 1200 characters or fewer.')
    c.execute('INSERT INTO vx55_preferences(user_id,notes,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET notes=excluded.notes,updated_at=excluded.updated_at',(uid,notes,int(time.time())))

def latest_outcomes(c,uid,mid):
    return c.execute('SELECT o.action_id,o.outcome,o.evidence,o.created_at FROM vx55_outcomes o WHERE o.user_id=? AND o.mission_id=? ORDER BY o.created_at DESC LIMIT 30',(uid,mid)).fetchall()

def plan(c,uid,mid):
    title,objective,status=mission_v53.mission(c,uid,mid)
    counts=mission_v53.counts(c,uid,mid)
    outcomes=latest_outcomes(c,uid,mid)
    scan_at,verified_at=c.execute('SELECT scan_at,verified_at FROM vx52_missions WHERE id=? AND user_id=?',(mid,uid)).fetchone()
    executed=counts.get('executed',0)
    labels=[('Observe business records',bool(scan_at),'Scan customer and site records; do not infer missing data.'),('Prepare and review proposals',bool(scan_at),'Edit drafts, reject unsuitable proposals, and approve only appropriate work.'),('Execute approved internal work',bool(executed),'Internal execution does not contact customers or establish revenue.'),('Verify workflow',bool(verified_at),'Review recorded actions and outstanding proposals.'),('Record observed outcomes',bool(outcomes),'Add owner-supplied evidence separately from workflow verification.')]
    if status!='active':next_step='Mission '+status+'. Review the existing records.'
    elif counts.get('approved',0):next_step='Execute or reconsider the approved internal proposals.'
    elif counts.get('pending',0):next_step='Review pending proposals and edit drafts before approval.'
    elif not scan_at:next_step='Run a mission scan to prepare proposals from existing records.'
    elif not executed:next_step='No internal actions executed yet. Review available records and proposals.'
    elif not verified_at:next_step='Verify workflow progress in Mission Control.'
    elif not outcomes:next_step='Record an observed outcome. Saving a draft is not customer contact.'
    elif any(x[1]=='needs_followup' for x in outcomes):next_step='Review the recorded follow-up need and decide on the next approved action.'
    else:next_step='Review outcome evidence and decide whether the objective is achieved.'
    return labels,next_step

def render(c,uid,mid,csrf):
    labels,next_step=plan(c,uid,mid)
    outcomes=latest_outcomes(c,uid,mid)
    actions=c.execute("SELECT id,kind,payload FROM vx53_actions WHERE user_id=? AND mission_id=? AND status='executed' ORDER BY executed_at DESC LIMIT 50",(uid,mid)).fetchall()
    notes_row=c.execute('SELECT notes FROM vx55_preferences WHERE user_id=?',(uid,)).fetchone()
    notes=notes_row[0] if notes_row else ''
    tok='<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="mission_id" value="'+e(mid)+'">'
    out=['<section class="panel v54-panel"><p class="eyebrow">ASCENDANCY / EVIDENCE-BASED MISSION PLAN</p><h2>Next meaningful action</h2><p class="v54-next">'+e(next_step)+'</p><ol class="mission-steps">']
    for label,done,explanation in labels:out.append('<li><strong>'+('✓ ' if done else '○ ')+e(label)+'</strong><p class="mission-note">'+e(explanation)+'</p></li>')
    out.append('</ol><p class="mission-note">This is a deterministic, local-first plan based on recorded state, not an AI model or an autonomous scheduler.</p></section>')
    out.append('<section class="panel"><h2>Outcome evidence</h2><p>Record what actually happened. These are your observations, not independently confirmed results. No emails or messages are sent.</p>')
    if actions:
        out.append('<form method="post" action="/mission-actions" class="v54-draft">'+tok+'<input type="hidden" name="action" value="record_outcome"><label>Executed action<select name="proposal_id" required>')
        for aid,kind,payload in actions:out.append('<option value="'+e(aid)+'">'+e(kind.replace('_',' ').title()+': '+payload[:90])+'</option>')
        out.append('</select></label><label>Observed result<select name="outcome" required><option value="draft_prepared">Draft prepared (not sent)</option><option value="contacted">Customer contacted (owner reported)</option><option value="replied">Customer replied (owner reported)</option><option value="needs_followup">Follow-up needed</option><option value="no_response">No response observed</option><option value="objective_achieved">Objective achieved (owner reported)</option></select></label><label>Evidence or observation<textarea name="evidence" rows="3" maxlength="1000" required placeholder="Describe the actual observation, date, and where evidence can be checked."></textarea></label><button>Record observed outcome</button></form>')
    else:out.append('<p>Execute an approved internal mission action before recording an outcome.</p>')
    if outcomes:
        out.append('<h3>Recorded outcomes</h3><ul class="v54-timeline">')
        for aid,outcome,evidence,ts in outcomes:out.append('<li><strong>'+e(outcome.replace('_',' ').title())+'</strong> · '+e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(ts)))+'<p>'+e(evidence)+'</p></li>')
        out.append('</ul>')
    out.append('</section><section class="panel"><h2>Persistent business guidance</h2><p>Optional account-level guidance for your own review. This is not automatically interpreted by an AI model and is not separated by company.</p><form method="post" action="/mission-actions" class="v54-draft">'+tok+'<input type="hidden" name="action" value="save_guidance"><label>Business notes<textarea name="notes" rows="4" maxlength="1200">'+e(notes)+'</textarea></label><button class="secondary-button">Save guidance</button></form></section>')
    return ''.join(out)
