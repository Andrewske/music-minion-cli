"""Import orchestration for SoundCloud tracks and playlists (streaming only).

Unlike YouTube which downloads files, SoundCloud tracks are stored as metadata
with permalink URLs for streaming via yt-dlp at playback time.
"""

import re
from dataclasses import dataclass
from typing import Optional

import yt_dlp
from loguru import logger

from music_minion.core import database
from music_minion.domain.library.models import Track

from .exceptions import (
    DuplicateTrackError,
    InvalidSoundCloudURLError,
    SoundCloudError,
    TrackUnavailableError,
)


@dataclass(frozen=True)
class SoundCloudImportResult:
    """Result of an import operation - returned instead of logging directly."""

    tracks: list[Track]
    imported_count: int
    skipped_count: int  # Duplicates
    failed_count: int
    failures: list[tuple[str, str]]  # (track_url, error_message)


def _extract_track_info(url: str) -> dict:
    """Extract track metadata from SoundCloud URL using yt-dlp.

    Args:
        url: SoundCloud track URL (permalink)

    Returns:
        Dict with track metadata: id, title, uploader, duration, webpage_url

    Raises:
        InvalidSoundCloudURLError: If URL is not a valid SoundCloud track
        TrackUnavailableError: If track cannot be accessed
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                raise TrackUnavailableError(f"Could not extract info from {url}")

            # Verify it's a SoundCloud track
            if info.get("extractor_key") != "Soundcloud":
                raise InvalidSoundCloudURLError(f"Not a SoundCloud URL: {url}")

            return {
                "id": str(info.get("id", "")),
                "title": info.get("title", ""),
                "uploader": info.get("uploader", ""),
                "duration": info.get("duration", 0),
                "webpage_url": info.get("webpage_url", url),
                "genre": info.get("genre"),
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "private" in error_msg or "not available" in error_msg:
            raise TrackUnavailableError(f"Track unavailable: {url}")
        raise SoundCloudError(f"Failed to extract track info: {e}")


def _extract_playlist_info(url: str) -> dict:
    """Extract playlist metadata and track list from SoundCloud URL using yt-dlp.

    Args:
        url: SoundCloud playlist/set URL

    Returns:
        Dict with playlist metadata and entries list

    Raises:
        InvalidSoundCloudURLError: If URL is not a valid SoundCloud playlist
        SoundCloudError: If playlist cannot be accessed
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",  # Get playlist entries without downloading each
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                raise SoundCloudError(f"Could not extract playlist info from {url}")

            # Verify it's a SoundCloud playlist
            if info.get("extractor_key") not in ("SoundcloudPlaylist", "SoundcloudSet"):
                # Could be a user's likes or tracks page
                if "soundcloud" not in info.get("extractor", "").lower():
                    raise InvalidSoundCloudURLError(f"Not a SoundCloud playlist: {url}")

            return {
                "id": str(info.get("id", "")),
                "title": info.get("title", "Unknown Playlist"),
                "uploader": info.get("uploader", ""),
                "entries": info.get("entries", []),
                "webpage_url": info.get("webpage_url", url),
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "private" in error_msg or "not available" in error_msg:
            raise SoundCloudError(f"Playlist unavailable or private: {url}")
        raise SoundCloudError(f"Failed to extract playlist info: {e}")


def validate_soundcloud_url(url: str) -> bool:
    """Check if URL looks like a SoundCloud track or playlist URL.

    Args:
        url: URL to validate

    Returns:
        True if URL appears to be a valid SoundCloud URL
    """
    # Basic URL pattern check - full validation happens during extraction
    pattern = r"^https?://(www\.)?soundcloud\.com/[\w-]+/[\w-]+"
    return bool(re.match(pattern, url))


def import_single_track(
    url: str,
    artist: Optional[str] = None,
    title: Optional[str] = None,
) -> Track:
    """Import a single SoundCloud track (metadata only, no download).

    Args:
        url: SoundCloud track permalink URL
        artist: Artist name (falls back to track uploader if not provided)
        title: Track title (falls back to track title if not provided)

    Returns:
        Track object for the imported track

    Raises:
        DuplicateTrackError: If track is already imported
        InvalidSoundCloudURLError: If URL is not a valid SoundCloud track
        TrackUnavailableError: If track cannot be accessed
    """
    if not validate_soundcloud_url(url):
        raise InvalidSoundCloudURLError(f"Invalid SoundCloud URL: {url}")

    # Extract track info using yt-dlp
    info = _extract_track_info(url)
    soundcloud_id = info["id"]

    # Check for duplicate before inserting
    existing_track = database.get_track_by_soundcloud_id(soundcloud_id)
    if existing_track:
        raise DuplicateTrackError(existing_track.id)

    # Use user-provided metadata or fall back to extracted metadata
    final_title = title or info["title"]
    final_artist = artist or info["uploader"]
    source_url = info["webpage_url"]  # Canonical permalink

    # Insert track into database (no local_path - streaming only)
    track_id = database.insert_soundcloud_track(
        soundcloud_id=soundcloud_id,
        source_url=source_url,
        title=final_title,
        artist=final_artist,
        duration=info["duration"],
        genre=info.get("genre"),
    )

    # Get the inserted track
    track = database.get_track_by_soundcloud_id(soundcloud_id)

    logger.info(
        f"Imported SoundCloud track: {final_artist} - {final_title} (ID: {track_id})"
    )

    return track


def import_playlist(playlist_url: str) -> SoundCloudImportResult:
    """Bulk import all tracks from a SoundCloud playlist (metadata only).

    Args:
        playlist_url: SoundCloud playlist/set URL

    Returns:
        SoundCloudImportResult with statistics and any failures

    Raises:
        SoundCloudError: If playlist cannot be accessed
    """
    # Extract playlist info
    playlist_info = _extract_playlist_info(playlist_url)
    playlist_title = playlist_info["title"]
    entries = playlist_info.get("entries", [])

    logger.info(
        f"Importing SoundCloud playlist: {playlist_title} ({len(entries)} tracks)"
    )

    if not entries:
        return SoundCloudImportResult(
            tracks=[],
            imported_count=0,
            skipped_count=0,
            failed_count=0,
            failures=[],
        )

    # Extract track IDs from entries (flat extraction gives us IDs)
    track_ids = []
    track_urls = {}  # id -> url mapping for later import

    for entry in entries:
        if entry and entry.get("id"):
            track_id = str(entry["id"])
            track_ids.append(track_id)
            track_urls[track_id] = entry.get("url", entry.get("webpage_url", ""))

    # Batch check duplicates BEFORE importing
    existing_ids = database.get_existing_soundcloud_ids(track_ids)
    new_track_ids = set(track_ids) - existing_ids

    logger.info(
        f"Found {len(existing_ids)} duplicates, will import {len(new_track_ids)} new tracks"
    )

    if not new_track_ids:
        # All tracks already imported
        return SoundCloudImportResult(
            tracks=[],
            imported_count=0,
            skipped_count=len(existing_ids),
            failed_count=0,
            failures=[],
        )

    # Import each new track individually (need full metadata extraction)
    tracks_data: list[dict] = []
    failures: list[tuple[str, str]] = []

    for track_id in new_track_ids:
        track_url = track_urls.get(track_id, "")
        if not track_url:
            failures.append((track_id, "No URL available for track"))
            continue

        try:
            # Extract full track info
            info = _extract_track_info(track_url)

            tracks_data.append(
                {
                    "soundcloud_id": info["id"],
                    "source_url": info["webpage_url"],
                    "title": info["title"],
                    "artist": info["uploader"],
                    "duration": info["duration"],
                    "genre": info.get("genre"),
                }
            )

        except (TrackUnavailableError, SoundCloudError) as e:
            logger.warning(f"Failed to import track {track_url}: {e}")
            failures.append((track_url, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error importing track {track_url}")
            failures.append((track_url, f"Unexpected error: {e}"))

    # Batch insert all successfully extracted tracks
    inserted_tracks: list[Track] = []

    if tracks_data:
        try:
            track_ids_inserted = database.batch_insert_soundcloud_tracks(tracks_data)
            logger.info(f"Batch inserted {len(track_ids_inserted)} SoundCloud tracks")

            # Get all inserted tracks in one query
            soundcloud_ids = [data["soundcloud_id"] for data in tracks_data]
            inserted_tracks = database.get_tracks_by_soundcloud_ids(soundcloud_ids)

        except Exception as e:
            logger.exception("Batch insert failed")
            # Add all tracks to failures
            for data in tracks_data:
                failures.append((data["source_url"], f"Database insert failed: {e}"))
            tracks_data = []

    return SoundCloudImportResult(
        tracks=inserted_tracks,
        imported_count=len(inserted_tracks),
        skipped_count=len(existing_ids),
        failed_count=len(failures),
        failures=failures,
    )


def get_playlist_preview(playlist_url: str) -> dict:
    """Get playlist info for preview before importing.

    Args:
        playlist_url: SoundCloud playlist/set URL

    Returns:
        Dict with title, track_count, and tracks list
    """
    playlist_info = _extract_playlist_info(playlist_url)

    tracks = []
    for entry in playlist_info.get("entries", []):
        if entry:
            tracks.append(
                {
                    "id": entry.get("id", ""),
                    "title": entry.get("title", "Unknown"),
                    "duration": entry.get("duration", 0),
                }
            )

    return {
        "title": playlist_info["title"],
        "track_count": len(tracks),
        "tracks": tracks,
    }
