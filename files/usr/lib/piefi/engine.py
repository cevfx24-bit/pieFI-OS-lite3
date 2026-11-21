#!/usr/bin/env python3
"""PieFi session/credit engine prototype. SQLite-backed; API for local integration."""
import os, sqlite3, time, secrets
DB = os.environ.get('PIEFI_DB', '/etc/piefi/piefi.sqlite3')

def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY, device TEXT NOT NULL, credits INTEGER NOT NULL DEFAULT 0,
      seconds INTEGER NOT NULL DEFAULT 0, started INTEGER, expires INTEGER,
      state TEXT NOT NULL DEFAULT 'ready', created INTEGER NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS coin_events (
      id TEXT PRIMARY KEY, device TEXT NOT NULL, amount INTEGER NOT NULL,
      created INTEGER NOT NULL, event_key TEXT UNIQUE)''')
    c.commit(); return c

def add_credit(device, amount, event_key=None):
    if not device or not isinstance(amount,int) or amount<=0: raise ValueError('invalid device or credit amount')
    c=db(); eid=secrets.token_hex(12); now=int(time.time())
    try:
      c.execute('INSERT INTO coin_events VALUES (?,?,?,?,?)',(eid,device,amount,now,event_key));
    except sqlite3.IntegrityError:
      c.close(); return {'duplicate':True}
    s=c.execute("SELECT id FROM sessions WHERE device=? AND state IN ('ready','active','paused') ORDER BY created DESC LIMIT 1",(device,)).fetchone()
    if s: c.execute('UPDATE sessions SET credits=credits+? WHERE id=?',(amount,s['id']))
    else: c.execute('INSERT INTO sessions(id,device,credits,created) VALUES(?,?,?,?)',(secrets.token_hex(12),device,amount,now))
    c.commit(); c.close(); return {'duplicate':False,'credit':amount}

def create_session(device, seconds_per_credit=60):
    c=db(); s=c.execute("SELECT * FROM sessions WHERE device=? AND state IN ('ready','active','paused') ORDER BY created DESC LIMIT 1",(device,)).fetchone()
    if not s or s['credits']<=0: c.close(); raise ValueError('no credits')
    now=int(time.time()); duration=s['credits']*seconds_per_credit
    c.execute("UPDATE sessions SET state='active', credits=0, started=?, expires=?, seconds=? WHERE id=?",(now,now+duration,duration,s['id']))
    c.commit(); c.close(); return {'id':s['id'],'device':device,'seconds':duration,'expires':now+duration}

def pause(session_id):
    c=db(); s=c.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
    if not s or s['state']!='active': c.close(); raise ValueError('session not active')
    left=max(0,s['expires']-int(time.time())); c.execute("UPDATE sessions SET state='paused',seconds=? WHERE id=?",(left,session_id)); c.commit(); c.close(); return left

def resume(session_id):
    c=db(); s=c.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
    if not s or s['state']!='paused' or s['seconds']<=0: c.close(); raise ValueError('session cannot resume')
    now=int(time.time()); c.execute("UPDATE sessions SET state='active',expires=? WHERE id=?",(now+s['seconds'],session_id)); c.commit(); c.close(); return now+s['seconds']

def status():
    c=db(); rows=[dict(r) for r in c.execute('SELECT * FROM sessions ORDER BY created DESC')]; c.close(); now=int(time.time())
    for r in rows:
      if r['state']=='active' and r['expires']<=now: r['state']='expired'
      if r['state']=='active': r['remaining']=max(0,r['expires']-now)
      elif r['state']=='paused': r['remaining']=r['seconds']
      else: r['remaining']=0
    return rows
