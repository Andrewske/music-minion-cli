"""
Provider metadata sync for multi-source tracks.

Writes and reads provider IDs (SoundCloud, Spotify, YouTube) to/from
MP3 (ID3v2) and M4A (MP4) file metadata tags.

This enables portability - provider IDs travel with the files across systems.
"""

import os
import shutil
from typing import Dict, List, Optional

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TXXX
from mutagen.mp4 import MP4

# Custom tag names for provider IDs
TAG_SOUNDCLOUD_ID = "SOUNDCLOUD_ID"
TAG_SPOTIFY_ID = "SPOTIFY_ID"
TAG_YOUTUBE_ID = "YOUTUBE_ID"


def read_provider_ids_from_file(local_path: str) -> Dict[str, Optional[str]]:
    """Read all provider IDs from file metadata.

    Args:
        local_path: Path to audio file (MP3 or M4A)

    Returns:
        Dictionary with provider IDs:
        {
            'soundcloud_id': 'track_id' or None,
            'spotify_id': 'track_id' or None,
            'youtube_id': 'video_id' or None
        }

    Examples:
        >>> ids = read_provider_ids_from_file('/path/to/song.mp3')
        >>> print(ids['soundcloud_id'])
        '123456789'
    """
    result = {"soundcloud_id": None, "spotify_id": None, "youtube_id": None}

    try:
        audio = MutagenFile(local_path)
        if audio is None:
            return result

        if isinstance(audio, ID3):
            # MP3 file with ID3v2 tags
            result["soundcloud_id"] = _read_id3_custom_tag(audio, TAG_SOUNDCLOUD_ID)
            result["spotify_id"] = _read_id3_custom_tag(audio, TAG_SPOTIFY_ID)
            result["youtube_id"] = _read_id3_custom_tag(audio, TAG_YOUTUBE_ID)

        elif isinstance(audio, MP4):
            # M4A file with MP4/iTunes tags
            result["soundcloud_id"] = _read_mp4_custom_tag(audio, TAG_SOUNDCLOUD_ID)
            result["spotify_id"] = _read_mp4_custom_tag(audio, TAG_SPOTIFY_ID)
            result["youtube_id"] = _read_mp4_custom_tag(audio, TAG_YOUTUBE_ID)

    except Exception:
        # File doesn't exist, corrupted, or unsupported format
        pass

    return result


def write_provider_ids_to_file(
    local_path: str, provider_ids: Dict[str, Optional[str]]
) -> bool:
    """Write provider IDs to file metadata.

    Uses atomic file operations to prevent corruption.

    Args:
        local_path: Path to audio file (MP3 or M4A)
        provider_ids: Dictionary with provider IDs to write:
            {
                'soundcloud_id': 'track_id' or None,
                'spotify_id': 'track_id' or None,
                'youtube_id': 'video_id' or None
            }

    Returns:
        True if successful, False otherwise

    Examples:
        >>> success = write_provider_ids_to_file(
        ...     '/path/to/song.mp3',
        ...     {'soundcloud_id': '123456789', 'spotify_id': None}
        ... )
    """
    if not os.path.exists(local_path):
        return False

    # Use atomic write: copy to temp, modify, replace
    temp_path = local_path + ".tmp"

    try:
        # Copy original to temp
        shutil.copy2(local_path, temp_path)

        # Load temp file
        audio = MutagenFile(temp_path)
        if audio is None:
            os.remove(temp_path)
            return False

        # Write provider IDs based on format
        if isinstance(audio, ID3):
            # MP3 file with ID3v2 tags
            _write_id3_custom_tag(
                audio, TAG_SOUNDCLOUD_ID, provider_ids.get("soundcloud_id")
            )
            _write_id3_custom_tag(audio, TAG_SPOTIFY_ID, provider_ids.get("spotify_id"))
            _write_id3_custom_tag(audio, TAG_YOUTUBE_ID, provider_ids.get("youtube_id"))

        elif isinstance(audio, MP4):
            # M4A file with MP4/iTunes tags
            _write_mp4_custom_tag(
                audio, TAG_SOUNDCLOUD_ID, provider_ids.get("soundcloud_id")
            )
            _write_mp4_custom_tag(audio, TAG_SPOTIFY_ID, provider_ids.get("spotify_id"))
            _write_mp4_custom_tag(audio, TAG_YOUTUBE_ID, provider_ids.get("youtube_id"))

        else:
            # Unsupported format
            os.remove(temp_path)
            return False

        # Save changes to temp file
        audio.save()

        # Atomic replace: temp → original
        os.replace(temp_path, local_path)

        return True

    except Exception:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


