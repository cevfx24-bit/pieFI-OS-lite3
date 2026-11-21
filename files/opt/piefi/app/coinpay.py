import os, sqlite3, time, secrets, base64, hashlib
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash

coin = Blueprint('piefi_coin', __name__)
DB = Path(os.environ.get('PIEFI_DB', '/etc/piefi/piefi.sqlite3'))
PRIMARY_ID = 'esp32-primary'
BACKUP_ID = 'esp8266-backup'
HEARTBEAT_TTL = 20
SESSION_TTL = 300

def db():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_coin_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS coin_plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price_cents INTEGER NOT NULL CHECK(price_cents>0),minutes INTEGER NOT NULL CHECK(minutes>0),rate_down INTEGER NOT NULL DEFAULT 10,rate_up INTEGER NOT NULL DEFAULT 10,enabled INTEGER NOT NULL DEFAULT 1,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS coin_denominations(pulses INTEGER PRIMARY KEY CHECK(pulses>0),amount_cents INTEGER NOT NULL CHECK(amount_cents>0));
        CREATE TABLE IF NOT EXISTS coin_controllers(id TEXT PRIMARY KEY,firmware TEXT NOT NULL DEFAULT '',ip TEXT NOT NULL DEFAULT '',last_seen INTEGER NOT NULL DEFAULT 0,last_event_at INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS coin_sessions(id TEXT PRIMARY KEY,plan_id INTEGER NOT NULL,client_ip TEXT NOT NULL,client_mac TEXT NOT NULL,hid TEXT NOT NULL,fas_encoded TEXT NOT NULL,fas_url TEXT NOT NULL,gateway_address TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'waiting',pulse_total INTEGER NOT NULL DEFAULT 0,amount_cents INTEGER NOT NULL DEFAULT 0,controller_id TEXT,reservation_id TEXT,created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,FOREIGN KEY(plan_id) REFERENCES coin_plans(id));
        CREATE TABLE IF NOT EXISTS coin_events(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT NOT NULL,session_id TEXT NOT NULL,pulses INTEGER NOT NULL,amount_cents INTEGER NOT NULL,created_at INTEGER NOT NULL,nonce TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS coin_pending_auth(id TEXT PRIMARY KEY,coin_session_id TEXT NOT NULL UNIQUE,client_ip TEXT NOT NULL,client_mac TEXT NOT NULL,hid TEXT NOT NULL,minutes INTEGER NOT NULL,rate_down INTEGER NOT NULL,rate_up INTEGER NOT NULL,created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',client_token TEXT);
        CREATE INDEX IF NOT EXISTS idx_coin_sessions_status ON coin_sessions(status,expires_at);
        CREATE INDEX IF NOT EXISTS idx_coin_events_created ON coin_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_coin_pending_token ON coin_pending_auth(client_token);
        ''')
        cols = {r['name'] for r in c.execute('PRAGMA table_info(coin_events)')}
        for name, decl in [('session_id', "TEXT NOT NULL DEFAULT ''"), ('amount_cents', 'INTEGER NOT NULL DEFAULT 0')]:
            if name not in cols:
                c.execute(f'ALTER TABLE coin_events ADD COLUMN {name} {decl}')
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_auth'").fetchone():
            pcols = {r['name'] for r in c.execute('PRAGMA table_info(pending_auth)')}
            if 'client_token' not in pcols:
                c.execute('ALTER TABLE pending_auth ADD COLUMN client_token TEXT')
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone():
            scols = {r['name'] for r in c.execute('PRAGMA table_info(sessions)')}
            if 'nds_token' not in scols:
                c.execute('ALTER TABLE sessions ADD COLUMN nds_token TEXT')

def device_token_ok():
    expected = os.environ.get('PIEFI_CONTROLLER_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    return bool(expected) and secrets.compare_digest(supplied, 'Bearer ' + expected)

def device_id_ok(device_id):
    return device_id in (PRIMARY_ID, BACKUP_ID)

def active_device(c, device_id, now):
    primary = c.execute('SELECT last_seen FROM coin_controllers WHERE id=?', (PRIMARY_ID,)).fetchone()
    primary_live = bool(primary and now - int(primary['last_seen']) <= HEARTBEAT_TTL)
    return device_id == PRIMARY_ID or (device_id == BACKUP_ID and not primary_live)

def touch_device(c, device_id, firmware='unknown'):
    now = int(time.time())
    ip = (request.remote_addr or '')[:45]
    c.execute('''INSERT INTO coin_controllers(id,firmware,ip,last_seen) VALUES(?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET firmware=excluded.firmware,ip=excluded.ip,last_seen=excluded.last_seen''',
      (device_id, str(firmware)[:80], ip, now))
    return now

def create_coin_session(client, encoded, fas_url, plan_id):
    now = int(time.time())
    sid = secrets.token_urlsafe(24)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        plan = c.execute('SELECT id FROM coin_plans WHERE id=? AND enabled=1', (plan_id,)).fetchone()
        if not plan:
            return None, 'Walang active na coin package. I-configure muna sa admin dashboard.'
        if not os.environ.get('PIEFI_CONTROLLER_TOKEN'):
            return None, 'Hindi pa naka-pair ang coin controller.'
        busy = c.execute("SELECT id FROM coin_sessions WHERE status IN ('waiting','collecting') AND expires_at>? LIMIT 1", (now,)).fetchone()
        if busy:
            return None, 'May kasalukuyang customer na gumagamit ng coin slot. Subukan muli mamaya.'
        c.execute('''INSERT INTO coin_sessions(id,plan_id,client_ip,client_mac,hid,fas_encoded,fas_url,gateway_address,status,created_at,expires_at)
          VALUES(?,?,?,?,?,?,?,?, 'waiting',?,?)''',
          (sid, plan_id, client['clientip'], client['clientmac'].lower(), client['hid'], encoded, fas_url, client['gatewayaddress'], now, now + SESSION_TTL))
    return sid, None

def local_day_start(now=None):
    now = int(now or time.time())
    lt = time.localtime(now)
    return int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)))

def controller_context():
    now = int(time.time())
    day_start = local_day_start(now)
    try:
        with db() as c:
            rows = {r['id']: dict(r) for r in c.execute('SELECT * FROM coin_controllers')}
            revenue = c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM coin_sessions WHERE status='authorized'").fetchone()[0]
            today = c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM coin_sessions WHERE status='authorized' AND created_at>=?", (day_start,)).fetchone()[0]
            active = c.execute("SELECT COUNT(*) FROM coin_sessions WHERE status IN ('waiting','collecting') AND expires_at>?", (now,)).fetchone()[0]
        return {'coin_revenue_cents': revenue, 'coin_today_cents': today, 'coin_waiting': active,
                'coin_primary_online': bool(rows.get(PRIMARY_ID) and now-rows[PRIMARY_ID]['last_seen'] <= HEARTBEAT_TTL),
                'coin_backup_online': bool(rows.get(BACKUP_ID) and now-rows[BACKUP_ID]['last_seen'] <= HEARTBEAT_TTL)}
    except sqlite3.Error:
        return {'coin_revenue_cents': 0, 'coin_today_cents': 0, 'coin_waiting': 0, 'coin_primary_online': False, 'coin_backup_online': False}

@coin.route('/api/controller/heartbeat', methods=['POST'])
def controller_heartbeat():
    if not device_token_ok(): return jsonify(ok=False, error='unauthorized'), 401
    data = request.get_json(silent=True) or {}
    did = str(data.get('device_id', ''))
    if not device_id_ok(did): return jsonify(ok=False, error='unknown_device'), 400
    with db() as c:
        now = touch_device(c, did, data.get('firmware', 'unknown'))
        active = active_device(c, did, now)
    return jsonify(ok=True, device_id=did, active=active, heartbeat_ttl=HEARTBEAT_TTL)

@coin.route('/api/controller/next-session', methods=['GET'])
def controller_next_session():
    if not device_token_ok(): return jsonify(ok=False, error='unauthorized'), 401
    did = request.args.get('device_id', '')
    if not device_id_ok(did): return jsonify(ok=False, error='unknown_device'), 400
    now = int(time.time())
    with db() as c:
        touch_device(c, did, request.args.get('firmware', 'unknown'))
        if not active_device(c, did, now): return jsonify(ok=True, active=False, session=None)
        c.execute("UPDATE coin_sessions SET status='expired' WHERE status IN ('waiting','collecting') AND expires_at<=?", (now,))
        row = c.execute("SELECT s.*,p.price_cents,p.name FROM coin_sessions s JOIN coin_plans p ON p.id=s.plan_id WHERE s.status IN ('waiting','collecting') AND s.expires_at>? ORDER BY s.created_at LIMIT 1", (now,)).fetchone()
        if not row: return jsonify(ok=True, active=True, session=None)
        if row['controller_id'] and row['controller_id'] != did:
            # The primary may immediately reclaim a session from the logical standby.
            if not (did == PRIMARY_ID and row['controller_id'] == BACKUP_ID):
                prev = c.execute('SELECT last_seen FROM coin_controllers WHERE id=?', (row['controller_id'],)).fetchone()
                if prev and now-int(prev['last_seen']) <= HEARTBEAT_TTL:
                    return jsonify(ok=True, active=True, session=None)
        c.execute("UPDATE coin_sessions SET status='collecting',controller_id=? WHERE id=?", (did, row['id']))
        return jsonify(ok=True, active=True, session={'id':row['id'],'plan':row['name'],'price_cents':row['price_cents'],'amount_cents':row['amount_cents'],'expires_at':row['expires_at']})

@coin.route('/api/controller/coin', methods=['POST'])
def controller_coin_event():
    if not device_token_ok(): return jsonify(ok=False, error='unauthorized'), 401
    data = request.get_json(silent=True) or {}
    did, sid, nonce = str(data.get('device_id','')), str(data.get('session_id','')), str(data.get('event_id',''))
    try: pulses = int(data.get('pulses', 0))
    except (TypeError, ValueError): return jsonify(ok=False, error='invalid_pulses'), 400
    if not device_id_ok(did) or not sid or not nonce or len(nonce)>100 or not 1<=pulses<=50:
        return jsonify(ok=False, error='invalid_event'), 400
    now = int(time.time())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        touch_device(c, did, data.get('firmware', 'unknown'))
        if not active_device(c, did, now): return jsonify(ok=False, error='standby_controller'), 409
        row = c.execute('SELECT s.*,p.price_cents,p.minutes,p.rate_down,p.rate_up FROM coin_sessions s JOIN coin_plans p ON p.id=s.plan_id WHERE s.id=?', (sid,)).fetchone()
        if not row or row['status']!='collecting' or row['expires_at']<=now or row['controller_id']!=did:
            return jsonify(ok=False, error='session_not_active'), 409
        denom = c.execute('SELECT amount_cents FROM coin_denominations WHERE pulses=?', (pulses,)).fetchone()
        if not denom: return jsonify(ok=False, error='unmapped_coin_pulse', pulses=pulses), 422
        amount = int(denom['amount_cents'])
        try:
            c.execute('INSERT INTO coin_events(device_id,session_id,pulses,amount_cents,created_at,nonce) VALUES(?,?,?,?,?,?)', (did,sid,pulses,amount,now,nonce))
        except sqlite3.IntegrityError:
            return jsonify(ok=False, error='duplicate_event'), 409
        total = int(row['amount_cents']) + amount
        c.execute('UPDATE coin_sessions SET amount_cents=?,pulse_total=pulse_total+? WHERE id=?', (total,pulses,sid))
        paid = total >= int(row['price_cents'])
        if paid:
            reservation = secrets.token_urlsafe(24)
            minutes = max(1, (total*int(row['minutes']) + int(row['price_cents'])-1)//int(row['price_cents']))
            c.execute('''INSERT INTO coin_pending_auth(id,coin_session_id,client_ip,client_mac,hid,minutes,rate_down,rate_up,created_at,expires_at,status)
              VALUES(?,?,?,?,?,?,?,?,?,?,'pending')''', (reservation,sid,row['client_ip'],row['client_mac'],row['hid'],minutes,row['rate_down'],row['rate_up'],now,now+300))
            c.execute("UPDATE coin_sessions SET status='paid',reservation_id=? WHERE id=?", (reservation,sid))
        c.execute('UPDATE coin_controllers SET last_event_at=? WHERE id=?', (now,did))
        return jsonify(ok=True, amount_added_cents=amount, total_cents=total, required_cents=row['price_cents'], paid=paid)

@coin.route('/api/coin/status/<sid>', methods=['GET'])
def coin_status(sid):
    now = int(time.time())
    with db() as c:
        row = c.execute('SELECT s.*,p.price_cents,p.name FROM coin_sessions s JOIN coin_plans p ON p.id=s.plan_id WHERE s.id=?', (sid,)).fetchone()
        if not row: return jsonify(ok=False,error='not_found'), 404
        if row['expires_at']<=now and row['status'] in ('waiting','collecting'):
            c.execute("UPDATE coin_sessions SET status='expired' WHERE id=?", (sid,))
            return jsonify(ok=True,status='expired',amount_cents=row['amount_cents'],required_cents=row['price_cents'])
        result = {'ok':True,'status':row['status'],'amount_cents':row['amount_cents'],'required_cents':row['price_cents'],'plan':row['name']}
        if row['status']=='paid' and row['reservation_id']:
            key = os.environ.get('PIEFI_FAS_KEY','')
            token = hashlib.sha256((row['hid']+key).encode()).hexdigest()
            custom = base64.b64encode(('piefi-coin:'+row['reservation_id']).encode()).decode()
            from urllib.parse import urlencode
            redir = row['fas_url'].rstrip('/') + '/fas/fas-hid.php?' + urlencode({'fas':row['fas_encoded'],'landing':'1'})
            result['auth'] = {'url':'http://'+row['gateway_address']+':2050/opennds_auth/','token':token,'custom':custom,'redir':redir}
        return jsonify(result)

@coin.route('/coin')
def coin_admin():
    from flask import session
    if not session.get('admin'): return redirect(url_for('login', next='/admin/coin'))
    now = int(time.time())
    day_start = local_day_start(now)
    with db() as c:
        plans=c.execute('SELECT * FROM coin_plans ORDER BY price_cents').fetchall()
        denoms=c.execute('SELECT * FROM coin_denominations ORDER BY pulses').fetchall()
        controllers=c.execute('SELECT * FROM coin_controllers ORDER BY id').fetchall()
        recent=c.execute('SELECT * FROM coin_sessions ORDER BY created_at DESC LIMIT 30').fetchall()
        revenue=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM coin_sessions WHERE status='authorized'").fetchone()[0]
        today=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM coin_sessions WHERE status='authorized' AND created_at>=?", (day_start,)).fetchone()[0]
    return render_template('coin.html',title='Coin Payment System',plans=plans,denoms=denoms,controllers=controllers,recent=recent,revenue=revenue,today=today,now=now,controller_token=os.environ.get('PIEFI_CONTROLLER_TOKEN','NOT CONFIGURED'),primary_id=PRIMARY_ID,backup_id=BACKUP_ID,heartbeat_ttl=HEARTBEAT_TTL)

@coin.route('/coin/plan', methods=['POST'])
def coin_add_plan():
    from flask import session
    if not session.get('admin'): return redirect(url_for('login'))
    try:
        name=request.form.get('name','').strip()[:40]
        price=int(round(float(request.form.get('price_pesos','0'))*100))
        minutes=int(request.form.get('minutes','0')); down=int(request.form.get('rate_down','10')); up=int(request.form.get('rate_up','10'))
        if not name or price<=0 or minutes<=0 or not (1<=down<=1000 and 1<=up<=1000): raise ValueError()
    except (ValueError,TypeError):
        flash('Invalid package values. Check price, minutes and Mbps.','error'); return redirect(url_for('coin_admin'))
    with db() as c: c.execute('INSERT INTO coin_plans(name,price_cents,minutes,rate_down,rate_up,created_at) VALUES(?,?,?,?,?,?)', (name,price,minutes,down,up,int(time.time())))
    flash('Coin package added.','success'); return redirect(url_for('coin_admin'))

@coin.route('/coin/plan/<int:pid>/toggle', methods=['POST'])
def coin_toggle_plan(pid):
    from flask import session
    if not session.get('admin'): return redirect(url_for('login'))
    with db() as c: c.execute('UPDATE coin_plans SET enabled=1-enabled WHERE id=?', (pid,))
    return redirect(url_for('coin_admin'))

@coin.route('/coin/denomination', methods=['POST'])
def coin_add_denomination():
    from flask import session
    if not session.get('admin'): return redirect(url_for('login'))
    try:
        pulses=int(request.form.get('pulses','0')); amount=int(round(float(request.form.get('amount_pesos','0'))*100))
        if not (1<=pulses<=50 and amount>0): raise ValueError()
    except (ValueError,TypeError):
        flash('Invalid pulse mapping. Use the exact pulse count measured from your coin acceptor.','error'); return redirect(url_for('coin_admin'))
    with db() as c: c.execute('INSERT INTO coin_denominations(pulses,amount_cents) VALUES(?,?) ON CONFLICT(pulses) DO UPDATE SET amount_cents=excluded.amount_cents', (pulses,amount))
    flash('Coin pulse mapping saved.','success'); return redirect(url_for('coin_admin'))

@coin.route('/coin/denomination/<int:pulses>/delete', methods=['POST'])
def coin_delete_denomination(pulses):
    from flask import session
    if not session.get('admin'): return redirect(url_for('login'))
    with db() as c: c.execute('DELETE FROM coin_denominations WHERE pulses=?', (pulses,))
    return redirect(url_for('coin_admin'))

def register_coinpay(app):
    app.register_blueprint(coin)
