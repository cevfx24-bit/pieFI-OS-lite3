# PieFI OS Lite terminal identity
case "$-" in
  *i*)
    HOSTNAME="$(cat /proc/sys/kernel/hostname 2>/dev/null)"
    [ -n "$HOSTNAME" ] || HOSTNAME="piefi"
    export PS1="\033[1;36m\u@${HOSTNAME}\033[0m:\033[1;32m\w\033[0m\# "
    printf '\033[1;36mPieFI OS Lite V3\033[0m\n'
    printf '\033[0;36mPisoWiFi Network Operating System\033[0m\n\n'
    ;;
esac
