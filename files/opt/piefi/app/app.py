import os, sqlite3, secrets, time, csv, io, platform, subprocess
from functools import wraps
from pathlib import Path
from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get('PIEFI_DB', BASE / 'piefi.sqlite3'))
app = Flask(__name__)
app.secret_key = os.environ.get('PIEFI_SECRET_KEY') or 'UNSAFE-DEV-SECRET-CHANGE-ME'
ADMIN_USER = os.environ.get('PIEFI_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('PIEFI_ADMIN_PASSWORD', 'change-me-now')
ADMIN_HASH = os.environ.get('PIEFI_ADMIN_PASSWORD_HASH') or generate_password_hash(ADMIN_PASSWORD)
VERSION = '0.9.0-coin-integration'

class AdminPrefixMiddleware:
    """Separate public customer portal from protected admin routes."""
    def __init__(self, application, prefix='/admin'):
        self.application = application
        self.prefix = prefix.rstrip('/')

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '/')

        if path == self.prefix or path == self.prefix + '/' or path.startswith(self.prefix + '/'):
            # Keep the public URL under /admin while Flask routes internally from /.
            remainder = path[len(self.prefix):] or '/'
            script_name = environ.get('SCRIPT_NAME', '').rstrip('/')
            if not script_name.endswith(self.prefix):
                script_name += self.prefix
            environ['SCRIPT_NAME'] = script_name
            environ['PATH_INFO'] = '/dashboard' if remainder in ('', '/') else remainder
            return self.application(environ, start_response)

        # Public customer portal and health endpoints.
        # Static assets must also be reachable by the login/admin pages.
        if (path in ('/', '/health', '/favicon.ico', '/robots.txt')
                or path == '/fas/fas-hid.php'
                or path.startswith('/static/') or path.startswith('/api/controller/')
                or path.startswith('/api/coin/status/')):
            return self.application(environ, start_response)

        from werkzeug.wrappers import Response as WResponse
        return WResponse('Not found', status=404)(environ, start_response)


app.wsgi_app = AdminPrefixMiddleware(app.wsgi_app)

from fas import register_fas
from coinpay import register_coinpay, init_coin_db, controller_context
register_fas(app)
register_coinpay(app)


