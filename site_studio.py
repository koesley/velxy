"""Local-only, owner-scoped website drafts. No external services or publishing."""
import html, re, secrets, time, json

def e(value): return html.escape(str(value), quote=True)

def setup(c):
    c.execute("CREATE TABLE IF NOT EXISTS vx_companies (id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL, FOREIGN KEY(owner_id) REFERENCES users(id))")
    c.execute("CREATE TABLE IF NOT EXISTS vx_sites (company_id TEXT PRIMARY KEY, headline TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '', theme TEXT NOT NULL DEFAULT 'violet', updated INTEGER NOT NULL, FOREIGN KEY(company_id) REFERENCES vx_companies(id))")

    c.execute("CREATE TABLE IF NOT EXISTS vx_agent_proposals (id TEXT PRIMARY KEY, company_id TEXT NOT NULL, owner_id INTEGER NOT NULL, instruction TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created INTEGER NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS vx_site_sections (company_id TEXT NOT NULL, section_key TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, position INTEGER NOT NULL, PRIMARY KEY(company_id, section_key), FOREIGN KEY(company_id) REFERENCES vx_companies(id))")

def section_action(c, owner, company_id, action, fields):
    if not c.execute('SELECT 1 FROM vx_companies WHERE id=? AND owner_id=?',(company_id,owner)).fetchone():
        raise ValueError('Company not found')
    key=fields.get('section_key','')
    allowed=('services','gallery','testimonials','faq')
    if key not in allowed: raise ValueError('Invalid section type')
    if action=='remove_section':
        c.execute('DELETE FROM vx_site_sections WHERE company_id=? AND section_key=?',(company_id,key))
        return
    if action!='save_section':raise ValueError('Unknown action')
    title=fields.get('section_title','').strip()
    content=fields.get('section_content','').strip()
    if not 1<=len(title)<=100 or len(content)>2500:raise ValueError('Section title must be 1–100 characters; content max 2500')
    pos=allowed.index(key)
    c.execute('INSERT INTO vx_site_sections(company_id,section_key,title,content,position) VALUES (?,?,?,?,?) ON CONFLICT(company_id,section_key) DO UPDATE SET title=excluded.title,content=excluded.content,position=excluded.position',(company_id,key,title,content,pos))

def slugify(value): return re.sub(r'[^a-z0-9]+','-',value.lower()).strip('-')[:42]

def create(c,owner,name,description):
    name=name.strip()[:90]; description=description.strip()[:500]
    if not 2<=len(name)<=90: raise ValueError('Company name must be 2–90 characters')
    company_id=secrets.token_hex(12)
    slug=(slugify(name) or 'business')+'-'+company_id[:6]
    c.execute('INSERT INTO vx_companies (id,owner_id,name,slug,description,created) VALUES (?,?,?,?,?,?)',(company_id,owner,name,slug,description,int(time.time())))
    c.execute('INSERT INTO vx_sites (company_id,headline,body,theme,updated) VALUES (?,?,?,?,?)',(company_id,'Welcome to '+name,description,'violet',int(time.time())))

def update(c,owner,company_id,headline,body,theme):
    if theme not in ('violet','ocean','forest'): raise ValueError('Invalid theme')
    if not 1<=len(headline.strip())<=120 or len(body)>3000: raise ValueError('Headline must be 1–120 characters and description at most 3000')
    row=c.execute('SELECT id FROM vx_companies WHERE id=? AND owner_id=?',(company_id,owner)).fetchone()
    if not row: raise ValueError('Company not found')
    c.execute('UPDATE vx_sites SET headline=?,body=?,theme=?,updated=? WHERE company_id=?',(headline.strip(),body.strip(),theme,int(time.time()),company_id))

