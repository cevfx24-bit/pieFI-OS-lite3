#!/usr/bin/env python3
"""PieFi OS Lite Phase 3 portal prototype. Simulation only; no captive access enforcement."""
import argparse, json, os, sqlite3, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PieFi OS Lite</title>
<style>
:root{font-family:Inter,system-ui,Segoe UI,Arial;background:#0b1220;color:#e6edf7}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#0b1220,#101b2e);min-height:100vh}.wrap{max-width:1050px;margin:auto;padding:24px}.top{display:flex;align-items:center;justify-content:space-between;gap:12px}.brand{font-size:24px;font-weight:800;letter-spacing:.3px}.brand span{color:#42d6a3}.sub{color:#94a3b8}.tabs{display:flex;gap:8px;margin:24px 0}.tab,button{border:0;border-radius:10px;padding:12px 16px;background:#1c2a40;color:#e6edf7;cursor:pointer}.tab.active,button.primary{background:#23a884;color:#06231b;font-weight:700}.panel{background:#132038;border:1px solid #263b57;border-radius:16px;padding:20px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.stat{background:#172740;padding:18px;border-radius:14px}.stat small{color:#93a7bf}.stat h2{margin:8px 0 0}.hidden{display:none}input{background:#0b1425;border:1px solid #354963;border-radius:9px;padding:12px;color:white;width:100%;margin:6px 0 12px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #2b3b50}code{color:#42d6a3}footer{color:#8396ac;padding:16px 0;font-size:12px}@media(max-width:600px){.wrap{padding:14px}.tabs{flex-wrap:wrap}.top{align-items:flex-start;flex-direction:column}}
</style></head><body><div class="wrap"><header class="top"><div><div class="brand">PieFi <span>OS Lite</span></div><div class="sub">Standalone PisoWiFi portal prototype</div></div><div id="status" class="sub">Simulation mode</div></header>
<div class="tabs"><button class="tab active" onclick="show('customer',this)">Customer Portal</button><button class="tab" onclick="show('admin',this)">Admin</button></div>
<section id="customer"><div class="panel"><h1>Connect to the Internet</h1><p class="sub">Insert coins at the vending machine or enter a voucher. This demo simulates credit only.</p><label>Voucher / Client ID</label><input id="client" placeholder="e.g. CLIENT-001"><label>Demo credit (minutes)</label><input id="minutes" type="number" min="1" max="1440" value="10"><button class="primary" onclick="addDemo()">Add demo credit</button><p id="msg"></p></div><div class="grid"><div class="stat"><small>Account</small><h2 id="acct">—</h2></div><div class="stat"><small>Credit</small><h2 id="credit">0 min</h2></div><div class="stat"><small>Ledger mode</small><h2>Simulation</h2></div></div></section>
<section id="admin" class="hidden"><div class="panel"><h2>Admin Overview</h2><p class="sub">Local demo view. Production admin authentication and access restrictions are not yet implemented.</p><button onclick="refresh()">Refresh ledger</button><div id="table"></div></div></section>
<footer>PieFi OS Lite • Phase 3 UI prototype • Not connected to openNDS, coin hardware, or firewall authorization.</footer></div>
<script>
function show(id,b){document.getElementById('customer').classList.toggle('hidden',id!=='customer');document.getElementById('admin').classList.toggle('hidden',id!=='admin');document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(id==='admin')refresh()}
async function addDemo(){let c=document.getElementById('client').value.trim(),m=Number(document.getElementById('minutes').value);if(!c||!Number.isInteger(m)||m<1||m>1440){document.getElementById('msg').textContent='Enter client ID and 1–1440 minutes.';return}let r=await fetch('/credit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:c,seconds:m*60})});let j=await r.json();document.getElementById('msg').textContent=j.error||'Credit added (simulation).';document.getElementById('acct').textContent=c;document.getElementById('credit').textContent=Math.floor(j.credited_seconds/60)+' min';refresh()}
async function refresh(){let r=await fetch('/clients'),j=await r.json();let rows=j.clients||[];document.getElementById('table').innerHTML='<table><thead><tr><th>Client</th><th>Credit</th><th>Updated</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>'+esc(x.client_id)+'</td><td>'+Math.floor(x.credited_seconds/60)+' min</td><td>'+new Date(x.updated_at*1000).toLocaleString()+'</td></tr>').join('')+'</tbody></table>'}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
</script></body></html>"""

def init(db):
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS clients(client_id TEXT PRIMARY KEY,credited_seconds INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)""")

class Server(HTTPServer): allow_reuse_address=True
def factory(db):
    class H(BaseHTTPRequestHandler):
        def sendj(self,status,obj):
            b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
        def do_GET(self):
            if self.path in ('/','/index.html'):
                b=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
            if self.path=='/health':return self.sendj(200,{'status':'ok','mode':'simulation'})
            if self.path=='/clients':
                with sqlite3.connect(db) as c: rows=c.execute('SELECT client_id,credited_seconds,updated_at FROM clients ORDER BY updated_at DESC').fetchall()
                return self.sendj(200,{'clients':[{'client_id':r[0],'credited_seconds':r[1],'updated_at':r[2]} for r in rows]})
            return self.sendj(404,{'error':'not found'})
        def do_POST(self):
            if self.path!='/credit':return self.sendj(404,{'error':'not found'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n<=0 or n>2048:raise ValueError()
                o=json.loads(self.rfile.read(n)); client=str(o['client_id']).strip(); seconds=int(o['seconds'])
                if not client or seconds<=0 or seconds>86400:raise ValueError()
            except Exception:return self.sendj(400,{'error':'provide client_id and positive seconds (max 24 hours)'})
            now=int(time.time())
            with sqlite3.connect(db) as c:
                c.execute('INSERT OR IGNORE INTO clients(client_id,credited_seconds,created_at,updated_at) VALUES(?,?,?,?)',(client,0,now,now))
                c.execute('UPDATE clients SET credited_seconds=credited_seconds+?,updated_at=? WHERE client_id=?',(seconds,now,client))
                total=c.execute('SELECT credited_seconds FROM clients WHERE client_id=?',(client,)).fetchone()[0]
            return self.sendj(200,{'client_id':client,'credited_seconds':total,'mode':'simulation'})
        def log_message(self,*a):pass
    return H
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default='./piefi.sqlite3');p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=8090);a=p.parse_args()
    init(a.db);s=Server((a.bind,a.port),factory(a.db));print(f'PieFi Phase 3 simulation UI: http://{a.bind}:{a.port}');s.serve_forever()
