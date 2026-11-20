# PieFi OS Lite V3 — GitHub staging

This starter adds a basic GitHub Actions source inventory and syntax-check workflow.

**This is not a fixed firmware image.** The workflow does not yet build OpenWrt or prove that the admin dashboard/captive portal work on the Wyse 5070. Upload the existing PieFi source files into this repository first; then CI can be extended to test actual Flask routes, portal files, Nginx, and OpenNDS.

Target URLs:
- Admin: `http://10.0.0.1/admin`
- Portal: `http://10.0.0.1/`

## Upload
Extract this ZIP and upload its contents (including the `.github` folder) into the repository root. Then upload the existing PieFi source tree separately. Do not upload firmware images, secrets, private keys, or passwords.
