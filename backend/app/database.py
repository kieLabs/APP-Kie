from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("APK_KIE_DATA_DIR", "/data/apk-kie"))
DB_PATH = DATA_DIR / "apk-kie.sqlite3"
_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _LOCK, _connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS builds (
                id TEXT PRIMARY KEY,
                app_name TEXT NOT NULL,
                package_name TEXT NOT NULL,
                mode TEXT NOT NULL,
                build_type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                logs TEXT NOT NULL DEFAULT '',
                artifact_path TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )


def create_build(build: dict[str, Any]) -> None:
    with _LOCK, _connect() as db:
        db.execute(
            """INSERT INTO builds
               (id, app_name, package_name, mode, build_type, status, progress, message, logs, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                build["id"], build["app_name"], build["package_name"], build["mode"],
                build["build_type"], "queued", 0, "Build queued.", "", datetime.now(timezone.utc).isoformat(),
            ),
        )


def update_build(build_id: str, **fields: Any) -> None:
    allowed = {"status", "progress", "message", "logs", "artifact_path", "finished_at"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return
    columns = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [build_id]
    with _LOCK, _connect() as db:
        db.execute(f"UPDATE builds SET {columns} WHERE id = ?", values)


def get_build(build_id: str) -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
    return dict(row) if row else None


def list_builds(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute(
            "SELECT * FROM builds ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)
        ).fetchall()
    return [dict(row) for row in rows]
