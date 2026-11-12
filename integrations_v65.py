"""V65 approved outbound webhook connector.

Owner-configured HTTPS destination, allowlisted hostname, HMAC signature,
single-attempt dispatch and audit trail. No arbitrary URL input at runtime.
"""
import hashlib
import hmac
import html
import ipaddress
import json
import os
import secrets
import socket
import time
import urllib.parse
import http.client
import business_agents_v59 as agents

def setup(c):
    agents.init(c)
    c.execute("""CREATE TABLE IF NOT EXISTS v65_dispatches(
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,job_id TEXT NOT NULL,
      actor INTEGER NOT NULL,state TEXT NOT NULL,response_code INTEGER NOT NULL,
      created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS v65_dispatch_once ON v65_dispatches(workspace_id,job_id)")

def config():
    endpoint=os.getenv("VELXTRIA_V65_WEBHOOK_URL","")
    secret=os.getenv("VELXTRIA_V65_WEBHOOK_SECRET","")
    allowed=os.getenv("VELXTRIA_V65_ALLOWED_HOST","")
    parsed=urllib.parse.urlsplit(endpoint)
    if not endpoint or not secret or len(secret)<24 or not allowed:
        raise ValueError("Outbound integration not configured")
    if parsed.scheme!="https" or not parsed.hostname or parsed.hostname!=allowed.lower() or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Outbound endpoint not allowed")
    if parsed.hostname in ("localhost",) or parsed.hostname.endswith((".local",".internal")):
        raise ValueError("Private endpoint not allowed")
    return parsed,secret

def public_addresses(host):
    # Resolve before connecting, and pin the resolved public IP to avoid DNS rebinding.
    addresses=set()
    for family,kind,proto,canon,sockaddr in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM):
        ip=ipaddress.ip_address(sockaddr[0])
        if not ip.is_global:raise ValueError("Nonpublic webhook address")
        addresses.add(str(ip))
    if not addresses:raise ValueError("Unable to resolve webhook")
    return sorted(addresses)

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip,timeout):
        super().__init__(host,443,timeout=timeout)
        self._ip=ip
    def connect(self):
        import ssl
        raw=socket.create_connection((self._ip,443),timeout=self.timeout)
        self.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=self.host)

def deliver(payload,dispatcher=None):
    parsed,secret=config()
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    if len(raw)>8192:raise ValueError("Payload too large")
    signature=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    if dispatcher is not None:return dispatcher(parsed.geturl(),raw,signature)
    ip=public_addresses(parsed.hostname)[0]
    conn=PinnedHTTPS(parsed.hostname,ip,timeout=8)
    try:
        path=(parsed.path or "/")+("?" + parsed.query if parsed.query else "")
        conn.request("POST",path,body=raw,headers={
            "Content-Type":"application/json","X-Velxtria-Signature":"sha256="+signature,
            "X-Velxtria-Event":"agent.approved","Content-Length":str(len(raw))})
        response=conn.getresponse()
        response.read(1024)
        return response.status
    finally:conn.close()

def dispatch(c,uid,wid,jid,dispatcher=None):
    agents.core.access(c,uid,wid,write=True,owner=True)
    setup(c)
    row=c.execute("SELECT agent,goal,proposal,status FROM bos59_agent_jobs WHERE id=? AND workspace_id=?",(jid,wid)).fetchone()
    if not row or row[3]!="approved":raise ValueError("Only approved tasks can be dispatched")
    # Validate destination before reserving the unique job attempt.
    config()
    did=secrets.token_hex(12);now=int(time.time())
    c.execute("INSERT INTO v65_dispatches VALUES(?,?,?,?,?,?,?,?)",(did,wid,jid,uid,"attempting",0,now,now))
    agents.core.audit(c,uid,wid,"v65_dispatch_attempt",did)
    payload={"event":"agent.approved","event_id":did,"workspace_id":wid,
             "job_id":jid,"agent":row[0],"goal":row[1],"approved_proposal":row[2]}
    status=0
    try:status=int(deliver(payload,dispatcher=dispatcher))
    except Exception:pass
    state="delivered" if 200<=status<300 else "failed"
    c.execute("UPDATE v65_dispatches SET state=?,response_code=?,updated=? WHERE id=? AND workspace_id=?",
              (state,status,int(time.time()),did,wid))
    agents.core.audit(c,uid,wid,"v65_dispatch_"+state,did)
    return did,state

def overview(c,uid,wid):
    role=agents.core.access(c,uid,wid);setup(c)
    jobs=c.execute("SELECT id,agent,goal,status FROM bos59_agent_jobs WHERE workspace_id=? AND status='approved' ORDER BY created DESC LIMIT 100",(wid,)).fetchall()
    attempts=c.execute("SELECT job_id,state,response_code,created FROM v65_dispatches WHERE workspace_id=? ORDER BY created DESC LIMIT 100",(wid,)).fetchall()
    return role,jobs,attempts

def render(c,uid,wid,csrf):
    role,jobs,attempts=overview(c,uid,wid)
    h=lambda x:html.escape(str(x),quote=True)
    sent={a[0] for a in attempts}
    hidden='<input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'">'
    out=['<section class="panel"><h1>VELXTRIA V65 · Outbound Integrations</h1><p>Send owner-approved tasks to one administrator-configured HTTPS webhook. This is a manual, single-attempt dispatch, not autonomous execution. Delivery does not prove downstream completion.</p></section>']
    for jid,agent,goal,status in jobs:
        out.append('<section class="panel"><h3>'+h(agent)+'</h3><p>'+h(goal)+'</p>')
        if role=="owner" and jid not in sent:
            out.append('<form method="post" action="/integrations-v65">'+hidden+'<input type="hidden" name="job" value="'+h(jid)+'"><button name="action" value="dispatch">Dispatch approved task</button></form>')
        out.append('</section>')
    out.append('<section class="panel"><h2>Delivery attempts</h2>')
    for jid,state,code,created in attempts:
        out.append('<p>Job '+h(jid)+' · '+h(state)+' · HTTP '+h(code)+'</p>')
    out.append('<p>Configure VELXTRIA_V65_WEBHOOK_URL, VELXTRIA_V65_ALLOWED_HOST, and VELXTRIA_V65_WEBHOOK_SECRET in Render. Failed attempts require manual investigation; automatic retries are disabled.</p></section>')
    return ''.join(out)
