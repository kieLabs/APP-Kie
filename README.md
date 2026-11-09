# APK KIE — Website to Android App Builder

**Standard design starter project** for a Blogger XML frontend and a separate Python + Android build server.

The same website contains three modes:

1. **Quick Builder** — Website URL, app name and icon; creates an APK.
2. **Advanced Builder** — Package name, version, orientation, splash/status/navigation colors, JavaScript, storage, file upload, camera, microphone and fullscreen settings.
3. **Professional Builder** — APK or AAB output, build progress and recent build history.

## Important architecture

Blogger cannot compile Android apps. The Blogger XML file is only the public website and dashboard. The Python FastAPI service runs on a separate server that has Java, Gradle and the Android SDK installed. Do not deploy the backend to GitHub Pages; GitHub Pages only serves static files and cannot run Android Gradle builds.

The generated Android app is a native Android WebView wrapper around the website URL. It does not copy the website into the APK, and the website still needs an internet connection. Sites that depend on unsupported native features, special login flows, DRM, or unusual browser APIs may need additional Android development.

## Folder structure

```text
APK-KIE/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI endpoints and build queue
│   │   ├── builder.py          # Generates and compiles Android projects
│   │   ├── models.py           # Input validation
│   │   └── database.py         # SQLite build history
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── android-template/           # Notes about generated Android template
├── docker-compose.yml
└── README.md
```

## 1) Deploy the backend on a Linux VPS

Use a Linux VPS with Docker installed. For Android builds, a practical starting point is **4 vCPU, 8 GB RAM and at least 25 GB free disk**; a larger machine is recommended for multiple simultaneous builds. The first Docker build downloads Android command-line tools, the Android SDK platform and Gradle dependencies, so it is substantially larger/slower than a normal Python API.

From the project root:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set:

- `SIGNING_SECRET` — a long random secret (keep it private and do not change it after creating signing keys).
- `ALLOWED_ORIGINS` — your Blogger URL, for example `https://yourblog.blogspot.com` or your custom domain.
- Keep `APK_KIE_DATA_DIR=/data/apk-kie`.

Then start the backend:

```bash
docker compose up -d --build
```

Check it:

```bash
curl http://YOUR-SERVER-IP:8000/api/health
```

The API should report `ok: true`, `java_available: true`, `gradle_available: true`, `android_home_set: true` and `signing_secret_configured: true`.

For real use, put the API behind HTTPS using a domain and reverse proxy (for example Caddy or Nginx). Do not expose a build server directly on the public internet without authentication, abuse protection and monitoring.

## 2) Connect the Blogger website to the backend

1. Download the separate `APK-KIE-Blogger-Theme.xml` file supplied with this project. Open it in a text editor.
2. Find this line near the bottom:

   ```js
   const API_BASE = 'https://YOUR-BACKEND-DOMAIN';
   ```

3. Replace it with your backend's HTTPS base URL, without a trailing slash. Example:

   ```js
   const API_BASE = 'https://api.yourdomain.com';
   ```

4. In Blogger, open **Theme → Restore → Upload** and upload `APK-KIE-Blogger-Theme.xml`.
5. Open the blog URL and test the Quick Builder.

The backend's `ALLOWED_ORIGINS` value must match the exact Blogger site origin, including `https://` and any `www` subdomain.

## 3) API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Checks backend tool availability |
| POST | `/api/builds` | Starts an APK or AAB build (multipart form) |
| GET | `/api/builds` | Returns recent build history |
| GET | `/api/builds/{build_id}` | Returns build status, progress and log text |
| GET | `/api/builds/{build_id}/download` | Downloads the completed APK or AAB |

Interactive API documentation is available at `/docs` on the backend.

## 4) Signing keys and updates

The backend creates a persistent signing key for each Android package name under `/data/apk-kie/signing/`. The persistent Docker volume stores these keys, build history and artifacts. **Back up the volume. Do not delete it. Keep the same `SIGNING_SECRET` and package name for app updates.** Increment `Version Code` for each new release. If the signing key is lost, Android will not accept an update signed with a different key as the same app.

Do not commit `backend/.env`, generated `.jks` files, passwords, or production build artifacts to GitHub.

## 5) Security and production readiness

This is a functional starter/MVP, not a public multi-user SaaS service yet. It includes input validation, image validation, per-IP build throttling, CORS configuration, a build timeout, and persistent per-package signing keys. It does **not** yet include user accounts, per-user app ownership, billing, CAPTCHA, malware scanning, admin controls, or a secure customer key-management portal. CORS is not authentication. Keep the build server private until proper authentication and abuse controls are added.

Only build apps for websites you own or are authorized to package. Uploaded icons and websites should be rights-cleared. The app wrapper requests camera/microphone permissions only when enabled and requested by the website.

## 6) Local tests

From `backend/` with Python 3.11+:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
pytest
```

The Android compilation itself must be tested on a machine/container with a compatible JDK, Gradle and Android SDK. The unit tests validate the server-side configuration rules; they do not replace a real APK installation test.

## Current limitations

- AAB is intended for Play Console upload; it is not directly installable like an APK.
- Website content remains online; offline website packaging is not included.
- Push notifications, native billing, Play Integrity, Firebase integration and custom native plugins are not included.
- The frontend is in English in this standard version. It can be translated later.

## GitHub upload (beginner-friendly)

1. Download and extract the project ZIP on your computer.
2. Create a GitHub repository named `APK-KIE`.
3. Upload the **contents** of the extracted `APK-KIE` folder (including the hidden `.github` folder), not the ZIP as a single file.
4. Keep the default branch named `main`. The workflow in `.github/workflows/backend-tests.yml` runs backend tests automatically.
5. The Blogger XML theme is supplied as a separate file: `APK-KIE-Blogger-Theme.xml`. It is not part of the GitHub source ZIP; upload it through Blogger's Theme restore/upload screen.
6. GitHub is used for source-code storage and automated tests. GitHub Pages cannot run the Python API or Android Gradle build server. Deploy `backend/` separately to a Linux VPS with Docker and Android SDK support.

See `START-HERE-HINDI.txt` and `docs/REPOSITORY-STRUCTURE.md` for the Hindi upload guide and folder map. The Blogger XML theme is a separate download.
