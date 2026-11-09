# APK KIE repository map

```text
APK-KIE/
├── .github/workflows/backend-tests.yml  # CI tests on pushes and pull requests
├── blogger/apk-kie-theme.xml            # Upload this file as Blogger theme
├── frontend/                             # Frontend notes and optional static assets
├── backend/                              # FastAPI + Android build service
│   ├── app/main.py                       # API routes
│   ├── app/builder.py                    # Generates Android WebView project + Gradle build
│   ├── app/models.py                     # Request validation
│   ├── app/database.py                   # Build history storage
│   ├── tests/                            # Backend unit tests
│   ├── Dockerfile                        # Android SDK + Python image
│   └── .env.example                      # Safe configuration template
├── android-template/                     # Notes; project generated per build by builder.py
├── scripts/                              # Local helper scripts
├── docker-compose.yml                    # VPS deployment
├── README.md                             # Main setup guide
└── SECURITY.md                           # Deployment security notes
```

`android-template/` is intentionally not a complete Gradle app checked into Git. `backend/app/builder.py` generates a fresh Android project for each requested build using that build's validated settings.
