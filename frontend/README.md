# APK KIE Frontend

Static responsive dashboard for GitHub Pages. It provides Quick and Advanced app configuration, API connection settings, build submission, build status polling, build history, and artifact download links.

## GitHub Pages deployment

1. Keep this folder at `frontend/` in the repository root.
2. Push the repository's default branch (`main`).
3. Open **Settings → Pages** and set **Source** to **GitHub Actions**.
4. The workflow `.github/workflows/deploy-frontend.yml` publishes the contents of this folder.
5. Open `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/`.

## Connect the backend

In the dashboard, select **API settings** and enter the public HTTPS base URL of the deployed FastAPI service, for example `https://api.example.com`. Save it, then use **Test connection**. The backend must allow the Pages origin in its `ALLOWED_ORIGINS` environment variable, e.g. `https://YOUR-USERNAME.github.io` (CORS origins do not include the repository path).

The dashboard does not compile Android apps in the browser. Actual APK/AAB generation requires the FastAPI backend, Android SDK, Java, Gradle, signing configuration, persistent storage, and server-side security controls. A missing backend URL or missing signing/build setup will prevent a real build.

## Configuration

The API URL is entered at runtime and saved in the current browser's local storage. No secret or signing key belongs in this frontend. The backend must use HTTPS and should be protected against abuse before public launch.
