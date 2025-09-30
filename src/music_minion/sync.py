"""
Metadata sync operations for Music Minion CLI

Handles bidirectional sync between database and file metadata.
Supports reading/writing tags to MP3 (ID3) and M4A files.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, COMM, ID3NoHeaderError
from mutagen.mp4 import MP4

from .database import (
    get_db_connection,
    get_track_tags,
    add_tags,
    remove_tag,
    get_all_tracks,
    get_track_by_path
)
from .config import Config


def get_file_mtime(file_path: str) -> Optional[int]:
    """Get file modification time as Unix timestamp.

    Args:
        file_path: Path to the file

    Returns:
        Unix timestamp or None if file doesn't exist
    """
    try:
        return int(os.path.getmtime(file_path))
    except (OSError, FileNotFoundError):
        return None


def write_tags_to_file(file_path: str, tags: List[str], config: Config) -> bool:
    """Write tags to file metadata COMMENT field.

    Args:
        file_path: Path to the audio file
        tags: List of tag names to write
        config: Configuration object with sync settings

    Returns:
        True if successful, False otherwise
    """
    if not config.sync.write_tags_to_metadata:
        return False

    try:
        audio = MutagenFile(file_path, easy=False)
        if audio is None:
            return False

        # Format tags with prefix
        tag_prefix = config.sync.tag_prefix
        formatted_tags = [f"{tag_prefix}{tag}" for tag in tags]
        tag_string = ", ".join(formatted_tags)

        if isinstance(audio, MP4):
            # M4A file - use \xa9cmt for comment
            audio["\xa9cmt"] = tag_string
        else:
            # MP3 file - use ID3 COMM frame
            try:
                audio.add_tags()
            except Exception:
                pass  # Tags already exist

            # Remove existing COMM frames to avoid duplicates
            if hasattr(audio, 'tags') and audio.tags:
                audio.tags.delall("COMM")
                # Add new COMM frame
                audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=tag_string))

        audio.save()
        return True

    except Exception as e:
        print(f"Error writing tags to {file_path}: {e}")
        return False


def read_tags_from_file(file_path: str, config: Config) -> List[str]:
    """Read tags from file metadata COMMENT field.

    Args:
        file_path: Path to the audio file
        config: Configuration object with sync settings

    Returns:
        List of tag names found in file metadata
    """
    try:
        audio = MutagenFile(file_path, easy=False)
        if audio is None:
            return []

        tag_prefix = config.sync.tag_prefix
        comment_text = ""

        if isinstance(audio, MP4):
            # M4A file
            comment_text = audio.get("\xa9cmt", [""])[0]
        else:
            # MP3 file - read ID3 COMM frame
            if hasattr(audio, 'tags') and audio.tags:
                comm_frames = audio.tags.getall("COMM")
                if comm_frames:
                    comment_text = comm_frames[0].text[0] if comm_frames[0].text else ""

        # Parse tags from comment
        if not comment_text:
            return []

        # Split by comma and strip whitespace
        tags = []
        for tag in comment_text.split(","):
            tag = tag.strip()
            # Remove prefix if present
            if tag.startswith(tag_prefix):
                tag = tag[len(tag_prefix):]
            if tag:
                tags.append(tag)

        return tags

    except Exception as e:
        print(f"Error reading tags from {file_path}: {e}")
        return []


def detect_file_changes(config: Config) -> List[Dict[str, Any]]:
    """Detect files that have been modified since last sync.

    Compares file modification time (mtime) with last_synced_at timestamp
    in the database to find files that need to be re-synced.

    Args:
        config: Configuration object

    Returns:
        List of track records that have changed
    """
    changed_tracks = []

    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, file_path, file_mtime, last_synced_at
            FROM tracks
            WHERE file_path IS NOT NULL
        """)

        for row in cursor.fetchall():
            track = dict(row)
            file_path = track['file_path']

            # Check if file still exists
            if not os.path.exists(file_path):
                continue

            current_mtime = get_file_mtime(file_path)
            if current_mtime is None:
                continue

            # Check if file has been modified
            stored_mtime = track['file_mtime']

            # If no stored mtime, or if current mtime is newer, file has changed
            if stored_mtime is None or current_mtime > stored_mtime:
                track['current_mtime'] = current_mtime
                changed_tracks.append(track)

    return changed_tracks


