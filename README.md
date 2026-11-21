# PieFi OS Stage 2 — x86 Gateway Build Scaffold

This stage prepares a reproducible OpenWrt x86/64 image build using the official OpenWrt ImageBuilder.
It is a gateway OS scaffold, not yet the upstream OpenPisoWiFi portal integration.

## Build
Run the GitHub Actions workflow `Build PieFi x86_64` in your repository. It downloads the official OpenWrt ImageBuilder for x86/64 and builds a generic x86/64 image with the selected packages and PieFi configuration files.

## Important
- Test in QEMU/VM first; do not install over a production machine.
- OpenWrt x86/64 image is the base system. Portal/vending features are staged separately and must be integrated/tested.
- ImageBuilder versions are pinned by workflow inputs/config for reproducibility; update them deliberately.
