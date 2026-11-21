#!/bin/sh
# pieFi OS Lite - OpenNDS Custom BinAuth
# Default binauth_log.sh remains responsible for client logging and restore.

PIEFI_BINAUTH="/opt/piefi/app/binauth.py"

if [ "$1" = "auth_client" ]; then
    result=$(/usr/bin/python3 "$PIEFI_BINAUTH" "$@" 2>/dev/null)
    rc=$?

    if [ "$rc" -ne 0 ] || [ -z "$result" ]; then
        exitlevel=1
    else
        IFS=' ' read -r session_length upload_rate download_rate upload_quota download_quota exitlevel <<EOF
$result
EOF
    fi
else
    /usr/bin/python3 "$PIEFI_BINAUTH" "$@" >/dev/null 2>&1
fi
