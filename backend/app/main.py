from __future__ import annotations

import os
import re
import shutil
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from PIL import Image

from . import database
from .builder import generate_android_project, run_gradle_build
from .models import BuildConfig

APP_VERSION = "1.0.0"
DATA_DIR = Path(os.getenv("APK_KIE_DATA_DIR", "/data/apk-kie"))
MAX_ICON_BYTES = 2 * 1024 * 1024
MAX_BUILDS_PER_HOUR = int(os.getenv("MAX_BUILDS_PER_HOUR", "5"))
SIGNING_SECRET = os.getenv("SIGNING_SECRET", "")
BUILD_LOCK = threading.Semaphore(max(1, int(os.getenv("MAX_PARALLEL_BUILDS", "1"))))
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, Deque[float]] = defaultdict(deque)

app = FastAPI(
    title="APK KIE Build API",
    description="Creates Android WebView APK and AAB builds from user-provided HTTPS websites.",
    version=APP_VERSION,
)

origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def startup() -> None:
    database.init_db()


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"HTTP_{exc.status_code}", "message": message}},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "APK KIE Build API", "version": APP_VERSION, "docs": "/docs"}


@app.get("/api/health")
def health() -> dict[str, object]:
    gradle = shutil.which(os.getenv("GRADLE_COMMAND", "gradle"))
    java = shutil.which(os.getenv("JAVA_COMMAND", "java"))
    return {
        "ok": True,
        "service": "apk-kie-build-api",
        "gradle_available": bool(gradle),
        "java_available": bool(java),
        "android_home_set": bool(os.getenv("ANDROID_HOME")),
        "signing_secret_configured": bool(SIGNING_SECRET),
    }


def _rate_limit(request: Request) -> None:
    limit = max(1, MAX_BUILDS_PER_HOUR)
    ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).timestamp()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS[ip]
        while bucket and now - bucket[0] > 3600:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Build limit reached for this IP. Try again later.")
        bucket.append(now)


def _auto_package_name(app_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", app_name.lower())[:22] or "websiteapp"
    return "com.apkie." + slug


def _write_icon(upload: UploadFile | None, build_dir: Path) -> Path | None:
    if upload is None or not upload.filename:
        return None
    if upload.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="App icon must be PNG, JPG or WEBP.")
    content = upload.file.read(MAX_ICON_BYTES + 1)
    if len(content) > MAX_ICON_BYTES:
        raise HTTPException(status_code=413, detail="App icon must be 2 MB or smaller.")
    if not content:
        return None
    icon_path = build_dir / "uploaded-icon"
    icon_path.write_bytes(content)
    try:
        with Image.open(icon_path) as image:
            if image.width > 4096 or image.height > 4096:
                raise ValueError("Image dimensions are too large.")
            image.verify()
    except Exception as exc:
        icon_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded icon is not a valid image.") from exc
    return icon_path