def connect():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS vouchers(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, minutes INTEGER NOT NULL, rate_down INTEGER NOT NULL DEFAULT 10, rate_up INTEGER NOT NULL DEFAULT 10, created_at INTEGER NOT NULL, redeemed_at INTEGER, expires_at INTEGER, client_id TEXT, status TEXT NOT NULL DEFAULT 'unused');
        CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, client_id TEXT NOT NULL, ip TEXT, mac TEXT, voucher_code TEXT, started_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'active', nds_token TEXT, FOREIGN KEY(voucher_code) REFERENCES vouchers(code));
        CREATE TABLE IF NOT EXISTS coin_events(id INTEGER PRIMARY KEY, device_id TEXT NOT NULL, pulses INTEGER NOT NULL, created_at INTEGER NOT NULL, nonce TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_voucher_status ON vouchers(status);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status, expires_at);
        ''')
        # Upgrade databases created by earlier PieFi builds before BinAuth uses nds_token.
        session_cols = {r['name'] for r in c.execute('PRAGMA table_info(sessions)')}
        if 'nds_token' not in session_cols:
            c.execute('ALTER TABLE sessions ADD COLUMN nds_token TEXT')
    init_coin_db()


def audit(action, detail=''):
    with connect() as c:
        c.execute('INSERT INTO audit(at,actor,action,detail) VALUES(?,?,?,?)', (int(time.time()), session.get('user', 'system'), action, detail[:500]))


def login_required(fn):
    @wraps(fn)
    def inner(*a, **kw):
        if not session.get('admin'):
            if request.path.startswith('/api/'): return jsonify(ok=False, error='authentication_required'), 401
            return redirect(url_for('login', next=request.path))
        return fn(*a, **kw)
    return inner


def read_counter(iface, key):
    try: return int(Path('/sys/class/net', iface, 'statistics', key).read_text().strip())
    except Exception: return 0


def system_info():
    try:
        load = os.getloadavg()
        cpu = round(min(100, load[0] * 100 / max(1, os.cpu_count() or 1)), 1)
    except Exception: cpu = None
    try:
        mem = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            k, v = line.split(':', 1); mem[k] = int(v.strip().split()[0])
        ram_total = mem.get('MemTotal', 0) // 1024
        ram_used = (mem.get('MemTotal', 0) - mem.get('MemAvailable', mem.get('MemFree', 0))) // 1024
    except Exception: ram_total = ram_used = 0
    interfaces=[]
    for p in Path('/sys/class/net').glob('*'):
        if p.name == 'lo': continue
        try: state=(p/'operstate').read_text().strip()
        except Exception: state='unknown'
        interfaces.append({'name':p.name,'state':state,'mac':(p/'address').read_text().strip() if (p/'address').exists() else '', 'rx':read_counter(p.name,'rx_bytes'),'tx':read_counter(p.name,'tx_bytes')})
    return {'hostname':platform.node(),'platform':platform.platform(),'kernel':platform.release(),'cpu_count':os.cpu_count() or 1,'cpu_load_percent':cpu,'ram_used_mb':ram_used,'ram_total_mb':ram_total,'interfaces':interfaces,'mode':'live' if Path('/proc').exists() else 'demo'}


@app.context_processor
def common(): return {'version':VERSION, **controller_context()}

@app.template_filter('datetime')
def fmt_datetime(value):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(value))) if value else '—'

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username','') == ADMIN_USER and check_password_hash(ADMIN_HASH, request.form.get('password','')):
            session.clear(); session['admin']=True; session['user']=ADMIN_USER
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
def customer_portal():
    return render_template('portal.html')


@app.route('/dashboard')
@login_required
def dashboard():
    now=int(time.time())
    with connect() as c:
        c.execute("UPDATE sessions SET status='expired' WHERE status='active' AND expires_at<=?", (now,))
        stats={k:c.execute(q).fetchone()[0] for k,q in {
            'vouchers_total':'SELECT COUNT(*) FROM vouchers','vouchers_unused':"SELECT COUNT(*) FROM vouchers WHERE status='unused'",'vouchers_used':"SELECT COUNT(*) FROM vouchers WHERE status='used'",'sessions_active':"SELECT COUNT(*) FROM sessions WHERE status='active'",'sessions_expired':"SELECT COUNT(*) FROM sessions WHERE status='expired'"}.items()}
        vouchers=c.execute('SELECT * FROM vouchers ORDER BY id DESC LIMIT 12').fetchall()
        clients=c.execute("SELECT * FROM sessions WHERE status='active' ORDER BY started_at DESC LIMIT 12").fetchall()
        events=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 10').fetchall()
    return render_template('dashboard.html', stats=stats, sys=system_info(), vouchers=vouchers, clients=clients, events=events, now=now)

@app.route('/vouchers')
@login_required
def vouchers_page():
    with connect() as c: rows=c.execute('SELECT * FROM vouchers ORDER BY id DESC LIMIT 500').fetchall()
    return render_template('vouchers.html', rows=rows)

@app.route('/vouchers/create', methods=['POST'])
@login_required
def create_voucher():
    try:
        count=max(1,min(100,int(request.form.get('count','1')))); minutes=max(1,min(10080,int(request.form.get('minutes','60')))); down=max(1,min(1000,int(request.form.get('rate_down','10')))); up=max(1,min(1000,int(request.form.get('rate_up','10'))))
    except ValueError: flash('Invalid numeric value','error'); return redirect(url_for('vouchers_page'))
    made=[]
    with connect() as c:
        for _ in range(count):
            for attempt in range(10):
                code=secrets.token_hex(3).upper()
                try:
                    c.execute('INSERT INTO vouchers(code,minutes,rate_down,rate_up,created_at) VALUES(?,?,?,?,?)',(code,minutes,down,up,int(time.time())))
                    made.append(code); break
                except sqlite3.IntegrityError: continue
    audit('voucher.create', f'count={len(made)} minutes={minutes}')
    flash(f'Created {len(made)} voucher(s): {", ".join(made[:8])}' + ('…' if len(made)>8 else ''), 'success')
    return redirect(url_for('vouchers_page'))

@app.route('/vouchers/<int:vid>/delete', methods=['POST'])
@login_required
def delete_voucher(vid):
    with connect() as c: c.execute('DELETE FROM vouchers WHERE id=? AND status="unused"',(vid,))
    audit('voucher.delete', f'id={vid} (unused only)'); flash('Unused voucher deleted if it existed.','success')
    return redirect(url_for('vouchers_page'))

@app.route('/vouchers.csv')
@login_required
def export_vouchers():
    out=io.StringIO(); w=csv.writer(out); w.writerow(['code','minutes','download_mbps','upload_mbps','status','created_at','redeemed_at','client_id'])
    with connect() as c:
        for r in c.execute('SELECT * FROM vouchers ORDER BY id DESC'): w.writerow([r['code'],r['minutes'],r['rate_down'],r['rate_up'],r['status'],r['created_at'],r['redeemed_at'],r['client_id']])
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=piefi-vouchers.csv'})

@app.route('/api/voucher/redeem', methods=['POST'])
def redeem():
    data=request.get_json(silent=True) or {}; code=str(data.get('code','')).strip().upper(); client=str(data.get('client_id','unknown'))[:128]; ip=str(data.get('ip',''))[:45]; mac=str(data.get('mac',''))[:32]; now=int(time.time())
    if not code: return jsonify(ok=False,error='code_required'),400
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM vouchers WHERE code=?',(code,)).fetchone()
        if not row: return jsonify(ok=False,error='invalid_voucher'),404
        if row['status']!='unused': return jsonify(ok=False,error='already_used'),409
        expiry=now+row['minutes']*60
        c.execute("UPDATE vouchers SET status='used',redeemed_at=?,expires_at=?,client_id=? WHERE id=? AND status='unused'",(now,expiry,client,row['id']))
        c.execute("INSERT INTO sessions(client_id,ip,mac,voucher_code,started_at,expires_at,status) VALUES(?,?,?,?,?,?, 'active')",(client,ip,mac,code,now,expiry))
        sid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    return jsonify(ok=True,session_id=sid,minutes=row['minutes'],expires_at=expiry,rate_down_mbps=row['rate_down'],rate_up_mbps=row['rate_up'],note='Voucher and session recorded. Live network authorization requires the captive-portal enforcement adapter, which is not enabled in this release.')

@app.route('/api/status')
@login_required
def api_status():
    with connect() as c:
        counts={'active_sessions':c.execute("SELECT COUNT(*) FROM sessions WHERE status='active' AND expires_at>?",(int(time.time()),)).fetchone()[0], 'unused_vouchers':c.execute("SELECT COUNT(*) FROM vouchers WHERE status='unused'").fetchone()[0]}
    return jsonify(ok=True,version=VERSION,system=system_info(),counts=counts,coin=controller_context())

@app.route('/api/sessions')
@login_required
def api_sessions():
    with connect() as c: rows=[dict(r) for r in c.execute('SELECT * FROM sessions ORDER BY id DESC LIMIT 200')]
    return jsonify(ok=True,sessions=rows)

@app.route('/api/sessions/<int:sid>/disconnect', methods=['POST'])
@login_required
def disconnect_session(sid):
    with connect() as c:
        row=c.execute("SELECT mac,ip,status FROM sessions WHERE id=?",(sid,)).fetchone()
    if not row or row['status']!='active':
        return jsonify(ok=False,error='session_not_active'),404
    target=(row['mac'] or row['ip'] or '').strip()
    if not target:
        return jsonify(ok=False,error='client_address_missing'),400
    try:
        result=subprocess.run(['/usr/bin/ndsctl','deauth',target],capture_output=True,text=True,timeout=8,check=True)
    except FileNotFoundError:
        return jsonify(ok=False,error='ndsctl_not_installed'),503
    except subprocess.CalledProcessError as exc:
        return jsonify(ok=False,error='ndsctl_deauth_failed',detail=(exc.stderr or exc.stdout or '')[:300]),502
    except subprocess.TimeoutExpired:
        return jsonify(ok=False,error='ndsctl_timeout'),504
    with connect() as c:
        c.execute("UPDATE sessions SET status='disconnected' WHERE id=? AND status='active'",(sid,))
    audit('session.disconnect',f'id={sid} client={target}')
    return jsonify(ok=True,session_id=sid,client=target,note='OpenNDS deauthentication command completed.')

@app.route('/settings')
@login_required
def settings_page(): return render_template('settings.html', sys=system_info())

@app.route('/logs')
@login_required
def logs_page():
    with connect() as c: rows=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200').fetchall()
    return render_template('logs.html', rows=rows)

@app.route('/health')
def health():
    db_ok = False
    try:
        with connect() as c:
            c.execute('SELECT 1').fetchone()
        db_ok = True
    except Exception:
        pass
    return jsonify(ok=db_ok, service='pieFi', version=VERSION,
                   database='ok' if db_ok else 'error')

if __name__ == '__main__':
    init_db()
    app.run(host=os.environ.get('PIEFI_BIND','127.0.0.1'),port=int(os.environ.get('PIEFI_PORT','8080')),debug=False)
