"""
Metadata sync operations for Music Minion CLI

Handles bidirectional sync between database and file metadata.
Supports reading/writing tags to MP3 (ID3) and M4A files.
"""

import os
import shutil
from typing import Any, Optional

from mutagen import File as MutagenFile
from mutagen.id3 import COMM, ID3
from mutagen.mp4 import MP4

from music_minion.core.config import Config
from music_minion.core.database import (
    add_tags,
    get_db_connection,
    get_track_tags,
    get_track_tags_batch,
    remove_tag,
)
from music_minion.domain.library.metadata import write_elo_to_file


def get_file_mtime(local_path: str) -> Optional[float]:
    """Get file modification time as Unix timestamp with sub-second precision.

    Args:
        local_path: Path to the file

    Returns:
        Unix timestamp (float) or None if file doesn't exist
    """
    try:
        return os.path.getmtime(local_path)
    except (OSError, FileNotFoundError):
        return None


def write_tags_to_file(local_path: str, tags: list[str], config: Config) -> bool:
    """Write tags to file metadata COMMENT field using atomic writes.

    Args:
        local_path: Path to the audio file
        tags: List of tag names to write
        config: Configuration object with sync settings

    Returns:
        True if successful, False otherwise
    """
    if not config.sync.write_tags_to_metadata:
        return False

    try:
        # Validate file format first (only MP3 and M4A supported)
        audio = MutagenFile(local_path, easy=False)
        if audio is None:
            print(f"Error: Could not open file {local_path}")
            return False

        if not isinstance(audio, (MP4, ID3)) and not hasattr(audio, "tags"):
            print(f"Unsupported format for {local_path} (only MP3/M4A supported)")
            return False

        # Atomic write: copy to temp, modify temp, then replace original
        temp_path = local_path + ".tmp"
        try:
            # Step 1: Copy original to temp
            shutil.copy2(local_path, temp_path)

            # Step 2: Load temp file for modification
            audio = MutagenFile(temp_path, easy=False)
            if audio is None:
                raise Exception("Could not open temp file")

            # Step 3: Modify tags in temp file
            # Format tags with prefix
            tag_prefix = config.sync.tag_prefix
            formatted_tags = [f"{tag_prefix}{tag}" for tag in tags]
            tag_string = ", ".join(formatted_tags)

            if isinstance(audio, MP4):
                # M4A file - use \xa9cmt for comment
                audio["\xa9cmt"] = tag_string
            else:
                # MP3 file - use ID3 COMM frame
                # Check if tags exist, add them if not
                if not hasattr(audio, "tags") or audio.tags is None:
                    try:
                        audio.add_tags()
                    except Exception as e:
                        raise Exception(f"Error adding ID3 tags: {e}")

                # Remove existing COMM frames to avoid duplicates
                if audio.tags:
                    audio.tags.delall("COMM")
                    # Add new COMM frame
                    audio.tags.add(
                        COMM(encoding=3, lang="eng", desc="", text=tag_string)
                    )

            # Step 4: Save temp file in place (no filename = saves to same file)
            audio.save()

            # Step 5: Atomically replace original with temp
            os.replace(temp_path, local_path)
            return True

        except Exception as e:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise e

    except PermissionError as e:
        print(f"Permission denied writing to {local_path}: {e}")
        return False
    except Exception as e:
        print(f"Error writing tags to {local_path}: {e}")
        return False


def read_tags_from_file(local_path: str, config: Config) -> list[str]:
    """Read tags from file metadata COMMENT field with deduplication.

    Args:
        local_path: Path to the audio file
        config: Configuration object with sync settings

    Returns:
        List of unique tag names found in file metadata
    """
    try:
        audio = MutagenFile(local_path, easy=False)
        if audio is None:
            return []

        # Validate file format
        if not isinstance(audio, (MP4, ID3)) and not hasattr(audio, "tags"):
            return []

        tag_prefix = config.sync.tag_prefix
        comment_text = ""

        if isinstance(audio, MP4):
            # M4A file
            comment_text = audio.get("\xa9cmt", [""])[0]
        elif hasattr(audio, "tags") and audio.tags:
            # Check for VorbisComment (Opus, Ogg Vorbis, FLAC)
            if hasattr(audio.tags, "get"):
                # VorbisComment uses dictionary-like access
                comment_text = audio.tags.get("COMMENT", [""])[0] if "COMMENT" in audio.tags else ""
            elif hasattr(audio.tags, "getall"):
                # ID3 tags (MP3) - read COMM frame
                comm_frames = audio.tags.getall("COMM")
                if comm_frames:
                    comment_text = comm_frames[0].text[0] if comm_frames[0].text else ""

        # Parse tags from comment
        if not comment_text:
            return []

        # Split by comma, strip whitespace, and deduplicate
        tags_set = set()
        for tag in comment_text.split(","):
            tag = tag.strip()
            # Remove prefix if present
            if tag.startswith(tag_prefix):
                tag = tag[len(tag_prefix) :]
            if tag:
                tags_set.add(tag.lower())  # Normalize to lowercase

        return list(tags_set)

    except Exception as e:
        print(f"Error reading tags from {local_path}: {e}")
        return []


