"""Import orchestration for YouTube videos and playlists."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

from music_minion.core import database
from music_minion.domain.library.models import Track

from .download import (
    check_available_space,
    download_playlist_videos,
    download_video,
    extract_video_id,
    get_playlist_info,
    sanitize_filename,
)
from .exceptions import DuplicateVideoError


@dataclass(frozen=True)
class ImportResult:
    """Result of an import operation - returned instead of logging directly."""

    tracks: list[Track]
    imported_count: int
    skipped_count: int
    failed_count: int
    failures: list[tuple[str, str]]  # (video_id, error_message)


def _get_output_dir() -> Path:
    """Get YouTube download directory."""
    output_dir = Path.home() / "music" / "youtube"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _get_temp_dir() -> Path:
    """Get temp directory for atomic file operations."""
    temp_dir = _get_output_dir() / ".tmp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def import_single_video(
    url: str,
    artist: Optional[str] = None,
    title: Optional[str] = None,
    album: Optional[str] = None,
) -> Track:
    """Import a single YouTube video with optional user-controlled metadata.

    Args:
        url: YouTube video URL
        artist: Artist name (falls back to video uploader if not provided)
        title: Track title (falls back to video title if not provided)
        album: Album name (optional)

    Returns:
        Track object for the imported video

    Raises:
        DuplicateVideoError: If video is already imported
        YouTubeError: For various download/import failures
    """
    # Extract youtube_id from URL
    youtube_id = extract_video_id(url)

    # Check for duplicate before downloading (saves bandwidth)
    existing_track = database.get_track_by_youtube_id(youtube_id)
    if existing_track:
        raise DuplicateVideoError(existing_track.id)

    # Download to temp directory first
    output_dir = _get_output_dir()
    temp_dir = _get_temp_dir()

    temp_path = None
    try:
        # Download video to temp location
        temp_path, metadata = download_video(url, temp_dir)

        # Fall back to YouTube metadata if user didn't provide
        final_title = title or metadata["title"]
        final_artist = artist or metadata["uploader"]
        final_album = album or ""

        # Determine final file path
        sanitized_name = sanitize_filename(final_title, temp_path.suffix)
        final_path = output_dir / sanitized_name

        # Handle collision by appending youtube_id
        if final_path.exists():
            name_parts = sanitized_name.rsplit(".", 1)
            sanitized_name = f"{name_parts[0]}_{youtube_id}.{name_parts[1]}"
            final_path = output_dir / sanitized_name

        # Insert track into database with final path
        track_id = database.insert_youtube_track(
            local_path=str(final_path),
            youtube_id=youtube_id,
            title=final_title,
            artist=final_artist,
            album=final_album,
            duration=metadata["duration"],
        )

        # Move file to final location atomically
        os.replace(temp_path, final_path)

        # Get the inserted track
        track = database.get_track_by_youtube_id(youtube_id)

        logger.info(f"Imported YouTube video: {final_artist} - {final_title} (ID: {track_id})")

        return track

    except Exception:
        # Clean up temp file on any failure
        if temp_path and temp_path.exists():
            logger.debug(f"Cleaning up temp file: {temp_path}")
            temp_path.unlink()
        raise


def import_playlist(playlist_id: str) -> ImportResult:
    """Bulk import all videos from a YouTube playlist with pre-download duplicate filtering.

    Args:
        playlist_id: YouTube playlist ID

    Returns:
        ImportResult with statistics and any failures

    Raises:
        YouTubeError: If playlist cannot be accessed
    """
    output_dir = _get_output_dir()
    temp_dir = _get_temp_dir()

    # Get playlist info
    playlist_info = get_playlist_info(playlist_id)
    playlist_title = playlist_info["title"]

    logger.info(
        f"Importing playlist: {playlist_title} ({playlist_info['video_count']} videos)"
    )

    # Extract all video IDs
    video_ids = [v["id"] for v in playlist_info["videos"]]

    # Batch check duplicates BEFORE downloading
    existing_ids = database.get_existing_youtube_ids(video_ids)
    new_video_ids = set(video_ids) - existing_ids

    logger.info(
        f"Found {len(existing_ids)} duplicates, will download {len(new_video_ids)} new videos"
    )

    if not new_video_ids:
        # All videos already imported
        return ImportResult(
            tracks=[],
            imported_count=0,
            skipped_count=len(existing_ids),
            failed_count=0,
            failures=[],
        )

    # Check disk space
    check_available_space(output_dir, len(new_video_ids))

    # Download only new videos
    successes, failures = download_playlist_videos(
        playlist_id=playlist_id, output_dir=temp_dir, skip_ids=existing_ids
    )

    # Prepare track data for batch insert
    tracks_data = []
    temp_to_final = {}  # Map temp paths to final paths

    for temp_path, metadata in successes:
        # Use playlist title as album name
        title = metadata["title"]
        artist = metadata.get("uploader", "")

        # Determine final file path
        sanitized_name = sanitize_filename(title, temp_path.suffix)
        final_path = output_dir / sanitized_name

        # Handle collision by appending a counter
        counter = 1
        while final_path.exists() or str(final_path) in [d["local_path"] for d in tracks_data]:
            name_parts = sanitized_name.rsplit(".", 1)
            sanitized_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
            final_path = output_dir / sanitized_name
            counter += 1

        # Get youtube_id from metadata
        youtube_id = metadata["id"]

        tracks_data.append(
            {
                "local_path": str(final_path),
                "youtube_id": youtube_id,
                "title": title,
                "artist": artist,
                "album": playlist_title,
                "duration": metadata["duration"],
            }
        )

        temp_to_final[temp_path] = final_path

    # Batch insert all tracks
    if tracks_data:
        try:
            track_ids = database.batch_insert_youtube_tracks(tracks_data)

            # Move all files atomically after successful DB insert
            for temp_path, final_path in temp_to_final.items():
                os.replace(temp_path, final_path)

            logger.info(f"Batch inserted {len(track_ids)} tracks")

            # Get all inserted tracks
            inserted_tracks = [
                database.get_track_by_youtube_id(data["youtube_id"]) for data in tracks_data
            ]

        except Exception as e:
            # Clean up temp files on batch insert failure
            logger.exception("Batch insert failed, cleaning up temp files")
            for temp_path in temp_to_final.keys():
                if temp_path.exists():
                    temp_path.unlink()
            raise
    else:
        inserted_tracks = []

    return ImportResult(
        tracks=inserted_tracks,
        imported_count=len(inserted_tracks),
        skipped_count=len(existing_ids),
        failed_count=len(failures),
        failures=[(vid, str(exc)) for vid, exc in failures],
    )


def cleanup_temp_directory() -> None:
    """Clean up orphaned temp files from previous failed imports."""
    temp_dir = _get_temp_dir()

    if temp_dir.exists():
        for f in temp_dir.iterdir():
            logger.debug(f"Cleaning up orphaned temp file: {f}")
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file {f}: {e}")
