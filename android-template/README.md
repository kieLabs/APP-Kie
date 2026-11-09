# Android WebView template

The backend creates a fresh Android project for each build using the form values. The generated project contains:

- Kotlin-free Android Java WebView shell
- HTTPS-only website loading and safe browsing
- Configurable JavaScript and DOM storage
- Optional file chooser support
- Optional camera and microphone web permissions with Android runtime permission prompts
- Custom launcher icon, splash background, status/navigation bar colors
- APK (release) and AAB (release bundle) tasks
- Persistent per-package signing key held on the backend volume

The executable project is generated under the backend's data directory for each build. Do not put signing keys in GitHub.
