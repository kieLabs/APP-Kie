# APK KIE backend

See the root `README.md` for Docker deployment, environment variables, Blogger setup, security notes and API reference.

Run locally (requires Java, Gradle and Android SDK):

```bash
python -m venv .venv
pip install -r requirements.txt
export SIGNING_SECRET='your-long-private-secret'
export ANDROID_HOME="$HOME/Android/Sdk"
uvicorn app.main:app --reload --port 8000
```

The process needs writable storage at `APK_KIE_DATA_DIR` (default `/data/apk-kie`). For a local computer, set it to a user-writable path such as `./data`.
