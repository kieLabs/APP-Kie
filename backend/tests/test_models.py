import pytest
from pydantic import ValidationError

from app.models import BuildConfig


def make_config(**overrides):
    data = {
        "site_url": "https://example.com",
        "app_name": "Example App",
        "package_name": "com.example.app",
    }
    data.update(overrides)
    return BuildConfig(**data)


def test_accepts_valid_https_website_and_package():
    config = make_config()
    assert config.site_url == "https://example.com"
    assert config.package_name == "com.example.app"


def test_rejects_http_website():
    with pytest.raises(ValidationError):
        make_config(site_url="http://example.com")


def test_rejects_package_name_with_uppercase_or_invalid_segment():
    with pytest.raises(ValidationError):
        make_config(package_name="com.Example.bad-name")


def test_rejects_invalid_color():
    with pytest.raises(ValidationError):
        make_config(splash_color="blue")


def test_rejects_invalid_version_name():
    with pytest.raises(ValidationError):
        make_config(version_name="1.0 bad")


def test_aab_mode_is_accepted():
    assert make_config(mode="pro", build_type="aab").build_type == "aab"
