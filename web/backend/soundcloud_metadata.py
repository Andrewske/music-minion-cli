"""Pure normalization helpers for SoundCloud feed ingestion."""

from datetime import datetime, timezone
from typing import Any, Optional


def parse_soundcloud_datetime(value: Any) -> Optional[datetime]:
    """Parse SoundCloud, SQLite, and ISO timestamps as aware UTC datetimes."""
    if not value or not isinstance(value, str):
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def upgraded_artwork_url(url: Optional[str]) -> Optional[str]:
    """Upgrade SoundCloud's default 100px artwork URL when one is available."""
    if not url:
        return None
    return url.replace("-large.", "-t500x500.")


def uploader_soundcloud_id(track: dict[str, Any]) -> Optional[str]:
    raw_id = (track.get("user") or {}).get("id")
    return str(raw_id) if raw_id is not None else None


def release_timestamp(track: dict[str, Any]) -> Optional[str]:
    """Return the explicit release/display date, never the upload timestamp."""
    return track.get("release_date") or track.get("display_date")


def track_metadata(track: dict[str, Any]) -> dict[str, Any]:
    """Normalize the metadata shared by upload and repost ingestion."""
    return {
        "soundcloud_id": str(track["id"]),
        "slug": track.get("permalink", ""),
        "title": track.get("title", ""),
        "artist_name": (track.get("user") or {}).get("username", "Unknown"),
        "duration_ms": track.get("duration", 0) or 0,
        "uploader_soundcloud_id": uploader_soundcloud_id(track),
        "genre": track.get("genre"),
        "artwork_url": upgraded_artwork_url(track.get("artwork_url")),
        "permalink_url": track.get("permalink_url"),
        "access": track.get("access"),
        "uploaded_at": track.get("created_at"),
        "released_at": release_timestamp(track),
        "metadata_updated_at": track.get("last_modified")
        or datetime.now(timezone.utc).isoformat(),
    }


def raw_repost_timestamp(track: dict[str, Any]) -> Optional[str]:
    """Return only an explicit repost timestamp from a repost payload.

    GET /users/:id/reposts/tracks normally returns bare tracks whose
    created_at is the upload time. Treating that field as repost time was the
    original data-integrity bug, so it is deliberately excluded here.
    """
    value = track.get("reposted_at") or track.get("repost_created_at")
    return value if isinstance(value, str) and value else None
