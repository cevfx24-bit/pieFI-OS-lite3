#!/bin/sh
# Delegate the stock OpenNDS logger, then apply PieFi's one-use voucher/coin policy.
METHOD="$1"
if [ -x /usr/lib/opennds/binauth_log.sh ]; then
    /usr/lib/opennds/binauth_log.sh "$@" >/dev/null 2>&1 || true
fi
if [ "$METHOD" = "auth_client" ]; then
    exec /usr/bin/python3 /opt/piefi/app/binauth.py "$@"
else
    /usr/bin/python3 /opt/piefi/app/binauth.py "$@" >/dev/null 2>&1 || true
fi
exit 0
