# PieFi OS Lite Reloaded — Stage 7

Adds a protected ESP coin-node API endpoint to the Stage 6 prototype. Node API requires bearer token, valid MAC and unique event key; duplicate keys are rejected by SQLite.

## Build
Use GitHub Actions (`workflow_dispatch`) to build OpenWrt x86/64 via ImageBuilder. Firmware and hardware are **not verified** until build succeeds and image is boot-tested.

## First boot
- Default LAN target: 10.0.0.1 (UCI defaults).
- PieFi service creates admin token at `/etc/piefi/token` and node token at `/etc/piefi/node-token`.
- Tokens are root-readable; copy securely and never publish them.
- API port 8080; health route `/api/health`.
- Admin APIs use `Authorization: Bearer <admin token>`.
- Coin node: `POST /api/node/coin`, `Authorization: Bearer <node token>`, JSON `{device: 'AA:BB:CC:DD:EE:FF', credits: 1, event_key: 'unique-id'}`.
- Do not expose the node API to the public internet. Firewall isolation remains to be implemented.

## Caveats
OpenNDS auth/deauth behavior, session-expiration deauth, portal/FAS flow, coin-node wiring, topology and image build still require verification. Development source only, not production-ready.
