# Security notes

- Never commit `backend/.env`, signing keys, passwords, API tokens, customer uploads, or generated APK/AAB files.
- Keep the build API behind HTTPS and authentication before public launch. CORS is not authentication.
- Restrict allowed origins in `backend/.env`; do not leave wildcard origins for a public deployment.
- Apply request-size limits, abuse controls, monitoring, backups and malware scanning before accepting public uploads.
- Only package websites that you own or are authorized to distribute.
- Back up the persistent `/data/apk-kie` volume securely. It contains signing material and build records.
