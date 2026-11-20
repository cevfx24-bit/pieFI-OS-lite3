# PieFi source upload checklist

- [ ] Upload existing `files/` overlay tree
- [ ] Upload build script
- [ ] Upload package list/configuration files used by ImageBuilder
- [ ] Upload Flask app, templates, and static assets
- [ ] Upload Nginx/OpenNDS configuration and FAS files
- [ ] Review and remove credentials, private keys, tokens, and personal data
- [ ] Run GitHub Actions source-check
- [ ] Add route tests for `/admin` and `/`
- [ ] Add OpenWrt ImageBuilder build job only after source layout is reviewed
