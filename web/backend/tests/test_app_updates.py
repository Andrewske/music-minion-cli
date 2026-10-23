"""Tests for the mobile app update endpoints (/api/app/latest, /api/app/apk)."""

import json

import pytest
from fastapi.testclient import TestClient

from web.backend.main import app
from web.backend.routers.app_updates import APP_UPDATES_DIR_ENV, get_app_updates_dir

client = TestClient(app)

MANIFEST = {
    "versionCode": 812,
    "versionName": "1.812+abc1234",
    "sha": "abc1234",
    "built_at": "2026-10-23T12:00:00Z",
    "apk_size": 4,
    "apk_sha256": "deadbeef",
    "changelog": ["feat(mobile): one-tap updates"],
}


@pytest.fixture
def updates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(APP_UPDATES_DIR_ENV, str(tmp_path))
    return tmp_path


def test_dir_defaults_to_data_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(APP_UPDATES_DIR_ENV, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert get_app_updates_dir() == tmp_path / "music-minion" / "app-updates"


def test_latest_returns_manifest(updates_dir):
    (updates_dir / "latest.json").write_text(json.dumps(MANIFEST))
    response = client.get("/api/app/latest")
    assert response.status_code == 200
    assert response.json() == MANIFEST


def test_latest_404_when_missing(updates_dir):
    response = client.get("/api/app/latest")
    assert response.status_code == 404


def test_latest_500_when_corrupt(updates_dir):
    (updates_dir / "latest.json").write_text("{not json")
    response = client.get("/api/app/latest")
    assert response.status_code == 500


def test_apk_streams_file(updates_dir):
    (updates_dir / "music-minion.apk").write_bytes(b"PK\x03\x04")
    response = client.get("/api/app/apk")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert response.content == b"PK\x03\x04"


def test_apk_404_when_missing(updates_dir):
    response = client.get("/api/app/apk")
    assert response.status_code == 404
