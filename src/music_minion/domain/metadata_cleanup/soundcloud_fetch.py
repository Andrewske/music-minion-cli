"""Resolve SoundCloud permalinks to the raw upload metadata, with a disk cache."""

import json
import time
from pathlib import Path
from typing import Any, Optional

import requests
from loguru import logger

from music_minion.domain.library.providers.soundcloud import auth as sc_auth

RESOLVE_URL = "https://api.soundcloud.com/resolve"
_TRACK_FIELDS = (
    "title",
    "metadata_artist",
    "description",
    "genre",
    "tag_list",
    "label_name",
    "release",
    "isrc",
    "release_year",
    "created_at",
)


def get_access_token() -> str:
    """Load the stored user token, refreshing it if needed."""
    tokens = sc_auth._load_user_tokens()
    fresh = sc_auth.ensure_fresh_tokens(tokens) if tokens else None
    if not fresh:
        raise RuntimeError(
            "SoundCloud token missing or refresh failed "
            "(soundcloud_fetch.get_access_token). Run: library auth soundcloud"
        )
    return fresh["access_token"]


def trim_track(track: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields useful for title/artist cleanup."""
    user = track.get("user") or {}
    trimmed = {field: track.get(field) for field in _TRACK_FIELDS}
    trimmed["uploader"] = user.get("username")
    trimmed["uploader_full_name"] = user.get("full_name") or None
    return {key: value for key, value in trimmed.items() if value not in (None, "")}


def resolve_permalink(url: str, token: str) -> Optional[dict[str, Any]]:
    """Fetch one track; None if it is gone or not a track."""
    response = requests.get(
        RESOLVE_URL,
        params={"url": url},
        headers={"Authorization": f"OAuth {token}"},
        timeout=30,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return trim_track(data) if data.get("kind") == "track" else None


def _load_cache(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def fetch_all(urls: list[str], cache_path: Path) -> dict[str, Optional[dict]]:
    """Resolve every url, reusing cached results. Misses are cached as None."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = _load_cache(cache_path)
    missing = [url for url in urls if url not in cache]
    token = get_access_token() if missing else ""
    for index, url in enumerate(missing, 1):
        try:
            cache[url] = resolve_permalink(url, token)
        except requests.RequestException:
            logger.exception(f"SoundCloud resolve failed for {url}")
            continue
        if index % 25 == 0:
            logger.info(f"Resolved {index}/{len(missing)} SoundCloud tracks")
            cache_path.write_text(json.dumps(cache, ensure_ascii=False))
        time.sleep(0.2)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False))
    return {url: cache.get(url) for url in urls}
