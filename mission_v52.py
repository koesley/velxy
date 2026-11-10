"""V5.2 Mission Control: local, account-scoped goal tracking linked to operator activity."""
import html, secrets, time
import operator_v5

def e(v): return html.escape(str(v),quote=True)
def setup(c):
    c.execute('''CREATE TABLE IF NOT EXISTS vx52_missions (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,title TEXT NOT NULL,objective TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at INTEGER NOT NULL,baseline_scan INTEGER NOT NULL DEFAULT 0,baseline_executions INTEGER NOT NULL DEFAULT 0,scan_at INTEGER NOT NULL DEFAULT 0,verified_at INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx52_missions_user ON vx52_missions(user_id,created_at)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx52_mission_events (id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,user_id INTEGER NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL,created_at INTEGER NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS vx52_mission_events_user ON vx52_mission_events(user_id,mission_id,created_at)')

def event(c,uid,mid,kind,detail):
    c.execute('INSERT INTO vx52_mission_events VALUES (?,?,?,?,?,?)',(secrets.token_hex(16),mid,uid,kind,detail,int(time.time())))

def count_executions(c,uid):
    return c.execute('SELECT COUNT(*) FROM vx51_executions WHERE user_id=?',(uid,)).fetchone()[0]

def create(c,uid,title,objective):
    title=title.strip(); objective=objective.strip()
    if not (3<=len(title)<=100 and 3<=len(objective)<=600):raise ValueError('Enter a mission title (3–100 characters) and objective (3–600 characters).')
    mid=secrets.token_hex(16); now=int(time.time()); baseline=count_executions(c,uid)
    c.execute('INSERT INTO vx52_missions(id,user_id,title,objective,status,created_at,baseline_executions) VALUES (?,?,?,?,?,?,?)',(mid,uid,title,objective,'active',now,baseline))
    event(c,uid,mid,'created','Mission created. No automated actions have been run.')

def action(c,uid,mid,kind):
    row=c.execute('SELECT status,scan_at,baseline_executions,verified_at FROM vx52_missions WHERE id=? AND user_id=?',(mid,uid)).fetchone()
    if not row:raise ValueError('Mission not found.')
    status,scan_at,baseline,verified=row
    if kind=='pause' and status=='active':
        c.execute("UPDATE vx52_missions SET status='paused' WHERE id=? AND user_id=?",(mid,uid));event(c,uid,mid,'paused','Mission paused; no scheduled activity exists.')
    elif kind=='resume' and status=='paused':
        c.execute("UPDATE vx52_missions SET status='active' WHERE id=? AND user_id=?",(mid,uid));event(c,uid,mid,'resumed','Mission resumed.')
    elif kind=='scan' and status=='active':
        import mission_v53
        made=mission_v53.scan(c,uid,mid)
        now=int(time.time())
        c.execute('UPDATE vx52_missions SET scan_at=? WHERE id=? AND user_id=?',(now,mid,uid))
        event(c,uid,mid,'scanned',f'{made} mission-specific proposals prepared. Review them in Mission Actions.')
    elif kind=='verify' and status=='active':
        if not scan_at:raise ValueError('Run a mission scan first.')
        import mission_v53
        counts=mission_v53.counts(c,uid,mid)
        executions=counts.get('executed',0)
        pending=counts.get('pending',0)+counts.get('approved',0)
        detail=f'Verification: {executions} mission-specific actions executed; {pending} proposals still awaiting execution. This is not proof of increased revenue.'
        if not verified:
            c.execute('UPDATE vx52_missions SET verified_at=? WHERE id=? AND user_id=?',(int(time.time()),mid,uid))
            event(c,uid,mid,'verified',detail)
    elif kind=='complete' and status=='active':
        if not verified:raise ValueError('Verify the mission before marking it complete.')
        c.execute("UPDATE vx52_missions SET status='completed' WHERE id=? AND user_id=?",(mid,uid))
        event(c,uid,mid,'completed','Owner marked mission complete. Business outcomes were not independently validated.')
    else:raise ValueError('This action is not available for the current mission status.')

def render(c,uid,csrf):
    missions=c.execute('SELECT id,title,objective,status,created_at,scan_at,baseline_executions,verified_at FROM vx52_missions WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    token='<input type="hidden" name="csrf" value="'+e(csrf)+'">'
    out=['<section class="hero"><p class="eyebrow">VELXTRIA V5.5 / MISSION CONTROL</p><h1>Give your business a mission.</h1><p>Turn a goal into a trackable workflow. Mission scans create evidence-based proposals; you approve and execute internal actions in Business Operator. No automatic customer contact, purchases, or website publishing.</p></section>',
    '<section class="panel"><h2>Create a mission</h2><form method="post" action="/missions" class="mission-form">'+token+'<input type="hidden" name="action" value="create"><label>Mission name<input name="title" maxlength="100" placeholder="Improve Gerate customer follow-ups" required></label><label>Business objective<textarea name="objective" maxlength="600" rows="3" placeholder="Review new leads, prepare appropriate follow-ups, and track completed work." required></textarea></label><button>Create mission</button></form><p class="mission-note">Goals are recorded as text, not interpreted by a paid AI model. The operator currently uses fixed, auditable business rules.</p></section>',
    '<section class="panel"><h2>Mission board</h2><p class="mission-note">Verification is recorded once per mission. Review Activity history to see the result; repeat clicks will not duplicate the verification event.</p>']
    if not missions:out.append('<p>No missions yet. Create your first mission above.</p>')
    for mid,title,objective,status,created,scan_at,baseline,verified in missions:
        import mission_v53
        counts=mission_v53.counts(c,uid,mid)
        executions=counts.get('executed',0)
        progress=100 if status=='completed' else (75 if verified and executions else 50 if executions else 25 if scan_at else 0)
        out.append('<article class="mission-card"><div class="mission-top"><h3>'+e(title)+'</h3><span class="mission-status">'+e(status.title())+'</span></div><p>'+e(objective)+'</p><div class="mission-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+str(progress)+'"><span style="width:'+str(progress)+'%"></span></div><p class="mission-note">Workflow progress: '+str(progress)+'% · '+str(executions)+' mission-specific actions executed. This does not measure revenue impact.</p>')
        out.append('<ol class="mission-steps"><li>'+('✓ ' if scan_at else '○ ')+'Observe: scan recorded business data</li><li>'+('✓ ' if scan_at else '○ ')+'Plan: prepare operator proposals</li><li>◇ Approve and execute relevant actions in <a href="/operator">Business Operator</a></li><li>'+('✓ ' if verified else '○ ')+'Verify: review activity and recorded results</li></ol>')
        out.append('<div class="mission-actions">')
        available=([('scan','Run mission scan'),('verify','Verify progress'),('pause','Pause mission')] if status=='active' else [('resume','Resume mission')] if status=='paused' else [])
        if status=='active' and verified:available.append(('complete','Mark complete'))
        for action_name,label in available:
            out.append('<form method="post" action="/missions">'+token+'<input type="hidden" name="action" value="'+action_name+'"><input type="hidden" name="mission_id" value="'+e(mid)+'"><button class="'+('secondary-button' if action_name in ('pause','verify','complete') else '')+'">'+label+'</button></form>')
        out.append('<p><a href="/mission-actions?id='+e(mid)+'">Open mission-specific proposals and execution →</a></p></div>')
        events=c.execute('SELECT event,detail,created_at FROM vx52_mission_events WHERE user_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 5',(uid,mid)).fetchall()
        out.append('<details class="mission-history"><summary>Activity history</summary><ul>')
        for kind,detail,ts in events:out.append('<li><strong>'+e(kind)+'</strong> · '+e(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(ts)))+' — '+e(detail)+'</li>')
        out.append('</ul></details></article>')
    out.append('</section><section class="panel"><h2>What runs automatically?</h2><p>Nothing in the background yet. Mission scans are owner-triggered, and operator actions still require approval and execution. This is a persistent mission coordinator, not an unsupervised AI agent. CRM is account-wide; website draft edits are owner-scoped. Full per-company CRM separation is not yet implemented.</p></section>')
    return ''.join(out)
