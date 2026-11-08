from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class BuildConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    site_url: str
    app_name: str = Field(min_length=1, max_length=30)
    package_name: str = ""
    version_name: str = Field(default="1.0.0", min_length=1, max_length=20)
    version_code: int = Field(default=1, ge=1, le=2_100_000_000)
    mode: Literal["quick", "advanced", "pro"] = "quick"
    build_type: Literal["apk", "aab"] = "apk"
    orientation: Literal["portrait", "landscape", "unspecified"] = "portrait"
    splash_color: str = "#3157d5"
    status_bar_color: str = "#2445b0"
    navigation_bar_color: str = "#10182b"
    javascript_enabled: bool = True
    dom_storage_enabled: bool = True
    file_upload_enabled: bool = True
    camera_enabled: bool = False
    microphone_enabled: bool = False
    fullscreen_enabled: bool = False
    keep_screen_on: bool = False
    allow_external_links: bool = True

    @field_validator("site_url")
    @classmethod
    def validate_site_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("Website URL must be a valid HTTPS URL.")
        if parsed.username or parsed.password:
            raise ValueError("Website URLs must not contain embedded credentials.")
        return value.rstrip("/")

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("App name is required.")
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("App name contains invalid control characters.")
        return value.strip()

    @field_validator("package_name")
    @classmethod
    def validate_package_name(cls, value: str) -> str:
        if value and not PACKAGE_RE.fullmatch(value):
            raise ValueError(
                "Package name must use lowercase Android segments, such as com.example.myapp."
            )
        return value

    @field_validator("version_name")
    @classmethod
    def validate_version_name(cls, value: str) -> str:
        if not value.strip() or not re.fullmatch(r"[A-Za-z0-9._+-]+", value):
            raise ValueError("Version name may contain letters, numbers, dots, plus and hyphens.")
        return value

    @field_validator("splash_color", "status_bar_color", "navigation_bar_color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not COLOR_RE.fullmatch(value):
            raise ValueError("Colors must use #RRGGBB format.")
        return value.lower()
