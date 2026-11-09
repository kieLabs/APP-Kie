# Frontend / Blogger Theme

The public APK KIE interface is currently delivered as a Blogger XML theme:

- Import `../blogger/apk-kie-theme.xml` in Blogger via **Theme → Restore → Upload**.
- Configure the `API_BASE` constant in the theme with the HTTPS URL of the deployed FastAPI backend.
- The theme is responsive and serves one layout for phones, tablets and desktops. No separate “web version” button is required.

This folder is reserved for optional standalone static frontend assets in a future version. Blogger XML is not deployed to GitHub Pages as a running backend.
