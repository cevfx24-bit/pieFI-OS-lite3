#!/usr/bin/env bash
set -euo pipefail

# Pin to an OpenWrt release known to have an x86/64 ImageBuilder. Change as desired.
RELEASE="${RELEASE:-24.10.5}"
TARGET="x86/64"
BASE="https://downloads.openwrt.org/releases/${RELEASE}/targets/x86/64"
WORK="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$WORK/.imagebuilder"
OUT="$WORK/output"
mkdir -p "$TMP" "$OUT"

if ! command -v wget >/dev/null || ! command -v tar >/dev/null; then
  echo "Install wget and tar first (Codespaces Ubuntu usually has them)." >&2; exit 1
fi

# Resolve archive format by probing common ImageBuilder archive names.
ARCHIVE=""
for suffix in tar.xz tar.zst; do
  candidate="openwrt-imagebuilder-${RELEASE}-${TARGET//\//-}.${suffix}"
  if wget -q --spider "$BASE/$candidate"; then ARCHIVE="$candidate"; break; fi
done
if [[ -z "$ARCHIVE" ]]; then
  echo "Could not locate ImageBuilder archive for OpenWrt ${RELEASE} at ${BASE}. Check release availability." >&2
  exit 2
fi

if [[ ! -d "$TMP/ib" ]]; then
  echo "Downloading $ARCHIVE..."
  wget -q "$BASE/$ARCHIVE" -O "$TMP/$ARCHIVE"
  mkdir -p "$TMP/extract"
  if [[ "$ARCHIVE" == *.xz ]]; then tar -xJf "$TMP/$ARCHIVE" -C "$TMP/extract"; else tar --zstd -xf "$TMP/$ARCHIVE" -C "$TMP/extract"; fi
  extracted="$(find "$TMP/extract" -maxdepth 1 -type d -name 'openwrt-imagebuilder-*' | head -1)"
  [[ -n "$extracted" ]] || { echo "ImageBuilder extraction failed" >&2; exit 3; }
  mv "$extracted" "$TMP/ib"
fi

IB="$TMP/ib"
# Copy overlay into ImageBuilder's files directory.
rm -rf "$IB/files"
cp -a "$WORK/files" "$IB/files"

PACKAGES="luci opennds sqlite3 python3 python3-light python3-logging python3-sqlite3 curl wget ca-bundle openssl-util tcpdump-mini ip-full ethtool usbutils kmod-usb-serial kmod-usb-serial-ftdi kmod-usb-serial-cp210x kmod-usb-serial-ch341 kmod-usb-net kmod-usb-net-rndis kmod-usb-net-cdc-ether kmod-e1000 kmod-e1000e kmod-igb kmod-ixgbe kmod-r8169"

cd "$IB"
make image PROFILE="generic" PACKAGES="$PACKAGES" FILES="$IB/files" || {
  echo "Build failed. Some packages may be unavailable for this release/target; inspect build output." >&2; exit 4;
}

find "$IB/bin/targets/x86/64" -maxdepth 1 -type f \( -name '*combined*.img.gz' -o -name '*combined-efi*.img.gz' \) -exec cp -v {} "$OUT/" \;
find "$IB/bin/targets/x86/64" -maxdepth 1 -type f -name '*manifest*' -exec cp -v {} "$OUT/" \;
if [[ -z "$(find "$OUT" -maxdepth 1 -type f -name '*.img.gz' -print -quit)" ]]; then
  echo "Build succeeded but no image gzip found in output; inspect $IB/bin/targets/x86/64" >&2; exit 5;
fi

echo "Done. Image files are in: $OUT"
