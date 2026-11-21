import base64, hashlib, os, secrets, sqlite3, time
from urllib.parse import urlencode
from flask import Blueprint, request, render_template_string

fas = Blueprint('piefi_fas', __name__)
DB = os.environ.get('PIEFI_DB', '/etc/piefi/piefi.sqlite3')

def db_connect():
    conn=sqlite3.connect(DB,timeout=10)
    conn.row_factory=sqlite3.Row
    return conn

def parse_fas_query(encoded):
    try:
        raw=base64.b64decode(encoded,validate=True).decode('utf-8')
        result={}
        for item in raw.split(', '):
            if '=' in item:
                key,value=item.split('=',1); result[key.strip()]=value.strip()
        required=('hid','gatewayaddress','clientip','clientmac')
        return result if all(result.get(k) for k in required) else None
    except Exception:
        return None

PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PieFi OS Lite - PisoWiFi</title>
<style>
:root{color-scheme:dark;--bg:#07111f;--line:#263b55;--text:#eef6ff;--muted:#9bb0c9;--accent:#25c6b7;--blue:#168fba}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:18px;font-family:Inter,system-ui,Arial;background:radial-gradient(ellipse at 50% 0%,#173653 0%,var(--bg) 58%);color:var(--text)}.card{width:100%;max-width:480px;padding:28px 24px;background:linear-gradient(155deg,#14263d,#0d192a);border:1px solid var(--line);border-radius:24px;box-shadow:0 24px 80px #0008}.mark{width:58px;height:58px;margin:0 auto 14px;display:grid;place-items:center;border-radius:18px;background:linear-gradient(135deg,var(--accent),var(--blue));color:#061522;font-size:30px;font-weight:900}.brand{text-align:center;font-size:27px;font-weight:800}.brand span{color:var(--accent)}.sub{text-align:center;color:var(--muted);font-size:14px;margin:7px 0 22px}.tag{display:inline-block;padding:6px 10px;border:1px solid #2b5266;border-radius:99px;color:#8fe8df;font-size:10px;letter-spacing:1.1px;font-weight:800}.section{margin-top:18px;padding:17px;border:1px solid #29425c;border-radius:16px;background:#0a1929}h2{font-size:16px;margin:0 0 8px}p{color:var(--muted);font-size:13px;line-height:1.55;margin:5px 0 12px}select,input{width:100%;padding:14px;border:1px solid #38516d;background:#081626;color:#fff;border-radius:11px;font-size:15px;margin:8px 0;outline:none}button{width:100%;padding:15px;margin-top:9px;border:0;border-radius:12px;background:linear-gradient(100deg,var(--accent),#28a9cb);color:#041521;font-size:14px;font-weight:900;letter-spacing:.5px;cursor:pointer}.secondary{background:#1b3650;color:#d9ecfb;border:1px solid #3a5874}.error{margin:12px 0;background:#4a1f2a;color:#ffc5cf;padding:12px;border:1px solid #85384a;border-radius:10px;font-size:13px}.foot{text-align:center;color:#7890aa;font-size:11px;margin:20px 0 0}
</style></head><body><main class="card"><div class="mark">⌁</div><div class="brand"><span>PieFi</span> OS Lite</div><p class="sub">PisoWiFi Internet Access</p><div style="text-align:center"><span class="tag">SECURE CUSTOMER ACCESS</span></div>
{% if error %}<div class="error" role="alert">{{error}}</div>{% endif %}
<section class="section"><h2>🪙 Insert Coin</h2><p>Pumili ng internet package, pagkatapos ay maghulog ng barya sa coin acceptor.</p>
{% if plans and controller_ready and denoms %}<form method="post"><input type="hidden" name="fas" value="{{encoded}}"><input type="hidden" name="payment_type" value="coin"><select name="plan_id" required>{% for p in plans %}<option value="{{p.id}}">{{p.name}} · ₱{{'%.2f'|format(p.price_cents/100)}} · {{p.minutes}} minutes</option>{% endfor %}</select><button type="submit">INSERT COIN · START PAYMENT</button></form>
{% else %}<p>Hindi pa naka-configure ang coin payment. Makipag-ugnayan sa operator.</p><button class="secondary" type="button" disabled>COIN PAYMENT UNAVAILABLE</button>{% endif %}</section>
<section class="section"><h2>Voucher Access</h2><p>Ilagay ang iyong voucher code para mag-connect.</p><form method="post"><input type="hidden" name="fas" value="{{encoded}}"><input type="hidden" name="payment_type" value="voucher"><input name="code" maxlength="32" required autocomplete="off" placeholder="ENTER VOUCHER CODE"><button class="secondary" type="submit">VERIFY VOUCHER</button></form></section>
<p class="foot">Powered by PieFi OS Lite · Customer Wi-Fi Portal</p></main></body></html>'''

COIN_WAIT_PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PieFi · Insert Coin</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#07111f;color:#eef6ff;font-family:system-ui;padding:20px}.card{max-width:420px;width:100%;padding:30px;text-align:center;background:#101e31;border:1px solid #263b55;border-radius:22px}h1{font-size:25px}.amount{font-size:38px;color:#25c6b7;font-weight:900;margin:16px}.muted{color:#9bb0c9;line-height:1.5}.bar{height:10px;background:#263b55;border-radius:20px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:#25c6b7;transition:width .2s}</style></head><body><main class="card"><div style="font-size:38px">🪙</div><h1>Insert Coin</h1><p class="muted" id="message">Naghihintay ng coin acceptor. Huwag isara ang page.</p><div class="amount" id="amount">₱0.00</div><div class="bar"><i id="progress"></i></div><p class="muted" id="target">Connecting to PieFi controller…</p><form id="authForm" method="get" style="display:none"><input type="hidden" name="tok" id="tok"><input type="hidden" name="custom" id="custom"><input type="hidden" name="redir" id="redir"></form></main>
<script>const sid={{session_id|tojson}};let done=false;async function poll(){if(done)return;try{const r=await fetch('/api/coin/status/'+encodeURIComponent(sid),{cache:'no-store'});const d=await r.json();if(!d.ok)throw new Error(d.error||'status error');const got=d.amount_cents||0,need=d.required_cents||1;document.getElementById('amount').textContent='₱'+(got/100).toFixed(2);document.getElementById('target').textContent='Package total: ₱'+(need/100).toFixed(2)+' · '+d.plan;document.getElementById('progress').style.width=Math.min(100,got/need*100)+'%';if(d.status==='paid'&&d.auth){done=true;document.getElementById('message').textContent='Bayad verified! Kinokonekta ka na…';document.getElementById('tok').value=d.auth.token;document.getElementById('custom').value=d.auth.custom;document.getElementById('redir').value=d.auth.redir;const f=document.getElementById('authForm');f.action=d.auth.url;f.submit();return;}if(d.status==='expired'){done=true;document.getElementById('message').textContent='Nag-expire ang payment session. Bumalik sa portal at magsimula muli.';return;}document.getElementById('message').textContent=d.status==='collecting'?'Coin acceptor ready. Ihulog ang barya.':'Naghihintay ng controller…';}catch(e){document.getElementById('message').textContent='Connecting…';}setTimeout(poll,1500);}poll();</script></body></html>'''

CONTINUE_PAGE = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>PieFi - Verify</title></head><body style="font-family:system-ui;text-align:center;padding:36px;background:#07111f;color:#eef6ff"><h2>{{message}}</h2><p>Press continue to request internet access.</p><form action="{{auth_url}}" method="get"><input type="hidden" name="tok" value="{{token}}"><input type="hidden" name="custom" value="{{custom}}"><input type="hidden" name="redir" value="{{redir}}"><button style="padding:14px 30px">Continue</button></form></body></html>'''

@fas.route('/fas/fas-hid.php', methods=['GET','POST'])
def fas_login():
    encoded=request.values.get('fas','')
    client=parse_fas_query(encoded)
    if not client: return 'Invalid OpenNDS authentication request.',400
    if request.values.get('landing')=='1':
        return '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>PieFi Connected</title></head><body style="font-family:system-ui;text-align:center;padding:40px;background:#07111f;color:#eef6ff"><h1>Connected!</h1><p>Your PieFi payment or voucher was accepted. Internet access is now available.</p><b>PieFi OS Lite</b></body></html>'

    def portal_context(error=None):
        now=int(time.time())
        with db_connect() as conn:
            plans=conn.execute('SELECT * FROM coin_plans WHERE enabled=1 ORDER BY price_cents').fetchall()
            denoms=conn.execute('SELECT pulses FROM coin_denominations').fetchall()
            devices=conn.execute('SELECT last_seen FROM coin_controllers').fetchall()
        online=any(now-int(d['last_seen'])<=20 for d in devices)
        return render_template_string(PAGE,encoded=encoded,error=error,plans=plans,denoms=denoms,
            controller_ready=bool(os.environ.get('PIEFI_CONTROLLER_TOKEN')) and online)

    if request.method=='GET': return portal_context()

    if request.form.get('payment_type')=='coin':
        try:
            from coinpay import create_coin_session
            plan_id=int(request.form.get('plan_id','0'))
        except (ValueError,ImportError): return portal_context('Coin payment setup error.'),503
        sid,error=create_coin_session(client,encoded,request.url_root.rstrip('/'),plan_id)
        if error: return portal_context(error),409
        return render_template_string(COIN_WAIT_PAGE,session_id=sid)

    code=request.form.get('code','').strip().upper()
    if not code or len(code)>32: return portal_context('Invalid voucher code.'),400
    key=os.environ.get('PIEFI_FAS_KEY','')
    if not key: return 'FAS key is not configured.',503
    reservation=secrets.token_urlsafe(24); now=int(time.time())
    try:
        with db_connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('''CREATE TABLE IF NOT EXISTS pending_auth(id TEXT PRIMARY KEY,voucher_code TEXT NOT NULL UNIQUE,client_ip TEXT NOT NULL,client_mac TEXT NOT NULL,hid TEXT NOT NULL,created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',client_token TEXT)''')
            cols={r['name'] for r in conn.execute('PRAGMA table_info(pending_auth)')}
            if 'client_token' not in cols: conn.execute('ALTER TABLE pending_auth ADD COLUMN client_token TEXT')
            conn.execute("DELETE FROM pending_auth WHERE expires_at<=? AND status='pending'",(now,))
            voucher=conn.execute("SELECT code FROM vouchers WHERE code=? AND status='unused'",(code,)).fetchone()
            if not voucher: return portal_context('Voucher is invalid or already used.'),400
            conn.execute('INSERT INTO pending_auth(id,voucher_code,client_ip,client_mac,hid,created_at,expires_at,status) VALUES(?,?,?,?,?,?,? ,\'pending\')',(reservation,code,client['clientip'],client['clientmac'].lower(),client['hid'],now,now+300))
    except sqlite3.IntegrityError:
        return portal_context('This voucher is already being processed.'),409
    except sqlite3.Error:
        return 'Voucher database error.',500
    token=hashlib.sha256((client['hid']+key).encode()).hexdigest()
    custom=base64.b64encode(('piefi:'+reservation).encode()).decode()
    redir=request.url_root.rstrip('/')+'/fas/fas-hid.php?'+urlencode({'fas':encoded,'landing':'1'})
    auth_url='http://'+client['gatewayaddress']+':2050/opennds_auth/'
    return render_template_string(CONTINUE_PAGE,auth_url=auth_url,token=token,custom=custom,redir=redir,message='Voucher verified')

def register_fas(app):
    app.register_blueprint(fas)