def detect_file_changes(config: Config) -> list[dict[str, Any]]:
    """Detect files that have been modified since last sync using optimized SQL.

    Only checks files in database, then verifies against filesystem.
    Much faster than checking all files individually.

    Args:
        config: Configuration object

    Returns:
        List of track records that have changed
    """
    changed_tracks = []

    with get_db_connection() as conn:
        # Optimized query: only get tracks that might need checking
        # Either never synced (file_mtime IS NULL) or potentially changed
        cursor = conn.execute("""
            SELECT id, local_path, file_mtime, last_synced_at
            FROM tracks
            WHERE local_path IS NOT NULL
        """)

        for row in cursor.fetchall():
            track = dict(row)
            local_path = track["local_path"]

            # Check if file still exists
            if not os.path.exists(local_path):
                continue

            current_mtime = get_file_mtime(local_path)
            if current_mtime is None:
                continue

            # Check if file has been modified
            stored_mtime = track["file_mtime"]

            # If no stored mtime, or if current mtime is newer, file has changed
            if stored_mtime is None or current_mtime > stored_mtime:
                track["current_mtime"] = current_mtime
                changed_tracks.append(track)

    return changed_tracks


def sync_metadata_export(
    track_ids: Optional[list[int]] = None, show_progress: bool = True
) -> dict[str, int]:
    """Export database metadata to file metadata.

    Writes title, artist, album, genre, year, bpm, key from database to files.

    Args:
        track_ids: Optional list of specific track IDs to export (None = all with local_path)
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'skipped': count}
    """
    from music_minion.domain.library.metadata import write_metadata_to_file

    stats = {"success": 0, "failed": 0, "skipped": 0}

    with get_db_connection() as conn:
        # Get tracks to export - only those with metadata changes since last export
        # Export if:
        #   1. Never written to file (file_mtime IS NULL)
        #   2. OR metadata updated after last file write (metadata_updated_at > file_mtime)
        # Do NOT export if metadata never updated (NULL) but file already written
        if track_ids:
            placeholders = ",".join("?" * len(track_ids))
            cursor = conn.execute(
                f"""
                SELECT id, local_path, title, artist, album, genre, year, bpm, key_signature
                FROM tracks
                WHERE id IN ({placeholders})
                  AND local_path IS NOT NULL AND local_path != ''
                  AND (file_mtime IS NULL
                       OR (metadata_updated_at IS NOT NULL
                           AND strftime('%s', metadata_updated_at) > file_mtime))
            """,
                track_ids,
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, local_path, title, artist, album, genre, year, bpm, key_signature
                FROM tracks
                WHERE local_path IS NOT NULL AND local_path != ''
                  AND (file_mtime IS NULL
                       OR (metadata_updated_at IS NOT NULL
                           AND strftime('%s', metadata_updated_at) > file_mtime))
            """
            )

        tracks = [dict(row) for row in cursor.fetchall()]

    if not tracks:
        if show_progress:
            print("No metadata changes to export")
        return stats

    if show_progress:
        print(f"Exporting metadata to {len(tracks)} file(s)...")

    total_tracks = len(tracks)
    reported_milestones: set[int] = set()

    # Batch mtime updates
    mtime_updates = []

    for i, track in enumerate(tracks, 1):
        local_path = track["local_path"]

        # Check if file exists
        if not local_path or not os.path.exists(local_path):
            stats["skipped"] += 1
            continue

        # Write metadata to file
        success = write_metadata_to_file(
            local_path,
            title=track.get("title"),
            artist=track.get("artist"),
            album=track.get("album"),
            genre=track.get("genre"),
            year=track.get("year"),
            bpm=track.get("bpm"),
            key=track.get("key_signature"),
        )

        if success:
            # Get mtime after write to update database
            current_mtime = get_file_mtime(local_path)
            mtime_updates.append((current_mtime, track["id"]))
            stats["success"] += 1
        else:
            stats["failed"] += 1

        # Milestone-based progress (25%, 50%, 75%, 100%)
        if show_progress:
            percent = (i * 100) // total_tracks
            if percent in {25, 50, 75, 100} and percent not in reported_milestones:
                reported_milestones.add(percent)
                print(f"  {percent}% complete ({i}/{total_tracks})")

    # Batch update mtimes in database
    if mtime_updates:
        with get_db_connection() as conn:
            conn.executemany(
                """
                UPDATE tracks
                SET file_mtime = ?
                WHERE id = ?
            """,
                mtime_updates,
            )
            conn.commit()

    if show_progress:
        print(
            f"\nMetadata export complete: {stats['success']} succeeded, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )

    return stats


def sync_elo_export(
    track_ids: Optional[list[int]] = None,
    show_progress: bool = True,
) -> dict[str, int]:
    """Export global ELO ratings to file metadata.

    Writes GLOBAL_ELO tag to audio files for tracks that have been rated.
    Skips tracks with default ELO (1500) to avoid cluttering unrated tracks.

    Args:
        track_ids: Optional list of specific track IDs to export (None = all rated tracks)
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'skipped': count}
    """
    stats = {"success": 0, "failed": 0, "skipped": 0}

    with get_db_connection() as conn:
        # Get tracks with ELO ratings that have been compared
        if track_ids:
            placeholders = ",".join("?" * len(track_ids))
            cursor = conn.execute(
                f"""
                SELECT t.id, t.local_path, e.rating
                FROM tracks t
                JOIN elo_ratings e ON t.id = e.track_id
                WHERE t.id IN ({placeholders})
                  AND t.local_path IS NOT NULL AND t.local_path != ''
                  AND e.rating != 1500.0 AND e.comparison_count > 0
            """,
                track_ids,
            )
        else:
            cursor = conn.execute(
                """
                SELECT t.id, t.local_path, e.rating
                FROM tracks t
                JOIN elo_ratings e ON t.id = e.track_id
                WHERE t.local_path IS NOT NULL AND t.local_path != ''
                  AND e.rating != 1500.0 AND e.comparison_count > 0
            """
            )

        tracks = [dict(row) for row in cursor.fetchall()]

    if not tracks:
        if show_progress:
            print("No rated tracks to export ELO for")
        return stats

    if show_progress:
        print(f"Exporting ELO ratings to {len(tracks)} file(s)...")

    total_tracks = len(tracks)
    reported_milestones: set[int] = set()

    for i, track in enumerate(tracks, 1):
        local_path = track["local_path"]

        # Check if file exists
        if not os.path.exists(local_path):
            stats["skipped"] += 1
            continue

        # Write ELO to file
        success = write_elo_to_file(
            local_path,
            global_elo=track["rating"],
            update_comment=False,
        )

        if success:
            stats["success"] += 1
        else:
            stats["failed"] += 1

        # Milestone-based progress (25%, 50%, 75%, 100%)
        if show_progress:
            percent = (i * 100) // total_tracks
            if percent in {25, 50, 75, 100} and percent not in reported_milestones:
                reported_milestones.add(percent)
                print(f"  {percent}% complete ({i}/{total_tracks})")

    if show_progress:
        print(
            f"\nELO export complete: {stats['success']} succeeded, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )

    return stats


def sync_export(
    config: Config, track_ids: Optional[list[int]] = None, show_progress: bool = True
) -> dict[str, int]:
    """Export database tags to file metadata with atomic writes.

    Writes all tags from database to file metadata COMMENT fields.

    Args:
        config: Configuration object
        track_ids: Optional list of specific track IDs to export (None = all)
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'skipped': count}
    """
    stats = {"success": 0, "failed": 0, "skipped": 0}

    if not config.sync.write_tags_to_metadata:
        if show_progress:
            print("Tag writing disabled in config (write_tags_to_metadata = false)")
        return stats

    with get_db_connection() as conn:
        # Get tracks to export
        if track_ids:
            placeholders = ",".join("?" * len(track_ids))
            cursor = conn.execute(
                f"""
                SELECT id, local_path FROM tracks
                WHERE id IN ({placeholders})
            """,
                track_ids,
            )
        else:
            cursor = conn.execute("SELECT id, local_path FROM tracks")

        tracks = [dict(row) for row in cursor.fetchall()]

    if show_progress:
        print(f"Exporting tags to {len(tracks)} file(s)...")

    total_tracks = len(tracks)
    reported_milestones: set[int] = set()

    # Batch database updates
    updates = []

    for i, track in enumerate(tracks, 1):
        track_id = track["id"]
        local_path = track["local_path"]

        # Check if file exists
        if not os.path.exists(local_path):
            stats["skipped"] += 1
            continue

        # Get mtime BEFORE write to avoid race condition
        mtime_before = get_file_mtime(local_path)

        # Get tags from database
        db_tags = get_track_tags(track_id, include_blacklisted=False)
        tag_names = [tag["tag_name"] for tag in db_tags]

        # Write to file
        if write_tags_to_file(local_path, tag_names, config):
            # Get mtime AFTER write
            current_mtime = get_file_mtime(local_path)
            updates.append((current_mtime, track_id))
            stats["success"] += 1
        else:
            stats["failed"] += 1

        # Milestone-based progress (25%, 50%, 75%, 100%)
        if show_progress:
            percent = (i * 100) // total_tracks
            if percent in {25, 50, 75, 100} and percent not in reported_milestones:
                reported_milestones.add(percent)
                print(f"  {percent}% complete ({i}/{total_tracks})")

    # Batch update database
    if updates:
        with get_db_connection() as conn:
            conn.executemany(
                """
                UPDATE tracks
                SET file_mtime = ?, last_synced_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                updates,
            )
            conn.commit()

    if show_progress:
        print(
            f"\nExport complete: {stats['success']} succeeded, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )

    return stats


def sync_import(
    config: Config, force_all: bool = False, show_progress: bool = True
) -> dict[str, int]:
    """Import tags from file metadata to database, preserving user/AI tags.

    Reads tags from file metadata and updates database. Only processes
    files that have been modified since last sync (unless force_all=True).

    CRITICAL: Only removes tags where source='file' to prevent data loss
    of user-created and AI-generated tags.

    Args:
        config: Configuration object
        force_all: If True, import from all files regardless of mtime
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'added': count, 'removed': count}
    """
    stats = {"success": 0, "failed": 0, "added": 0, "removed": 0}

    # Detect changed files
    if force_all:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM tracks WHERE local_path IS NOT NULL")
            changed_tracks = [dict(row) for row in cursor.fetchall()]
    else:
        changed_tracks = detect_file_changes(config)

    if not changed_tracks:
        if show_progress:
            print("No files need importing.")
        return stats

    if show_progress:
        if force_all:
            print(f"Importing tags from all {len(changed_tracks)} file(s)...")
        else:
            print(f"Importing tags from {len(changed_tracks)} changed file(s)...")

    total_tracks = len(changed_tracks)
    reported_milestones: set[int] = set()

    # Batch load all tags for changed tracks (optimization: single query instead of N queries)
    track_ids = [track["id"] for track in changed_tracks]
    all_tags_batch = get_track_tags_batch(track_ids, include_blacklisted=False)

    # Batch database updates
    mtime_updates = []

    for i, track in enumerate(changed_tracks, 1):
        track_id = track["id"]
        local_path = track["local_path"]

        # Check if file exists
        if not os.path.exists(local_path):
            stats["failed"] += 1
            continue

        try:
            # Read tags from file
            file_tags = read_tags_from_file(local_path, config)
            file_tag_set = set(file_tags)

            # Get current database tags from batch result
            db_tags = all_tags_batch.get(track_id, [])
            db_tag_dict = {tag["tag_name"]: tag["source"] for tag in db_tags}
            db_tag_set = set(db_tag_dict.keys())

            # Find tags to add and remove
            tags_to_add = file_tag_set - db_tag_set
            tags_to_remove = db_tag_set - file_tag_set

            # Add new tags from file
            if tags_to_add:
                add_tags(track_id, list(tags_to_add), source="file")
                stats["added"] += len(tags_to_add)

            # CRITICAL: Only remove tags where source='file'
            # This preserves user and AI tags from being deleted
            for tag in tags_to_remove:
                tag_source = db_tag_dict.get(tag)
                if tag_source == "file":
                    remove_tag(track_id, tag)
                    stats["removed"] += 1
                # else: Keep user/AI tags even if not in file

            # Update mtime for batch processing
            current_mtime = get_file_mtime(local_path)
            mtime_updates.append((current_mtime, track_id))
            stats["success"] += 1

        except Exception as e:
            if show_progress:
                print(f"  Error importing {local_path}: {e}")
            stats["failed"] += 1

        # Milestone-based progress (25%, 50%, 75%, 100%)
        if show_progress:
            percent = (i * 100) // total_tracks
            if percent in {25, 50, 75, 100} and percent not in reported_milestones:
                reported_milestones.add(percent)
                print(f"  {percent}% complete ({i}/{total_tracks})")

    # Batch update mtimes
    if mtime_updates:
        with get_db_connection() as conn:
            conn.executemany(
                """
                UPDATE tracks
                SET file_mtime = ?, last_synced_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                mtime_updates,
            )
            conn.commit()

    if show_progress:
        print(
            f"\nImport complete: {stats['success']} files processed, "
            f"{stats['added']} tags added, {stats['removed']} tags removed, "
            f"{stats['failed']} failed"
        )

    return stats


def get_sync_status(config: Config) -> dict[str, Any]:
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
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM tracks WHERE local_path IS NOT NULL"
        )
        total_tracks = cursor.fetchone()["count"]

        # Get last sync time
        cursor = conn.execute("""
            SELECT MAX(last_synced_at) as last_sync
            FROM tracks
            WHERE last_synced_at IS NOT NULL
        """)
        last_sync_row = cursor.fetchone()
        last_sync = last_sync_row["last_sync"] if last_sync_row else None

        # Count tracks never synced
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM tracks
            WHERE local_path IS NOT NULL AND last_synced_at IS NULL
        """)
        never_synced = cursor.fetchone()["count"]

    return {
        "total_tracks": total_tracks,
        "changed_files": len(changed_files),
        "never_synced": never_synced,
        "last_sync": last_sync,
        "sync_enabled": config.sync.write_tags_to_metadata,
    }


def rescan_library(
    config: Config, full_rescan: bool = False, show_progress: bool = True
) -> dict[str, int]:
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


def path_similarity(path1: str, path2: str) -> float:
    """Calculate similarity between two directory paths (0.0-1.0).

    Uses difflib.SequenceMatcher on path components to determine
    how similar two directory paths are.

    Args:
        path1: First directory path
        path2: Second directory path

    Returns:
        Similarity score from 0.0 (completely different) to 1.0 (identical)

    Example:
        >>> path_similarity("/Music/Album1", "/Music/Album2")
        0.8
        >>> path_similarity("/Music/Album1", "/Music/Album1/Disc2")
        0.9
    """
    from difflib import SequenceMatcher
    from pathlib import Path

    parts1 = Path(path1).parts
    parts2 = Path(path2).parts
    return SequenceMatcher(None, parts1, parts2).ratio()


def detect_missing_and_moved_files(config: Config) -> dict[str, Any]:
    """Detect missing files and attempt to relocate moved files.

    Scans all local tracks in the database and checks if their files still exist.
    For missing files, attempts to match them with untracked files on disk using
    filename + filesize. Files with .sync-conflict- in their path are auto-deleted.

    Algorithm:
        1. Query all source='local' tracks from database
        2. Check which tracks have missing files (local_path doesn't exist)
        3. Build index of all untracked files on disk
        4. For each missing file:
           - If Syncthing conflict → delete
           - If filename match with same filesize → relocate
           - If multiple matches → pick closest by path similarity (≥0.8)
           - If no match → delete

    Args:
        config: Configuration object with library paths

    Returns:
        Dictionary with keys:
            - relocated: Count of files successfully relocated
            - deleted: Count of orphaned records deleted
            - actions: Detailed list of all actions taken
    """
    from pathlib import Path

    from loguru import logger

    AUTO_RELOCATE_THRESHOLD = 0.8  # Path similarity threshold for auto-match

    # Step 1: Query all local tracks
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, local_path, title, artist
            FROM tracks
            WHERE source = 'local' AND local_path IS NOT NULL
        """)
        db_tracks = [dict(row) for row in cursor.fetchall()]

    # Step 2: Separate Syncthing conflicts and missing files
    actions = []
    syncthing_conflicts = []
    missing_tracks = []

    for track in db_tracks:
        # Auto-delete ALL Syncthing conflict tracks (regardless of file existence)
        if '.sync-conflict-' in track['local_path']:
            syncthing_conflicts.append(track)
            actions.append({
                'type': 'delete',
                'track_id': track['id'],
                'old_path': track['local_path'],
                'reason': 'syncthing_conflict'
            })
        elif not os.path.exists(track['local_path']):
            missing_tracks.append(track)

    if syncthing_conflicts:
        logger.info(f"Found {len(syncthing_conflicts)} Syncthing conflict tracks to delete")

    if not missing_tracks and not syncthing_conflicts:
        logger.info("No missing files or conflicts detected")
        return {'relocated': 0, 'deleted': 0, 'actions': []}

    logger.info(f"Found {len(missing_tracks)} tracks with missing files")

    # Step 3: Build untracked file index
    all_files_on_disk = set()
    for library_path in config.music.library_paths:
        for ext in config.music.supported_formats:
            all_files_on_disk.update(Path(library_path).rglob(f"*{ext}"))

    # Filter to untracked files (not in database)
    db_paths = {t['local_path'] for t in db_tracks}
    untracked_files = all_files_on_disk - db_paths

    # Index by filename: {filename: [(full_path, filesize), ...]}
    untracked_index = {}
    for filepath in untracked_files:
        # Skip Syncthing conflicts
        if '.sync-conflict-' in filepath.name:
            continue

        filename = filepath.name
        try:
            filesize = filepath.stat().st_size
            untracked_index.setdefault(filename, []).append((str(filepath), filesize))
        except OSError:
            # Skip files we can't stat
            continue

    logger.info(f"Found {len(untracked_files)} untracked files, {len(untracked_index)} unique filenames")

    # Step 4: Match and classify missing files
    # Note: actions list already initialized in Step 2 with Syncthing conflicts

    for missing in missing_tracks:
        old_path = missing['local_path']

        # Try to match by filename
        filename = Path(old_path).name
        candidates = untracked_index.get(filename, [])

        if not candidates:
            # No match - schedule for deletion
            actions.append({
                'type': 'delete',
                'track_id': missing['id'],
                'old_path': old_path,
                'reason': 'file_not_found'
            })

        elif len(candidates) == 1:
            # Single candidate - auto-relocate
            new_path, new_size = candidates[0]
            actions.append({
                'type': 'relocate',
                'track_id': missing['id'],
                'old_path': old_path,
                'new_path': new_path
            })

        else:
            # Multiple candidates - pick best by path similarity
            old_dir = str(Path(old_path).parent)
            best_match = None
            best_score = 0

            for new_path, new_size in candidates:
                new_dir = str(Path(new_path).parent)
                score = path_similarity(old_dir, new_dir)
                if score > best_score:
                    best_score = score
                    best_match = new_path

            if best_score >= AUTO_RELOCATE_THRESHOLD:
                actions.append({
                    'type': 'relocate',
                    'track_id': missing['id'],
                    'old_path': old_path,
                    'new_path': best_match,
                    'confidence': best_score
                })
            else:
                # Low confidence - delete (file likely truly gone)
                actions.append({
                    'type': 'delete',
                    'track_id': missing['id'],
                    'old_path': old_path,
                    'reason': 'ambiguous_match_low_confidence'
                })

    # Step 5: Execute actions (batch operations)
    relocated_count = 0
    deleted_count = 0

    with get_db_connection() as conn:
        # Batch relocations
        relocate_updates = [
            (action['new_path'], action['track_id'])
            for action in actions if action['type'] == 'relocate'
        ]
        if relocate_updates:
            conn.executemany("""
                UPDATE tracks
                SET local_path = ?, file_mtime = NULL
                WHERE id = ?
            """, relocate_updates)
            relocated_count = len(relocate_updates)

        # Batch deletions
        delete_ids = [
            (action['track_id'],)
            for action in actions if action['type'] == 'delete'
        ]
        if delete_ids:
            conn.executemany("""
                DELETE FROM tracks WHERE id = ?
            """, delete_ids)
            deleted_count = len(delete_ids)

        conn.commit()

    # Log detailed actions
    logger.info(f"Cleanup complete: {relocated_count} relocated, {deleted_count} deleted")
    for action in actions:
        if action['type'] == 'relocate':
            logger.info(f"Relocated: {action['old_path']} → {action['new_path']}")
        elif action['type'] == 'delete':
            logger.info(f"Deleted: {action['old_path']} (reason: {action['reason']})")

    return {
        'relocated': relocated_count,
        'deleted': deleted_count,
        'actions': actions
    }
