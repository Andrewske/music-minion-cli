"""Mobile app self-update: serve the latest APK built by scripts/build-apk.sh."""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from music_minion.core.config import get_data_dir

router = APIRouter(prefix="/api/app", tags=["app"])

APP_UPDATES_DIR_ENV = "MUSIC_MINION_APP_UPDATES_DIR"
MANIFEST_NAME = "latest.json"
APK_NAME = "music-minion.apk"
APK_MEDIA_TYPE = "application/vnd.android.package-archive"


def get_app_updates_dir() -> Path:
    """Directory holding latest.json + the APK; env override, else the data dir."""
    override = os.environ.get(APP_UPDATES_DIR_ENV)
    return Path(override) if override else get_data_dir() / "app-updates"


@router.get("/latest")
def get_latest_build() -> dict[str, Any]:
    """Manifest of the newest published build (versionCode, sha, changelog...)."""
    path = get_app_updates_dir() / MANIFEST_NAME
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"No app build published at {path}")
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        logger.exception(f"Unreadable app manifest at {path}")
        raise HTTPException(status_code=500, detail=f"Unreadable {path}: {e}") from e
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=500, detail=f"{path} is not a JSON object")
    return manifest


@router.get("/apk")
def get_latest_apk() -> FileResponse:
    """Stream the APK from disk (FileResponse reads in chunks, ~100 MB file)."""
    path = get_app_updates_dir() / APK_NAME
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"No APK published at {path}")
    return FileResponse(path, media_type=APK_MEDIA_TYPE, filename=APK_NAME)
