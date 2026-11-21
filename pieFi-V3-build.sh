#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="25.12.6"
ROOT="$HOME/piefi-build-v3"
FILES="$ROOT/files"
BUILDER="$HOME/piefi-build/openwrt-imagebuilder-${VERSION}-x86-64.Linux-x86_64"
OUT="$BUILDER/bin/targets/x86/64"
FINAL="$ROOT/output/PIEFI-V3-UPDATED"
PKGLIST="$ROOT/piefi-v3-packages.txt"

fail() { echo "[ERROR] $*" >&2; exit 1; }
say() { echo; echo "[pieFi V3 COMPLETE] $*"; }

[[ "$(uname -m)" == "x86_64" ]] || fail "Kailangan ang 64-bit Ubuntu/WSL."
[[ -f "$BUILDER/Makefile" ]] || fail "ImageBuilder Makefile missing: $BUILDER"
[[ -s "$PKGLIST" ]] || fail "Package list missing."

# Preserve the existing V3 source tree. This script never deletes files/ or output.
for f in \
  etc/config/network etc/config/dhcp etc/config/nginx etc/config/opennds \
  etc/init.d/piefi etc/init.d/piefi-net etc/rc.d/S99piefi-net \
  etc/uci-defaults/99-piefi-firstboot etc/hotplug.d/net/95-piefi-net \
  etc/nginx/conf.d/piefi.conf usr/sbin/piefi-net-detect \
  opt/piefi/app/app.py opt/piefi/app/fas.py opt/piefi/app/binauth.py \
  opt/piefi/app/coinpay.py opt/piefi/app/piefi-binauth.sh \
  opt/piefi/app/templates/coin.html
 do [[ -s "$FILES/$f" ]] || fail "Missing required V3 file: $f"; done
[[ -s "$ROOT/firmware/esp32/piefi_coin_esp32.ino" ]] || fail "Missing ESP32 primary firmware."
[[ -s "$ROOT/firmware/esp8266/piefi_coin_esp8266.ino" ]] || fail "Missing ESP8266 backup firmware."

# nginx package is installed by ImageBuilder; its restrict_locally include is supplied by package files at runtime.
# Do not copy a fake include into the overlay. Verify that the configuration references the packaged include.
grep -q "include restrict_locally;" "$FILES/etc/nginx/conf.d/piefi.conf" || fail "Expected nginx local restriction include missing."

say "Shell syntax checks..."
for f in etc/uci-defaults/99-piefi-firstboot etc/init.d/piefi etc/init.d/piefi-net \
         usr/sbin/piefi-net-detect etc/hotplug.d/net/95-piefi-net \
         opt/piefi/app/piefi-binauth.sh; do sh -n "$FILES/$f"; done

say "Python syntax checks..."
python3 - "$FILES/opt/piefi/app" <<'PYCODE'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
for name in ('app.py','fas.py','binauth.py','coinpay.py'):
 p=root/name; compile(p.read_text(),str(p),'exec'); print('OK:',name)
PYCODE

# Confirm captive portal / coin / auto-network config is actually staged.
grep -q "gatewayinterface 'br-lan'" "$FILES/etc/config/opennds" || fail "OpenNDS is not bound to br-lan."
grep -q "eth0" "$FILES/usr/sbin/piefi-net-detect" || fail "WAN eth0 mapping missing."
grep -q "eth1" "$FILES/usr/sbin/piefi-net-detect" || fail "LAN eth1 mapping missing."
grep -q "10.0.0.1" "$FILES/usr/sbin/piefi-net-detect" || fail "LAN gateway missing."
grep -q "coinpay" "$FILES/opt/piefi/app/app.py" || fail "Coin integration not registered in Flask app."

PACKAGES="$(tr '\n' ' ' < "$PKGLIST")"
mkdir -p "$FINAL"
cd "$BUILDER"
say "ImageBuilder profile check..."
make info > "$ROOT/imagebuilder-info-v3.txt" 2>&1 || fail "ImageBuilder profile check failed."

say "Building complete PieFi V3 (single-job build)..."
make -j1 image PROFILE=generic PACKAGES="$PACKAGES" FILES="$FILES" || fail "ImageBuilder build failed. HUWAG mag-flash."

# Do not use the first wildcard manifest blindly; select the generic x86-64 manifest.
mapfile -t MANIFESTS < <(find "$OUT" -maxdepth 1 -type f -name '*x86-64-generic*.manifest' -printf '%T@ %p\n' | sort -nr | cut -d' ' -f2-)
((${#MANIFESTS[@]})) || fail "Walang x86-64 generic manifest."
MANIFEST="${MANIFESTS[0]}"
for pkg in opennds kmod-usb-net-rtl8152 nginx-ssl nginx-ssl-util python3-flask python3-sqlite3; do
 grep -q "^${pkg} " "$MANIFEST" || fail "Package missing from manifest: $pkg"; done

shopt -s nullglob
IMAGES=("$OUT"/*x86-64-generic-*combined*.img.gz)
((${#IMAGES[@]})) || fail "Walang combined x86-64 generic firmware image."
NEW_IMAGES=()
for image in "${IMAGES[@]}"; do
 name="PieFI-OS-Lite-V3-$(basename "$image")"
 dest="$FINAL/$name"
 cp -f "$image" "$dest"
 gzip -t "$dest" || fail "Gzip integrity check failed: $name"
 NEW_IMAGES+=("$name")
done
cp "$MANIFEST" "$FINAL/MANIFEST-pieFi-v3.txt"
(cd "$FINAL" && sha256sum "${NEW_IMAGES[@]}" > SHA256SUMS-pieFi-v3.txt)

cat > "$FINAL/BUILD-INFO-pieFi-v3.txt" <<INFO
PieFi OS Lite V3 COMPLETE BUILD
Base: OpenWrt $VERSION ImageBuilder; x86/64 generic
WAN: fixed eth0 DHCP; LAN: fixed eth1 USB Ethernet; br-lan 10.0.0.1/24
DHCP: customer LAN enabled by piefi-net-detect after NIC enumeration
Captive portal: OpenNDS enabled on br-lan; standard client captive-portal detection (CPD) on supported phones/computers
Portal FAS: Flask /fas/fas-hid.php; OpenNDS FAS port 2080
Dashboard: http://10.0.0.1/admin (Nginx :80 -> Flask :8080)
Coin page: http://10.0.0.1/admin/coin; ESP32 primary / ESP8266 backup
First boot admin: admin / piefi3645 (root-only credentials file)
Validation: source presence, shell/Python syntax, package manifest, gzip integrity, SHA256
Not yet hardware-proven: Dell boot, live WAN/LAN link, CPD popup behavior, voucher auth, ESP coin pulse/payment.
INFO
say "BUILD OUTPUT AND CHECKS COMPLETE"
printf '%s\n' "${NEW_IMAGES[@]}"
echo "Output: $FINAL"
echo "Manifest: $FINAL/MANIFEST-pieFi-v3.txt"
echo "Checksums: $FINAL/SHA256SUMS-pieFi-v3.txt"
