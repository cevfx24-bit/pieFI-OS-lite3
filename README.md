# PieFi OS Lite Integrated Image Builder (x86-64)

This kit builds a **custom OpenWrt x86-64 image** with PieFi branding, openNDS, LuCI, SQLite and common administration/network packages. It also installs a small local PieFi landing/service placeholder.

> Build output is a firmware image, not yet a production-tested PisoWiFi appliance. The portal-credit-to-openNDS authorization path and coin-reader hardware driver still require integration and hardware testing.

## Build in GitHub Codespaces (Ubuntu)

1. Upload this folder to a GitHub repository.
2. Open the repository in Codespaces.
3. In Terminal run:

```bash
chmod +x scripts/build.sh
./scripts/build.sh
```

The script downloads the OpenWrt ImageBuilder for the release configured in `scripts/build.sh` (default `24.10.5`) and builds x86-64 combined EFI/BIOS image output where supported by the ImageBuilder target.

Build output is in `output/`. The `.img.gz` is the image to write to USB/SSD using a disk image writer. **Writing it erases the target drive.**

## Change release

Edit the `RELEASE` setting near the top of `scripts/build.sh` to a release available in the official OpenWrt downloads directory. This build kit deliberately pins a release instead of silently changing versions.

## Included package selection

openNDS, LuCI, firewall4/nftables, dnsmasq, SQLite, Python 3, USB/serial tools, basic diagnostics, and common x86 drivers. Package availability varies by release.

## Current limits

- No tested coin acceptor hardware connection yet.
- The installed PieFi web service is a foundation/placeholder, not full account-credit captive authorization.
- Configure WAN/LAN interfaces for your specific hardware before deployment.
- Do not expose the admin interface to the public internet.
