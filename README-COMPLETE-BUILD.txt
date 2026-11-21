PIEFI OS LITE V3 — COMPLETE BUILD SOURCE

This package merges the existing V3 source with the previously supplied FIX2 ESP32/ESP8266 coin integration. It retains the Flask dashboard, FAS voucher flow, OpenNDS, coin payment pages, firmware sketches, network detector, firstboot setup, and branding files.

INSTALL INTO EXISTING WSL PROJECT (creates a backup first; does not delete the project):
  cd ~
  cp -a piefi-build-v3 piefi-build-v3.backup-before-complete-$(date +%Y%m%d-%H%M%S)
  unzip -o /mnt/c/Users/CEV/Downloads/PIEFI-OS-LITE-V3-COMPLETE-BUILD.zip -d ~/piefi-build-v3

The ZIP contents are rooted at the project level, so this overlays the existing source tree. It does not delete extra files or the output folder.

BUILD:
  cd ~/piefi-build-v3
  chmod +x pieFi-V3-build.sh
  ./PIEFI-V3-MASTER-COMMAND.sh

LOG: tail -f ~/piefi-build-v3/build-piefi-v3-updated.log
OUTPUT: ~/piefi-build-v3/output/PIEFI-V3-UPDATED

NETWORK TARGET: eth0 WAN DHCP; eth1 USB LAN; br-lan 10.0.0.1/24. Startup and hotplug scripts wait for interface enumeration and configure the bridge automatically.

AUTOP0PUP: OpenNDS is enabled on br-lan and uses captive-portal detection (CPD). Devices that support CPD should display their sign-in popup. OS captive-portal behavior varies, so no firmware can guarantee a popup on every device or when connectivity-check traffic is blocked.

COIN: ESP32 primary / ESP8266 standby. Configure packages and exact measured pulse-to-denomination mapping in /admin/coin before live payment. Never connect a 12V coin acceptor output directly to a GPIO.

VALIDATION LIMIT: Build checks cover source presence, shell/Python syntax, package manifest, and compressed-image integrity. Actual Dell Wyse boot, Ethernet carrier, internet routing, captive-portal popup, and real coin authorization still require hardware testing. Do not flash if build checks fail.
