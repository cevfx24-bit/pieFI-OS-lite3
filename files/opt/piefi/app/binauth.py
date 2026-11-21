#!/usr/bin/python3
import base64, os, sqlite3, sys, time
from urllib.parse import unquote
DB=os.environ.get('PIEFI_DB','/etc/piefi/piefi.sqlite3')

def decode_custom(value):
    try:
        raw=base64.b64decode(unquote(value),validate=True).decode('utf-8')
        if raw.startswith('piefi:') or raw.startswith('piefi-coin:'):
            return raw.split(':',1)
    except Exception:
        pass
    return None

def emit(allow, minutes=0, upload=0, download=0):
    print(int(minutes),int(upload),int(download),0,0,0 if allow else 1)

def main():
    if len(sys.argv)<2:
        emit(False); return
    method=sys.argv[1]; now=int(time.time())
    with sqlite3.connect(DB,timeout=10) as c:
        c.row_factory=sqlite3.Row
        if method=='auth_client':
            # OpenNDS v10+: arg2 MAC, arg7 client IP, arg8 client token, arg9 custom.
            if len(sys.argv)<10: emit(False); return
            mac=sys.argv[2].strip().lower(); ip=sys.argv[7].strip(); token=sys.argv[8].strip()
            parsed=decode_custom(sys.argv[9])
            if not parsed: emit(False); return
            kind,reservation=parsed
            if kind=='piefi':
                row=c.execute('''SELECT p.*,v.minutes,v.rate_down,v.rate_up FROM pending_auth p JOIN vouchers v ON v.code=p.voucher_code WHERE p.id=?''',(reservation,)).fetchone()
                valid=bool(row and row['status']=='pending' and row['expires_at']>now and row['client_ip']==ip and row['client_mac'].lower()==mac and row['voucher_code'])
                if valid:
                    c.execute('UPDATE pending_auth SET client_token=? WHERE id=?',(token,reservation))
                    emit(True,row['minutes'],row['rate_up']*1000,row['rate_down']*1000); return
            elif kind=='piefi-coin':
                row=c.execute('SELECT * FROM coin_pending_auth WHERE id=?',(reservation,)).fetchone()
                valid=bool(row and row['status']=='pending' and row['expires_at']>now and row['client_ip']==ip and row['client_mac'].lower()==mac)
                if valid:
                    c.execute('UPDATE coin_pending_auth SET client_token=? WHERE id=?',(token,reservation))
                    emit(True,row['minutes'],row['rate_up']*1000,row['rate_down']*1000); return
            emit(False); return

        if method=='client_auth':
            # OpenNDS non-auth methods: arg2 MAC, arg7 client token.
            if len(sys.argv)<8: return
            mac=sys.argv[2].strip().lower(); token=sys.argv[7].strip()
            if not token: return
            c.execute('BEGIN IMMEDIATE')
            p=c.execute('SELECT * FROM pending_auth WHERE client_token=? AND client_mac=?',(token,mac)).fetchone()
            if p and p['status']=='pending' and p['expires_at']>now:
                v=c.execute("SELECT * FROM vouchers WHERE code=? AND status='unused'",(p['voucher_code'],)).fetchone()
                if v:
                    expiry=now+int(v['minutes'])*60
                    upd=c.execute("UPDATE vouchers SET status='used',redeemed_at=?,expires_at=?,client_id=? WHERE code=? AND status='unused'",(now,expiry,mac,p['voucher_code']))
                    if upd.rowcount==1:
                        c.execute("INSERT INTO sessions(client_id,ip,mac,voucher_code,started_at,expires_at,status,nds_token) VALUES(?,?,?,?,?,?, 'active',?)",(mac,p['client_ip'],mac,p['voucher_code'],now,expiry,token))
                        c.execute("UPDATE pending_auth SET status='authorized' WHERE id=?",(p['id'],))
                return
            cp=c.execute('SELECT * FROM coin_pending_auth WHERE client_token=? AND client_mac=?',(token,mac)).fetchone()
            if cp and cp['status']=='pending' and cp['expires_at']>now:
                expiry=now+int(cp['minutes'])*60
                c.execute("INSERT INTO sessions(client_id,ip,mac,voucher_code,started_at,expires_at,status,nds_token) VALUES(?,?,?,NULL,?,?, 'active',?)",(mac,cp['client_ip'],mac,now,expiry,token))
                c.execute("UPDATE coin_pending_auth SET status='authorized' WHERE id=?",(cp['id'],))
                c.execute("UPDATE coin_sessions SET status='authorized' WHERE id=?",(cp['coin_session_id'],))
            return

        if method in ('client_deauth','idle_deauth','timeout_deauth','downquota_deauth','upquota_deauth','downrate_deauth','uprate_deauth','ndsctl_deauth','shutdown_deauth'):
            if len(sys.argv)<8: return
            mac=sys.argv[2].strip().lower(); token=sys.argv[7].strip()
            status='expired' if method in ('timeout_deauth','idle_deauth') else 'disconnected'
            if token:
                c.execute("UPDATE sessions SET status=? WHERE nds_token=? AND lower(mac)=? AND status='active'",(status,token,mac))
            else:
                c.execute("UPDATE sessions SET status=? WHERE lower(mac)=? AND status='active'",(status,mac))
            if token:
                c.execute("UPDATE pending_auth SET status='finished' WHERE client_token=?",(token,))
                c.execute("UPDATE coin_pending_auth SET status='finished' WHERE client_token=?",(token,))
            return

if __name__=='__main__':
    try: main()
    except Exception:
        if len(sys.argv)>1 and sys.argv[1]=='auth_client': emit(False)
        sys.exit(1)
