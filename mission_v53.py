"""V5.3: scoped, approval-gated local mission actions. No external side effects."""
import html, secrets, time

def e(x): return html.escape(str(x),quote=True)
def setup(c):
    c.execute('''CREATE TABLE IF NOT EXISTS vx53_actions (id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,user_id INTEGER NOT NULL,company_id TEXT NOT NULL DEFAULT '',kind TEXT NOT NULL,target_id TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL,executed_at INTEGER NOT NULL DEFAULT 0,result TEXT NOT NULL DEFAULT '',UNIQUE(mission_id,kind,target_id,payload))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx53_actions_scope ON vx53_actions(user_id,mission_id,status)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx53_site_history (id TEXT PRIMARY KEY,action_id TEXT NOT NULL,user_id INTEGER NOT NULL,company_id TEXT NOT NULL,old_headline TEXT NOT NULL,new_headline TEXT NOT NULL,created_at INTEGER NOT NULL,restored_at INTEGER NOT NULL DEFAULT 0)''')

def mission(c,uid,mid):
    row=c.execute('SELECT title,objective,status FROM vx52_missions WHERE id=? AND user_id=?',(mid,uid)).fetchone()
    if not row:raise ValueError('Mission not found.')
    return row

def scan(c,uid,mid):
    title,objective,status=mission(c,uid,mid)
    if status!='active':raise ValueError('Mission must be active.')
    words=(title+' '+objective).lower()
    crm=any(w in words for w in ('customer','lead','follow-up','follow up','crm','sales','contact'))
    site=any(w in words for w in ('website','site','headline','landing','web page','webpage','fashion','storefront'))
    if not (crm or site):raise ValueError('This version supports customer/lead missions and website missions. Specify one of those goals in the mission title or objective.')
    made=0
    if crm:
        for cid,name,email,stage in c.execute("SELECT id,name,email,stage FROM vx3_contacts WHERE user_id=? AND stage IN ('lead','qualified') ORDER BY created_at DESC LIMIT 25",(uid,)).fetchall():
            payload='Follow-up draft for '+name+': Thank you for your interest. Would you like to learn more about our products or services?'
            made+=add(c,uid,mid,'crm_draft',cid,payload)
    if site:
        companies=c.execute('SELECT c.id,c.name,s.headline FROM vx_companies c JOIN vx_sites s ON c.id=s.company_id WHERE c.owner_id=? ORDER BY c.created DESC LIMIT 20',(uid,)).fetchall() if table_exists(c,'vx_companies') else []
        for cid,name,headline in companies:
            # Explicit draft proposal: no fabricated business performance claims or autonomous copy changes.
            payload='Explore '+name+' — Discover what makes us different'
            if headline!=payload:made+=add(c,uid,mid,'site_headline',cid,payload,company_id=cid)
    c.execute('UPDATE vx52_missions SET scan_at=? WHERE id=? AND user_id=?',(int(time.time()),mid,uid))
    import mission_v52
    mission_v52.event(c,uid,mid,'scanned',f'Mission-specific check prepared {made} new proposals; no account-wide operator proposals created.')
    return made

def table_exists(c,name):
    try:c.execute('SELECT 1 FROM '+name+' LIMIT 1');return True
    except Exception:return False

def add(c,uid,mid,kind,target,payload,company_id=''):
    # Avoid repeatedly proposing the same contact or site target after a draft edit.
    if c.execute('SELECT 1 FROM vx53_actions WHERE mission_id=? AND user_id=? AND kind=? AND target_id=?',(mid,uid,kind,target)).fetchone():return 0
    c.execute('INSERT INTO vx53_actions(id,mission_id,user_id,company_id,kind,target_id,payload,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)',(secrets.token_hex(16),mid,uid,company_id,kind,target,payload,'pending',int(time.time())))
    return 1

