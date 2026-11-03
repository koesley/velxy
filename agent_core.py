"""VELXTRIA agent coordinator v1: deterministic, approval-gated, no outbound actions.

Uses the portal's existing database connection (SQLite or PostgreSQL adapter).
Never sends email, discovers contacts, charges money, or deploys code.
"""
import json
import secrets
import time

STAGES = ('research', 'draft', 'review', 'fulfillment')

def setup(c):
    c.execute('CREATE TABLE IF NOT EXISTS agent_control (id INTEGER PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 1)')
    c.execute('INSERT INTO agent_control (id,paused) SELECT 1,1 WHERE NOT EXISTS (SELECT 1 FROM agent_control WHERE id=1)')
    c.execute('CREATE TABLE IF NOT EXISTS agent_tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, draft TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS agent_audit (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, event TEXT NOT NULL, created INTEGER NOT NULL)')

def audit(c, task_id, event):
    c.execute('INSERT INTO agent_audit (id,task_id,event,created) VALUES (?,?,?,?)',(secrets.token_hex(12),task_id,event,int(time.time())))

def paused(c):
    return bool(c.execute('SELECT paused FROM agent_control WHERE id=1').fetchone()[0])

def set_paused(c, value):
    c.execute('UPDATE agent_control SET paused=? WHERE id=1',(int(bool(value)),))
    audit(c,'system','paused' if value else 'resumed')

def create(c,title):
    title=title.strip()
    if not 3 <= len(title) <= 160: raise ValueError('Task title must be 3–160 characters')
    ident=secrets.token_hex(12); t=int(time.time())
    c.execute('INSERT INTO agent_tasks (id,title,stage,status,draft,created,updated) VALUES (?,?,?,?,?,?,?)',(ident,title,'research','queued','',t,t))
    audit(c,ident,'created')
    return ident

def tick(c,ident):
    """Advance one internal simulation step. Review requires explicit approval."""
    if paused(c): raise ValueError('Agents are paused')
    row=c.execute('SELECT title,stage,status FROM agent_tasks WHERE id=?',(ident,)).fetchone()
    if not row: raise ValueError('Task not found')
    title,stage,status=row
    if status in ('awaiting_approval','complete','rejected'): raise ValueError('Task requires approval or is finished')
    if stage=='research':
        # No external data is accessed. This is an internal planning note only.
        draft='Planning brief for: '+title+'\nVerify customer need and permission before outreach. No leads have been discovered.'
        next_stage='draft'; next_status='queued'
    elif stage=='draft':
        draft='DRAFT ONLY — NOT SENT\nSubject: A question about your reporting workflow\nHello, would a simpler sales reporting workflow be useful for your team?\nPlease let me know if you would like details.\n\nReview recipient eligibility, claims, and consent before any sending.'
        next_stage='review'; next_status='awaiting_approval'
    else: raise ValueError('Unsupported stage')
    c.execute('UPDATE agent_tasks SET stage=?,status=?,draft=?,updated=? WHERE id=?',(next_stage,next_status,draft,int(time.time()),ident))
    audit(c,ident,'advanced_to_'+next_stage)

def decide(c,ident,approved):
    row=c.execute('SELECT stage,status FROM agent_tasks WHERE id=?',(ident,)).fetchone()
    if not row or row!=('review','awaiting_approval'): raise ValueError('No draft awaiting approval')
    # Approval only marks a draft reviewed; it does not authorize a real send.
    c.execute('UPDATE agent_tasks SET stage=?,status=?,updated=? WHERE id=?',('fulfillment','complete' if approved else 'rejected',int(time.time()),ident))
    audit(c,ident,'draft_approved_no_send' if approved else 'draft_rejected')

def tasks(c):
    return c.execute('SELECT id,title,stage,status,draft FROM agent_tasks ORDER BY created DESC LIMIT 30').fetchall()