def sync_provider_ids_to_file(track_id: int, local_path: str) -> bool:
    """Sync provider IDs from database to file metadata.

    Reads track's provider IDs from database and writes them to the file.

    Args:
        track_id: Database track ID
        local_path: Path to audio file

    Returns:
        True if successful
    """
    from ...core import database

    # Get track from database
    track_data = database.get_track_by_id(track_id)
    if not track_data:
        return False

    # Extract provider IDs
    provider_ids = {
        "soundcloud_id": track_data.get("soundcloud_id"),
        "spotify_id": track_data.get("spotify_id"),
        "youtube_id": track_data.get("youtube_id"),
    }

    # Write to file
    return write_provider_ids_to_file(local_path, provider_ids)


def sync_provider_ids_from_file(local_path: str) -> Optional[int]:
    """Sync provider IDs from file metadata to database.

    Reads provider IDs from file and updates the database track record.

    Args:
        local_path: Path to audio file

    Returns:
        Track ID if successful, None otherwise
    """
    from ...core import database

    # Read provider IDs from file
    provider_ids = read_provider_ids_from_file(local_path)

    # Get track by file path
    track_data = database.get_track_by_path(local_path)
    if not track_data:
        return None

    track_id = track_data["id"]

    # Update database with provider IDs
    with database.get_db_connection() as conn:
        updates = []
        values = []

        if provider_ids["soundcloud_id"]:
            updates.append("soundcloud_id = ?")
            values.append(provider_ids["soundcloud_id"])

        if provider_ids["spotify_id"]:
            updates.append("spotify_id = ?")
            values.append(provider_ids["spotify_id"])

        if provider_ids["youtube_id"]:
            updates.append("youtube_id = ?")
            values.append(provider_ids["youtube_id"])

        if updates:
            values.append(track_id)
            update_clause = ", ".join(updates)

            conn.execute(
                f"""
                UPDATE tracks
                SET {update_clause}
                WHERE id = ?
            """,
                values,
            )
            conn.commit()

    return track_id


def batch_sync_to_files(track_ids: List[int], progress_callback=None) -> Dict[str, int]:
    """Batch sync provider IDs from database to files.

    Args:
        track_ids: List of track IDs to sync
        progress_callback: Optional callback function(current, total)

    Returns:
        Statistics: {'success': N, 'failed': N, 'skipped': N}
    """
    from ...core import database

    stats = {"success": 0, "failed": 0, "skipped": 0}
    total = len(track_ids)

    for i, track_id in enumerate(track_ids):
        if progress_callback:
            progress_callback(i + 1, total)

        # Get track data
        track_data = database.get_track_by_id(track_id)
        if not track_data:
            stats["skipped"] += 1
            continue

        local_path = track_data.get("local_path")
        if not local_path or not os.path.exists(local_path):
            stats["skipped"] += 1
            continue

        # Sync provider IDs to file
        success = sync_provider_ids_to_file(track_id, local_path)

        if success:
            stats["success"] += 1
        else:
            stats["failed"] += 1

    return stats


def batch_sync_from_files(
    local_paths: List[str], progress_callback=None
) -> Dict[str, int]:
    """Batch sync provider IDs from files to database.

    Args:
        local_paths: List of file paths to sync
        progress_callback: Optional callback function(current, total)

    Returns:
        Statistics: {'success': N, 'failed': N, 'skipped': N}
    """
    stats = {"success": 0, "failed": 0, "skipped": 0}
    total = len(local_paths)

    for i, local_path in enumerate(local_paths):
        if progress_callback:
            progress_callback(i + 1, total)

        # Sync provider IDs from file
        track_id = sync_provider_ids_from_file(local_path)

        if track_id:
            stats["success"] += 1
        else:
            stats["failed"] += 1

    return stats


# ============================================================================
# Private helper functions for tag reading/writing
# ============================================================================


def _read_id3_custom_tag(audio: ID3, tag_name: str) -> Optional[str]:
    """Read custom TXXX tag from ID3."""
    frame_id = f"TXXX:{tag_name}"
    if frame_id in audio:
        return audio[frame_id].text[0]
    return None


def _write_id3_custom_tag(audio: ID3, tag_name: str, value: Optional[str]) -> None:
    """Write or remove custom TXXX tag in ID3."""
    frame_id = f"TXXX:{tag_name}"

    if value:
        # Write/update tag
        audio[frame_id] = TXXX(
            encoding=3,  # UTF-8
            desc=tag_name,
            text=[value],
        )
    else:
        # Remove tag if exists
        if frame_id in audio:
            del audio[frame_id]


def _read_mp4_custom_tag(audio: MP4, tag_name: str) -> Optional[str]:
    """Read custom freeform tag from MP4/iTunes."""
    tag_id = f"----:com.apple.iTunes:{tag_name}"
    if tag_id in audio:
        return audio[tag_id][0].decode("utf-8")
    return None


def _write_mp4_custom_tag(audio: MP4, tag_name: str, value: Optional[str]) -> None:
    """Write or remove custom freeform tag in MP4/iTunes."""
    tag_id = f"----:com.apple.iTunes:{tag_name}"

    if value:
        # Write/update tag
        audio[tag_id] = value.encode("utf-8")
    else:
        # Remove tag if exists
        if tag_id in audio:
            del audio[tag_id]