def act(c,uid,mid,aid,operation):
    _,_,state=mission(c,uid,mid)
    if state!='active':raise ValueError('Mission is not active.')
    row=c.execute('SELECT kind,target_id,payload,status,company_id FROM vx53_actions WHERE id=? AND mission_id=? AND user_id=?',(aid,mid,uid)).fetchone()
    if not row:raise ValueError('Action not found.')
    kind,target,payload,status,cid=row
    if operation=='reject':
        if status!='pending':raise ValueError('Only pending proposals can be rejected.')
        c.execute("UPDATE vx53_actions SET status='rejected' WHERE id=? AND user_id=?",(aid,uid))
        import mission_v52
        mission_v52.event(c,uid,mid,'rejected','Owner rejected a '+kind+' proposal.');return
    if operation=='approve':
        if status!='pending':raise ValueError('Only pending proposals can be approved.')
        c.execute("UPDATE vx53_actions SET status='approved' WHERE id=? AND user_id=?",(aid,uid))
        import mission_v52
        mission_v52.event(c,uid,mid,'approved','Owner approved a '+kind+' proposal; no external action taken.');return
    if operation!='execute' or status!='approved':raise ValueError('Approve the action before execution.')
    if kind=='crm_draft':
        contact=c.execute('SELECT name,email FROM vx3_contacts WHERE id=? AND user_id=?',(target,uid)).fetchone()
        if not contact:raise ValueError('Contact no longer exists.')
        # Save draft as an internal artifact, never send or change contact stage.
        result='Saved internal draft for '+contact[0]+'. No email sent.'
    elif kind=='site_headline':
        site=c.execute('SELECT s.headline FROM vx_sites s JOIN vx_companies c ON c.id=s.company_id WHERE s.company_id=? AND c.owner_id=?',(cid,uid)).fetchone()
        if not site:raise ValueError('Private website draft not found or access denied.')
        c.execute('INSERT INTO vx53_site_history VALUES (?,?,?,?,?,?,?,?)',(secrets.token_hex(16),aid,uid,cid,site[0],payload,int(time.time()),0))
        c.execute('UPDATE vx_sites SET headline=?,updated=? WHERE company_id=?',(payload,int(time.time()),cid))
        result='Private website draft headline updated. Not published.'
    else:raise ValueError('Unsupported action.')
    c.execute("UPDATE vx53_actions SET status='executed',executed_at=?,result=? WHERE id=? AND user_id=? AND status='approved'",(int(time.time()),result,aid,uid))
    import mission_v52
    mission_v52.event(c,uid,mid,'executed',result)


def edit_draft(c,uid,mid,aid,new_text):
    """Edit a pending internal draft; never contact customers."""
    _,_,mission_state=mission(c,uid,mid)
    if mission_state!='active':raise ValueError('Mission must be active.')
    row=c.execute('SELECT kind,target_id,status FROM vx53_actions WHERE id=? AND user_id=? AND mission_id=?',(aid,uid,mid)).fetchone()
    if not row or row[0]!='crm_draft' or row[2]!='pending':raise ValueError('Only pending customer drafts can be edited.')
    text=new_text.strip()
    if not 10<=len(text)<=1200:raise ValueError('Draft must be between 10 and 1200 characters.')
    if not c.execute('SELECT 1 FROM vx3_contacts WHERE id=? AND user_id=?',(row[1],uid)).fetchone():raise ValueError('Customer no longer exists.')
    c.execute('UPDATE vx53_actions SET payload=? WHERE id=? AND user_id=? AND mission_id=?',(text,aid,uid,mid))
    import mission_v52
    mission_v52.event(c,uid,mid,'draft_edited','Owner edited a pending internal follow-up draft; no message was sent.')

def mission_insights(c,uid,mid):
    """Evidence-based mission-specific state; never claims revenue impact."""
    title,objective,status=mission(c,uid,mid)
    counts_map=counts(c,uid,mid)
    pending=counts_map.get('pending',0)
    approved=counts_map.get('approved',0)
    executed=counts_map.get('executed',0)
    rejected=counts_map.get('rejected',0)
    if status!='active':next_step='Mission is '+status+'. Resume it to continue.' if status=='paused' else 'Mission has been marked complete.'
    elif approved:next_step=f'Execute {approved} approved internal action(s).'
    elif pending:next_step=f'Review {pending} pending proposal(s). Edit customer drafts before approval if needed.'
    elif executed:next_step='Verify progress in Mission Control. Check outcomes before marking complete.'
    else:next_step='Run a mission scan. Add relevant business records if no proposals are found.'
    return dict(pending=pending,approved=approved,executed=executed,rejected=rejected,next_step=next_step)

def restore(c,uid,mid,aid):
    mission(c,uid,mid)
    row=c.execute('SELECT h.id,h.company_id,h.old_headline,h.new_headline FROM vx53_site_history h JOIN vx53_actions a ON a.id=h.action_id WHERE h.action_id=? AND a.mission_id=? AND h.user_id=? AND h.restored_at=0',(aid,mid,uid)).fetchone()
    if not row:raise ValueError('No active snapshot to restore.')
    hid,cid,old,new=row
    current=c.execute('SELECT s.headline FROM vx_sites s JOIN vx_companies c ON c.id=s.company_id WHERE c.id=? AND c.owner_id=?',(cid,uid)).fetchone()
    if not current or current[0]!=new:raise ValueError('Draft changed since execution. Restore manually in Site Studio to avoid overwriting newer edits.')
    c.execute('UPDATE vx_sites SET headline=?,updated=? WHERE company_id=?',(old,int(time.time()),cid))
    c.execute('UPDATE vx53_site_history SET restored_at=? WHERE id=?',(int(time.time()),hid))
    import mission_v52
    mission_v52.event(c,uid,mid,'restored','Previous private website headline restored.')

