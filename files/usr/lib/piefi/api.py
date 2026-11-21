#!/usr/bin/env python3
"""PieFi Stage 6 API: credits, session control and OpenNDS hooks."""
import os, subprocess, threading, time, re
from flask import Flask, request, jsonify, render_template_string
from engine import add_credit, create_session, pause, resume, status
TOKEN=os.environ.get('PIEFI_ADMIN_TOKEN','')
NODE_TOKEN=os.environ.get('PIEFI_NODE_TOKEN',TOKEN)
NDS=os.environ.get('PIEFI_NDS_AUTH','0')=='1'
app=Flask('piefi')
PAGE='<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>PieFi</title><style>body{font-family:system-ui;background:#101827;color:#e9eef9;margin:20px}main{max-width:900px;margin:auto}section{background:#1c2a40;padding:16px;border-radius:12px;margin:12px 0}button,input{padding:10px;border-radius:8px;margin:3px}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #445}input{max-width:100%}</style><main><h1>PieFi OS Lite Reloaded</h1><section><h2>Admin</h2><input id=token type=password placeholder="Admin token"><button onclick="saveToken()">Save</button><p id=msg></p></section><section><h2>Sessions</h2><button onclick="refresh()">Refresh</button><table id=t></table></section><section><h2>Manual credit (test/admin)</h2><input id=device placeholder="Client MAC"><input id=credit type=number value=1 min=1><button onclick="coin()">Add credit</button><button onclick="start()">Start</button></section></main><script>token.value=localStorage.token||\'\';function saveToken(){localStorage.token=token.value;msg.innerText=\'Token stored locally\';refresh()}async function api(p,m=\'GET\',b){return fetch(p,{method:m,headers:{\'Content-Type\':\'application/json\',\'Authorization\':\'Bearer \'+(localStorage.token||\'\')},body:b?JSON.stringify(b):undefined})}async function refresh(){try{let r=await api(\'/api/status\');if(!r.ok)throw Error(\'API \'+r.status);let d=await r.json();t.innerHTML=\'<tr><th>Device</th><th>Status</th><th>Remaining</th><th>Actions</th></tr>\'+d.map(x=>`<tr><td>${x.device}</td><td>${x.state}</td><td>${x.remaining||0}s</td><td><button onclick="act(\'${x.id}\',\'pause\')">Pause</button><button onclick="act(\'${x.id}\',\'resume\')">Resume</button></td></tr>`).join(\'\')}catch(e){msg.innerText=e.message}}async function act(id,a){await api(\'/api/session/\'+id+\'/\'+a,\'POST\');refresh()}async function coin(){let r=await api(\'/api/coin\',\'POST\',{device:device.value,credits:+credit.value,event_key:\'manual-\'+Date.now()});msg.innerText=await r.text();refresh()}async function start(){let r=await api(\'/api/session/start\',\'POST\',{device:device.value,seconds_per_credit:60});msg.innerText=await r.text();refresh()}refresh();setInterval(refresh,5000)</script>'

def auth():
    if not TOKEN: return jsonify(error='Admin token is not configured'),503
    if request.headers.get('Authorization','')!='Bearer '+TOKEN: return jsonify(error='unauthorized'),401
    return None
def valid_device(d): return bool(re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',d or ''))
def nds(cmd,device):
    if not NDS:return True
    try: return subprocess.run(['/usr/bin/ndsctl',cmd,device],timeout=5,check=False).returncode==0
    except Exception:return False
@app.get('/')
def home(): return render_template_string(PAGE)
@app.get('/api/status')
def stat():
    e=auth(); return e if e else jsonify(status())
@app.post('/api/coin')
def coin():
    e=auth();
    if e:return e
    d=request.get_json(silent=True) or {}
    if not valid_device(str(d.get('device',''))):return jsonify(error='device must be a valid MAC address'),400
    try:return jsonify(add_credit(str(d['device']),int(d.get('credits',0)),d.get('event_key')))
    except (ValueError,TypeError) as x:return jsonify(error=str(x)),400
@app.post('/api/node/coin')
def node_coin():
    # ESP coin node endpoint: bearer node token, MAC and unique pulse event ID.
    if not NODE_TOKEN or request.headers.get('Authorization','') != 'Bearer '+NODE_TOKEN:
        return jsonify(error='unauthorized'),401
    d=request.get_json(silent=True) or {}
    device=str(d.get('device',''))
    event_key=str(d.get('event_key',''))
    credits=d.get('credits',1)
    if not valid_device(device) or not event_key or len(event_key)>128:
        return jsonify(error='valid MAC and event_key required'),400
    try:
        result=add_credit(device,int(credits),event_key)
        return jsonify(result)
    except (ValueError,TypeError) as x:
        return jsonify(error=str(x)),400

@app.post('/api/session/start')
def start():
    e=auth();
    if e:return e
    d=request.get_json(silent=True) or {}; device=str(d.get('device',''))
    if not valid_device(device):return jsonify(error='device must be a valid MAC address'),400
    try:
        result=create_session(device,int(d.get('seconds_per_credit',60)))
        if NDS and not nds('auth',device):return jsonify(error='OpenNDS authorization failed',session=result),502
        return jsonify(result)
    except (ValueError,TypeError) as x:return jsonify(error=str(x)),400
@app.post('/api/session/<sid>/pause')
def pa(sid):
    e=auth();
    if e:return e
    try:
        left=pause(sid); s=next((x for x in status() if x['id']==sid),None)
        if s:nds('deauth',s['device'])
        return jsonify(remaining=left)
    except ValueError as x:return jsonify(error=str(x)),400
@app.post('/api/session/<sid>/resume')
def re(sid):
    e=auth();
    if e:return e
    try:
        expires=resume(sid); s=next((x for x in status() if x['id']==sid),None)
        if not s:return jsonify(error='session not found'),404
        if NDS and not nds('auth',s['device']):return jsonify(error='OpenNDS authorization failed'),502
        return jsonify(expires=expires)
    except ValueError as x:return jsonify(error=str(x)),400
@app.get('/api/health')
def health():return jsonify(ok=True,service='piefi-stage7',nds=NDS)
def expiry_loop():
    deauthed=set()
    while True:
        for s in status():
            if s['state']=='expired' and s['id'] not in deauthed:
                nds('deauth',s['device']); deauthed.add(s['id'])
        time.sleep(3)
if __name__=='__main__':
    threading.Thread(target=expiry_loop,daemon=True).start()
    app.run(host='0.0.0.0',port=8080)