def studio(c,owner,csrf):
    rows=c.execute('SELECT c.id,c.name,c.slug,c.description,s.headline,s.body,s.theme FROM vx_companies c JOIN vx_sites s ON c.id=s.company_id WHERE c.owner_id=? ORDER BY c.created DESC',(owner,)).fetchall()
    out=['''<section class="studio-intro"><span class="studio-eyebrow">VELXTRIA / Site Studio</span><h1>Build something remarkable.</h1><p>Create and refine private website concepts for each company. No AI, public publishing, hosting subscriptions, or paid integrations are enabled.</p><span class="studio-chip">LOCAL DRAFT MODE</span></section>
    <section class="studio-panel"><h2>New company</h2><p class="hint">Create a workspace and start with a polished landing-page draft.</p><form class="studio-form" method="post" action="/site-studio">'''+ '<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="action" value="create"><label>Company name<input name="name" maxlength="90" placeholder="e.g. Gerate Studio" required></label><label>What does this company do?<textarea name="description" maxlength="500" placeholder="Describe its products, services and customers"></textarea></label><button>Create company</button></form></section>']
    for cid,name,slug,desc,headline,body,theme in rows:
        opts=''.join('<option value="'+x+'"'+(' selected' if theme==x else '')+'>'+x.title()+'</option>' for x in ('violet','ocean','forest'))
        out.append('<section class="studio-panel"><span class="studio-eyebrow">Website draft</span><h2>'+e(name)+'</h2><p class="hint">Edit the hero copy and color palette. Preview remains private to your account.</p><div class="studio-grid"><form class="studio-form" method="post" action="/site-studio"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="action" value="update"><input type="hidden" name="company_id" value="'+e(cid)+'"><label>Main headline<input name="headline" maxlength="120" required value="'+e(headline)+'"></label><label>Introduction / page text<textarea name="body" maxlength="3000">'+e(body)+'</textarea></label><label>Color theme<select name="theme">'+opts+'</select></label><button>Save draft</button></form><div><span class="studio-chip">LIVE CONCEPT</span><h3 class="studio-sample-headline">'+e(headline)+'</h3><p class="studio-sample-body">'+e(body)+'</p><div class="studio-actions"><a class="studio-preview-link" target="_blank" rel="noopener" href="/site-preview?id='+e(cid)+'">Open full preview ↗</a></div><p class="hint studio-save-hint">Save first to update the full preview. This is not a public website.</p></div></div></section>')
    for cid,name,slug,desc,headline,body,theme in rows:
        sections=c.execute('SELECT section_key,title,content FROM vx_site_sections WHERE company_id=? ORDER BY position',(cid,)).fetchall()
        existing={key:(title,content) for key,title,content in sections}
        out.append('<section class="studio-panel"><span class="studio-eyebrow">Page sections</span><h2>'+e(name)+' · Content blocks</h2><p class="hint">Choose a section, write its content, and save. These are private draft blocks, not a drag-and-drop editor.</p>')
        for key,label in [('services','Services / Products'),('gallery','Gallery captions'),('testimonials','Testimonials'),('faq','Frequently asked questions')]:
            title,content=existing.get(key,(label,''))
            out.append('<form class="studio-form section-editor" method="post" action="/site-studio"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="company_id" value="'+e(cid)+'"><input type="hidden" name="section_key" value="'+e(key)+'"><h3>'+e(label)+'</h3><label>Section heading<input maxlength="100" name="section_title" required value="'+e(title)+'"></label><label>Section text (separate items with new lines)<textarea maxlength="2500" name="section_content">'+e(content)+'</textarea></label><div class="studio-actions"><button name="action" value="save_section">Save section</button>'+(('<button class="section-remove" name="action" value="remove_section" formnovalidate>Remove section</button>') if key in existing else '')+'</div></form>')
        out.append('</section>')
    return ''.join(out)