def counts(c,uid,mid):
    return {s:n for s,n in c.execute('SELECT status,COUNT(*) FROM vx53_actions WHERE user_id=? AND mission_id=? GROUP BY status',(uid,mid)).fetchall()}

def render(c,uid,mid,csrf):
    title,objective,status=mission(c,uid,mid)
    tok='<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="mission_id" value="'+e(mid)+'">'
    insight=mission_insights(c,uid,mid)
    out=['<section class="hero"><p class="eyebrow">VELXTRIA V5.5 / ASCENDANCY ACTIONS</p><h1>'+e(title)+'</h1><p>'+e(objective)+'</p><p>Mission-specific proposals. Customer follow-ups are saved as internal drafts. Website edits affect private drafts only.</p></section>', '<section class="panel"><h2>Mission-specific operator</h2><form method="post" action="/mission-actions">'+tok+'<button name="action" value="scan">Scan this mission</button></form></section>', '<section class="panel"><h2>Mission proposals</h2>']
    out.insert(1,'<section class="panel v54-panel"><p class="eyebrow">OVERMIND / MISSION INTELLIGENCE</p><h2>Next best step</h2><p class="v54-next">'+e(insight['next_step'])+'</p><div class="v54-stats">'+''.join('<div><strong>'+str(insight[key])+'</strong><span>'+key.title()+'</span></div>' for key in ('pending','approved','executed','rejected'))+'</div><p class="mission-note">Counts are based on this mission&#39;s recorded actions, not business revenue or customer responses.</p></section>')
    import mission_v55
    out.insert(2,mission_v55.render(c,uid,mid,csrf))
    rows=c.execute('SELECT id,kind,target_id,payload,status,result,company_id FROM vx53_actions WHERE mission_id=? AND user_id=? ORDER BY created_at DESC LIMIT 100',(mid,uid)).fetchall()
    if not rows:out.append('<p>No mission-specific proposals yet. Run the scan. Add CRM leads or create a website in Site Studio if needed.</p>')
    for aid,kind,target,payload,state,result,cid in rows:
        name='Customer follow-up draft' if kind=='crm_draft' else 'Private website headline change'
        out.append('<article class="proposal-card"><h3>'+name+'</h3><p>'+e(payload)+'</p><p><small>Status: '+e(state)+'</small></p>')
        if result:out.append('<p>'+e(result)+'</p>')
        if state=='pending' and kind=='crm_draft':
            out.append('<form class="v54-draft" method="post" action="/mission-actions">'+tok+'<input type="hidden" name="proposal_id" value="'+e(aid)+'"><label>Edit internal follow-up draft<textarea name="draft_text" rows="4" maxlength="1200" required>'+e(payload)+'</textarea></label><button name="action" value="edit_draft" class="secondary-button">Save draft changes</button></form>')
        if state in ('pending','approved'):
            out.append('<div class="action-row">')
            for op,label in ([('approve','Approve'),('reject','Reject')] if state=='pending' else [('execute','Execute approved action')]):
                out.append('<form method="post" action="/mission-actions">'+tok+'<input type="hidden" name="proposal_id" value="'+e(aid)+'"><button name="action" value="'+op+'" class="'+('secondary-button' if op=='reject' else '')+'">'+label+'</button></form>')
            out.append('</div>')
        if state=='executed' and kind=='site_headline':
            snapshot=c.execute('SELECT restored_at FROM vx53_site_history WHERE action_id=? AND user_id=?',(aid,uid)).fetchone()
            if snapshot and not snapshot[0]:out.append('<form method="post" action="/mission-actions">'+tok+'<input type="hidden" name="proposal_id" value="'+e(aid)+'"><button class="secondary-button" name="action" value="restore">Restore previous draft headline</button></form>')
            out.append('<p><a href="/site-preview?id='+e(cid)+'" target="_blank" rel="noopener">View private website preview</a></p>')
        out.append('</article>')
    out.append('</section><section class="panel"><h2>Mission activity log</h2><p>Only events for this mission are shown. No emails are sent and no websites are published.</p><ul class="v54-timeline">')
    for kind,detail,ts in c.execute('SELECT event,detail,created_at FROM vx52_mission_events WHERE user_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 30',(uid,mid)).fetchall():
        out.append('<li><strong>'+e(kind.replace('_',' ').title())+'</strong><small>'+e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(ts)))+'</small><p>'+e(detail)+'</p></li>')
    out.append('</ul></section>')
    return ''.join(out)