def sync_export(config: Config, track_ids: Optional[List[int]] = None,
                show_progress: bool = True) -> Dict[str, int]:
    """Export database tags to file metadata.

    Writes all tags from database to file metadata COMMENT fields.

    Args:
        config: Configuration object
        track_ids: Optional list of specific track IDs to export (None = all)
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'skipped': count}
    """
    stats = {'success': 0, 'failed': 0, 'skipped': 0}

    if not config.sync.write_tags_to_metadata:
        if show_progress:
            print("Tag writing disabled in config (write_tags_to_metadata = false)")
        return stats

    with get_db_connection() as conn:
        # Get tracks to export
        if track_ids:
            placeholders = ','.join('?' * len(track_ids))
            cursor = conn.execute(f"""
                SELECT id, file_path FROM tracks
                WHERE id IN ({placeholders})
            """, track_ids)
        else:
            cursor = conn.execute("SELECT id, file_path FROM tracks")

        tracks = [dict(row) for row in cursor.fetchall()]

    if show_progress:
        print(f"Exporting tags to {len(tracks)} file(s)...")

    for track in tracks:
        track_id = track['id']
        file_path = track['file_path']

        # Check if file exists
        if not os.path.exists(file_path):
            stats['skipped'] += 1
            continue

        # Get tags from database
        db_tags = get_track_tags(track_id, include_blacklisted=False)
        tag_names = [tag['tag_name'] for tag in db_tags]

        # Write to file
        if write_tags_to_file(file_path, tag_names, config):
            # Update mtime and last_synced_at in database
            current_mtime = get_file_mtime(file_path)
            with get_db_connection() as conn:
                conn.execute("""
                    UPDATE tracks
                    SET file_mtime = ?, last_synced_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (current_mtime, track_id))
                conn.commit()

            stats['success'] += 1
            if show_progress and stats['success'] % 100 == 0:
                print(f"  Exported {stats['success']}/{len(tracks)}...")
        else:
            stats['failed'] += 1

    if show_progress:
        print(f"\nExport complete: {stats['success']} succeeded, "
              f"{stats['failed']} failed, {stats['skipped']} skipped")

    return stats


def sync_import(config: Config, force_all: bool = False,
                show_progress: bool = True) -> Dict[str, int]:
    """Import tags from file metadata to database.

    Reads tags from file metadata and updates database. Only processes
    files that have been modified since last sync (unless force_all=True).

    Args:
        config: Configuration object
        force_all: If True, import from all files regardless of mtime
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'added': count, 'removed': count}
    """
    stats = {'success': 0, 'failed': 0, 'added': 0, 'removed': 0}

    # Detect changed files
    if force_all:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM tracks WHERE file_path IS NOT NULL")
            changed_tracks = [dict(row) for row in cursor.fetchall()]
    else:
        changed_tracks = detect_file_changes(config)

    if show_progress:
        if force_all:
            print(f"Importing tags from all {len(changed_tracks)} file(s)...")
        else:
            print(f"Importing tags from {len(changed_tracks)} changed file(s)...")

    for track in changed_tracks:
        track_id = track['id']
        file_path = track['file_path']

        # Check if file exists
        if not os.path.exists(file_path):
            stats['failed'] += 1
            continue

        try:
            # Read tags from file
            file_tags = read_tags_from_file(file_path, config)
            file_tag_set = set(file_tags)

            # Get current database tags
            db_tags = get_track_tags(track_id, include_blacklisted=False)
            db_tag_set = set(tag['tag_name'] for tag in db_tags)

            # Find tags to add and remove
            tags_to_add = file_tag_set - db_tag_set
            tags_to_remove = db_tag_set - file_tag_set

            # Add new tags from file
            if tags_to_add:
                add_tags(track_id, list(tags_to_add), source='file')
                stats['added'] += len(tags_to_add)

            # Remove tags not in file
            for tag in tags_to_remove:
                remove_tag(track_id, tag)
                stats['removed'] += 1

            # Update mtime and last_synced_at
            current_mtime = get_file_mtime(file_path)
            with get_db_connection() as conn:
                conn.execute("""
                    UPDATE tracks
                    SET file_mtime = ?, last_synced_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (current_mtime, track_id))
                conn.commit()

            stats['success'] += 1
            if show_progress and stats['success'] % 100 == 0:
                print(f"  Imported {stats['success']}/{len(changed_tracks)}...")

        except Exception as e:
            if show_progress:
                print(f"  Error importing {file_path}: {e}")
            stats['failed'] += 1

    if show_progress:
        print(f"\nImport complete: {stats['success']} files processed, "
              f"{stats['added']} tags added, {stats['removed']} tags removed, "
              f"{stats['failed']} failed")

    return stats


def get_sync_status(config: Config) -> Dict[str, Any]:
    """Get sync status information.

    Shows how many files need syncing, last sync time, etc.

    Args:
        config: Configuration object

    Returns:
        Dictionary with sync status information
    """
    changed_files = detect_file_changes(config)

    with get_db_connection() as conn:
        # Count total tracks
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks WHERE file_path IS NOT NULL")
        total_tracks = cursor.fetchone()['count']

        # Get last sync time
        cursor = conn.execute("""
            SELECT MAX(last_synced_at) as last_sync
            FROM tracks
            WHERE last_synced_at IS NOT NULL
        """)
        last_sync_row = cursor.fetchone()
        last_sync = last_sync_row['last_sync'] if last_sync_row else None

        # Count tracks never synced
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM tracks
            WHERE file_path IS NOT NULL AND last_synced_at IS NULL
        """)
        never_synced = cursor.fetchone()['count']

    return {
        'total_tracks': total_tracks,
        'changed_files': len(changed_files),
        'never_synced': never_synced,
        'last_sync': last_sync,
        'sync_enabled': config.sync.write_tags_to_metadata
    }


def rescan_library(config: Config, full_rescan: bool = False,
                   show_progress: bool = True) -> Dict[str, int]:
    """Rescan library for file changes and update metadata.

    Args:
        config: Configuration object
        full_rescan: If True, rescan all files. If False, only changed files.
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats from sync_import
    """
    if show_progress:
        if full_rescan:
            print("Performing full library rescan...")
        else:
            print("Performing incremental library rescan...")

    # Import from changed (or all) files
    return sync_import(config, force_all=full_rescan, show_progress=show_progress)