def preview(c,owner,company_id):
    row=c.execute('SELECT c.name,s.headline,s.body,s.theme FROM vx_companies c JOIN vx_sites s ON c.id=s.company_id WHERE c.id=? AND c.owner_id=?',(company_id,owner)).fetchone()
    if not row:return None
    name,headline,body,theme=row
    paragraphs=''.join('<p>'+e(chunk).replace('\n','<br>')+'</p>' for chunk in body.split('\n\n') if chunk.strip()) or '<p>Welcome to our studio.</p>'
    sections=c.execute('SELECT section_key,title,content FROM vx_site_sections WHERE company_id=? ORDER BY position',(company_id,)).fetchall()
    section_html=''.join('<section class="content-section" id="'+e(key)+'"><div class="content-wrap"><span class="eyebrow">'+e(key)+'</span><h2>'+e(title)+'</h2>'+''.join('<p>'+e(line)+'</p>' for line in content.splitlines() if line.strip())+'</div></section>' for key,title,content in sections)
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>'''+e(name)+''' · Private draft</title><link rel="stylesheet" href="/site-preview.css"></head><body class="theme-'''+e(theme)+'''"><div class="notice">PRIVATE DRAFT PREVIEW · NOT PUBLISHED</div><nav class="nav"><a class="logo" href="#home">'''+e(name)+'''<span>✦</span></a><div class="navlinks"><a href="#home">Home</a><a href="#about">About</a><a href="#contact">Contact</a></div></nav><main id="home" class="hero"><div><div class="eyebrow">Crafted with VELXTRIA</div><h1>'''+e(headline)+'''</h1><div class="intro">'''+paragraphs+'''</div><div class="buttons"><a class="button" href="#contact">Explore our vision ↗</a><a class="button secondary" href="#about">Learn more</a></div></div><div class="art" role="img" aria-label="Abstract decorative geometric illustration"><div class="art-label">'''+e(name.upper())+''' / A NEW PERSPECTIVE</div></div></main>'''+section_html+'''<section class="details" id="about"><div class="details-inner"><div><span class="eyebrow">Our story</span><br><strong>Built around your vision.</strong></div><div id="contact"><span class="eyebrow">Get in touch</span><p class="contact-placeholder">Contact details coming soon.</p></div></div></section><footer>'''+e(name)+''' · Concept preview only · Powered by VELXTRIA</footer></body></html>'''

def agent_action(c,owner,company_id,action,fields):
    if not c.execute('SELECT 1 FROM vx_companies WHERE id=? AND owner_id=?',(company_id,owner)).fetchone():
        raise ValueError('Company not found')
    if action=='propose':
        instruction=fields.get('instruction','').strip()
        if not 1<=len(instruction)<=500: raise ValueError('Instruction must be 1–500 characters')
        # Intentionally constrained: no generative model, shell commands, network or automatic execution.
        match=re.fullmatch(r'(?:change|set|update) (?:the )?(?:website )?headline to (.+)',instruction,re.I|re.S)
        if match:
            value=match.group(1).strip()
            if not 1<=len(value)<=120:raise ValueError('Headline must be 1–120 characters')
            kind='headline';payload={'headline':value}
        else:
            match=re.fullmatch(r'(?:change|set|update) (?:the )?(?:website )?description to (.+)',instruction,re.I|re.S)
            if match:
                value=match.group(1).strip()
                if not 1<=len(value)<=3000:raise ValueError('Description too long')
                kind='description';payload={'body':value}
            else:
                match=re.fullmatch(r'(?:change|set|update) (?:the )?theme to (violet|ocean|forest)',instruction,re.I)
                if match:kind='theme';payload={'theme':match.group(1).lower()}
                else:raise ValueError('This free prototype understands: set headline to ..., set description to ..., or set theme to violet/ocean/forest.')
        c.execute('INSERT INTO vx_agent_proposals VALUES (?,?,?,?,?,?,?,?)',(secrets.token_hex(12),company_id,owner,instruction,kind,json.dumps(payload),'pending',int(time.time())))
        return
    if action not in ('approve_proposal','reject_proposal'):raise ValueError('Unknown agent action')
    pid=fields.get('proposal_id','')
    row=c.execute('SELECT action,payload FROM vx_agent_proposals WHERE id=? AND company_id=? AND owner_id=? AND status=?',(pid,company_id,owner,'pending')).fetchone()
    if not row:raise ValueError('Proposal not found or already decided')
    if action=='approve_proposal':
        kind,payload=row;data=json.loads(payload)
        if kind=='headline':c.execute('UPDATE vx_sites SET headline=?,updated=? WHERE company_id=?',(data['headline'],int(time.time()),company_id))
        elif kind=='description':c.execute('UPDATE vx_sites SET body=?,updated=? WHERE company_id=?',(data['body'],int(time.time()),company_id))
        elif kind=='theme':c.execute('UPDATE vx_sites SET theme=?,updated=? WHERE company_id=?',(data['theme'],int(time.time()),company_id))
        else:raise ValueError('Invalid proposal')
    c.execute('UPDATE vx_agent_proposals SET status=? WHERE id=? AND company_id=? AND owner_id=?',('approved' if action=='approve_proposal' else 'rejected',pid,company_id,owner))

def agent_workspace(c,owner,csrf):
    rows=c.execute('SELECT id,name FROM vx_companies WHERE owner_id=? ORDER BY created DESC',(owner,)).fetchall()
    out=['<section class="studio-intro"><span class="studio-eyebrow">VELXTRIA / AGENT WORKSPACE</span><h1>Business agent · local prototype</h1><p>Rule-based instructions only. No AI model, external requests, automatic publishing, or paid usage. Changes require your approval.</p></section>']
    for cid,name in rows:
        out.append('<section class="studio-panel"><h2>'+e(name)+'</h2><form class="studio-form" method="post" action="/site-agent"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="company_id" value="'+e(cid)+'"><label>Tell your agent what to change<textarea name="instruction" maxlength="500" required placeholder="set headline to Discover Gerate"></textarea></label><button name="action" value="propose">Prepare change</button></form><p class="hint">Try: set headline to New arrivals | set description to Fashion for everyone | set theme to ocean</p>')
        proposals=c.execute('SELECT id,instruction,action,payload,status FROM vx_agent_proposals WHERE company_id=? AND owner_id=? ORDER BY created DESC LIMIT 15',(cid,owner)).fetchall()
        for pid,instruction,kind,payload,status in proposals:
            out.append('<div class="agent-proposal"><p><strong>'+e(status.upper())+'</strong> · '+e(instruction)+'</p><p class="hint">Proposed '+e(kind)+': '+e(str(json.loads(payload)))+'</p>')
            if status=='pending':out.append('<form method="post" action="/site-agent"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="company_id" value="'+e(cid)+'"><input type="hidden" name="proposal_id" value="'+e(pid)+'"><button name="action" value="approve_proposal">Approve change</button> <button name="action" value="reject_proposal">Reject</button></form>')
            out.append('</div>')
        out.append('<p><a href="/site-preview?id='+e(cid)+'" target="_blank" rel="noopener">Open private preview</a></p></section>')
    return ''.join(out)
