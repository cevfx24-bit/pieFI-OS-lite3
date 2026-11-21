# PieFi OS Lite — GitHub Run Package (Prototype)

This package is an early **portal/credit simulation**, not a finished PisoWiFi firmware.

## Run in GitHub Codespaces
1. Upload this folder to a GitHub repository.
2. Open the repository and select **Code → Codespaces → Create codespace**.
3. In the Codespaces terminal, run:
   ```bash
   python3 app/piefi_portal.py --bind 0.0.0.0 --port 8090
   ```
4. Open the forwarded port 8090 when Codespaces offers it.

## Run locally (Linux/Windows with Python 3)
```bash
python3 app/piefi_portal.py --bind 127.0.0.1 --port 8090
```
Open http://127.0.0.1:8090

## What it does
- Responsive PieFi customer/admin prototype UI
- SQLite ledger with simulated credit balances
- HTTP endpoints: `/health`, `/clients`, `/credit`

## Important
- Simulation only: does **not** authorize clients to use internet.
- Not yet integrated with openNDS, OpenWrt, firewall rules, or coin acceptor hardware.
- Admin view currently lacks authentication; keep it local/lab-only.
- This is not an OpenWrt image builder yet.