def _perform_build(build_id: str, config: BuildConfig, icon_path: Path | None) -> None:
    job_dir = DATA_DIR / "builds" / build_id
    project_dir = job_dir / "project"
    try:
        with BUILD_LOCK:
            database.update_build(build_id, status="running", progress=8, message="Preparing Android project.")
            if not SIGNING_SECRET:
                raise RuntimeError("SIGNING_SECRET is missing. Set a long private secret in the backend environment before building signed APK/AAB files.")

            def progress(percent: int, message: str, logs: str = "") -> None:
                current = database.get_build(build_id) or {}
                existing_logs = current.get("logs", "")
                combined = (existing_logs + ("\n" if existing_logs else "") + logs)[-12000:]
                database.update_build(
                    build_id,
                    status="running",
                    progress=percent,
                    message=message,
                    logs=combined,
                )

            progress(12, "Generating Android WebView app.")
            generate_android_project(
                config=config,
                output_dir=project_dir,
                icon_path=icon_path,
                signing_dir=DATA_DIR / "signing",
                signing_secret=SIGNING_SECRET,
            )
            progress(18, "Android project generated. Starting Gradle.")
            artifact = run_gradle_build(project_dir, config.build_type, progress)
            final_path = job_dir / ("app-release.apk" if config.build_type == "apk" else "app-release.aab")
            shutil.copy2(artifact, final_path)
            database.update_build(
                build_id,
                status="completed",
                progress=100,
                message="Your Android app is ready to download.",
                artifact_path=str(final_path),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
    except Exception as exc:
        message = str(exc).strip() or "Build failed for an unknown reason."
        database.update_build(
            build_id,
            status="failed",
            progress=100,
            message=message[:1800],
            logs=message[-12000:],
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


@app.post("/api/builds", status_code=202)
async def create_build(
    request: Request,
    background_tasks: BackgroundTasks,
    site_url: str = Form(...),
    app_name: str = Form(...),
    package_name: str = Form(""),
    version_name: str = Form("1.0.0"),
    version_code: int = Form(1),
    mode: str = Form("quick"),
    build_type: str = Form("apk"),
    orientation: str = Form("portrait"),
    splash_color: str = Form("#3157d5"),
    status_bar_color: str = Form("#2445b0"),
    navigation_bar_color: str = Form("#10182b"),
    javascript_enabled: bool = Form(False),
    dom_storage_enabled: bool = Form(False),
    file_upload_enabled: bool = Form(False),
    camera_enabled: bool = Form(False),
    microphone_enabled: bool = Form(False),
    fullscreen_enabled: bool = Form(False),
    keep_screen_on: bool = Form(False),
    allow_external_links: bool = Form(False),
    icon: UploadFile | None = File(None),
) -> dict[str, str]:
    _rate_limit(request)
    if not SIGNING_SECRET:
        raise HTTPException(status_code=503, detail="The build server is not configured yet. Set SIGNING_SECRET in backend environment.")
    try:
        config = BuildConfig(
            site_url=site_url,
            app_name=app_name,
            package_name=package_name or _auto_package_name(app_name),
            version_name=version_name,
            version_code=version_code,
            mode=mode,
            build_type=build_type,
            orientation=orientation,
            splash_color=splash_color,
            status_bar_color=status_bar_color,
            navigation_bar_color=navigation_bar_color,
            javascript_enabled=javascript_enabled,
            dom_storage_enabled=dom_storage_enabled,
            file_upload_enabled=file_upload_enabled,
            camera_enabled=camera_enabled,
            microphone_enabled=microphone_enabled,
            fullscreen_enabled=fullscreen_enabled,
            keep_screen_on=keep_screen_on,
            allow_external_links=allow_external_links,
        )
    except ValidationError as exc:
        messages = "; ".join(item["msg"] for item in exc.errors())
        raise HTTPException(status_code=422, detail=messages) from exc

    build_id = uuid.uuid4().hex
    job_dir = DATA_DIR / "builds" / build_id
    job_dir.mkdir(parents=True, exist_ok=True)
    icon_path = _write_icon(icon, job_dir)
    database.create_build(
        {
            "id": build_id,
            "app_name": config.app_name,
            "package_name": config.package_name,
            "mode": config.mode,
            "build_type": config.build_type,
        }
    )
    background_tasks.add_task(_perform_build, build_id, config, icon_path)
    return {"build_id": build_id, "status": "queued", "message": "Build request accepted."}


@app.get("/api/builds")
def get_builds(limit: int = 12) -> dict[str, object]:
    rows = database.list_builds(limit)
    builds = [
        {
            "id": row["id"],
            "app_name": row["app_name"],
            "package_name": row["package_name"],
            "mode": row["mode"],
            "build_type": row["build_type"],
            "status": row["status"],
            "progress": row["progress"],
            "message": row["message"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
        }
        for row in rows
    ]
    return {"builds": builds}


@app.get("/api/builds/{build_id}")
def get_build(build_id: str) -> dict[str, object]:
    row = database.get_build(build_id)
    if not row:
        raise HTTPException(status_code=404, detail="Build not found.")
    return {
        "build_id": row["id"],
        "app_name": row["app_name"],
        "package_name": row["package_name"],
        "mode": row["mode"],
        "build_type": row["build_type"],
        "status": row["status"],
        "progress": row["progress"],
        "message": row["message"],
        "logs": row["logs"][-12000:],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


@app.get("/api/builds/{build_id}/download")
def download_build(build_id: str) -> FileResponse:
    row = database.get_build(build_id)
    if not row:
        raise HTTPException(status_code=404, detail="Build not found.")
    if row["status"] != "completed" or not row["artifact_path"]:
        raise HTTPException(status_code=409, detail="Build is not ready for download.")
    artifact = Path(row["artifact_path"]).resolve()
    build_root = (DATA_DIR / "builds" / build_id).resolve()
    if build_root not in artifact.parents or not artifact.is_file():
        raise HTTPException(status_code=404, detail="Build artifact is missing.")
    media_type = "application/vnd.android.package-archive" if row["build_type"] == "apk" else "application/octet-stream"
    return FileResponse(
        artifact,
        media_type=media_type,
        filename=f"{re.sub(r'[^A-Za-z0-9_-]+', '_', row['app_name'])}.{row['build_type']}",
    )
