#!/usr/bin/env python3
"""
Migration script to separate SoundCloud tracks that have local paths.

Creates separate local records for tracks with source='soundcloud' and local_path set,
updates all foreign key references to point to the new local track IDs, and clears
local_path on the original SoundCloud tracks.
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.core.database import get_db_connection


def verify_pre_migration(conn) -> tuple[int, list[int]]:
    """Verify tracks needing migration and return count and IDs.

    Returns:
        Tuple of (count, list of track IDs)
    """
    cursor = conn.execute("""
        SELECT id, title, artist, local_path
        FROM tracks
        WHERE source = 'soundcloud' AND local_path IS NOT NULL
        ORDER BY id
    """)
    tracks = cursor.fetchall()

    if not tracks:
        logger.info("No tracks found needing migration")
        return 0, []

    logger.info(f"Found {len(tracks)} tracks with source='soundcloud' and local_path:")
    for track in tracks[:5]:  # Show first 5 as sample
        logger.info(f"  - ID {track[0]}: {track[1]} by {track[2]} ({track[3]})")
    if len(tracks) > 5:
        logger.info(f"  ... and {len(tracks) - 5} more")

    return len(tracks), [track[0] for track in tracks]


def verify_post_migration(conn, original_track_ids: list[int]) -> None:
    """Verify migration was successful."""
    # Check original tracks have local_path cleared
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM tracks
        WHERE id IN ({})
        AND local_path IS NOT NULL
    """.format(",".join("?" * len(original_track_ids))), original_track_ids)
    remaining_with_path = cursor.fetchone()[0]

    if remaining_with_path > 0:
        logger.error(f"ERROR: {remaining_with_path} SoundCloud tracks still have local_path set")
        return

    logger.info(f"✓ All {len(original_track_ids)} SoundCloud tracks have local_path cleared")

    # Check new local records were created
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM tracks
        WHERE source = 'local'
        AND soundcloud_id IS NOT NULL
        AND soundcloud_id IN (
            SELECT soundcloud_id
            FROM tracks
            WHERE id IN ({})
        )
    """.format(",".join("?" * len(original_track_ids))), original_track_ids)
    new_local_count = cursor.fetchone()[0]

    logger.info(f"✓ Created {new_local_count} new local track records")


def migrate_track(conn, track_id: int, dry_run: bool) -> int | None:
    """Migrate a single track and return the new local track ID.

    Returns:
        New local track ID if successful, None if dry run
    """
    # Get original track data
    cursor = conn.execute("""
        SELECT local_path, title, artist, top_level_artist, album, genre, year,
               duration, key_signature, bpm, created_at, updated_at, enriched_at,
               file_mtime, last_synced_at, remix_artist, soundcloud_id,
               soundcloud_synced_at
        FROM tracks
        WHERE id = ?
    """, (track_id,))
    track = cursor.fetchone()

    if not track:
        logger.error(f"Track {track_id} not found")
        return None

    if dry_run:
        logger.info(f"[DRY RUN] Would create local track for: {track[1]} by {track[2]}")
        return None

    # Insert new local track (copy all fields, set source='local')
    cursor = conn.execute("""
        INSERT INTO tracks (
            source, local_path, title, artist, top_level_artist, album, genre, year,
            duration, key_signature, bpm, created_at, updated_at, enriched_at,
            file_mtime, last_synced_at, remix_artist, soundcloud_id,
            soundcloud_synced_at
        )
        VALUES (
            'local', ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?
        )
    """, ('local',) + track)

    new_local_id = cursor.lastrowid
    logger.info(f"Created local track {new_local_id} for SoundCloud track {track_id}: {track[1]} by {track[2]}")

    return new_local_id


def update_fk_tables(conn, old_track_id: int, new_track_id: int, dry_run: bool) -> None:
    """Update all foreign key references from old track ID to new track ID."""

    # Define all FK tables and their track_id columns
    fk_updates = [
        ("playlist_tracks", "track_id"),
        ("ratings", "track_id"),
        ("notes", "track_id"),
        ("playback_sessions", "track_id"),
        ("tags", "track_id"),
        ("track_emojis", "track_id"),
        ("track_dimension_votes", "track_id"),
        ("bucket_tracks", "track_id"),
        ("track_genres", "track_id"),
        ("radio_history", "track_id"),
        ("radio_skipped", "track_id"),
        ("track_listen_sessions", "track_id"),
        ("playlist_elo_ratings", "track_id"),
        ("ai_requests", "track_id"),
        ("playlist_builder_skipped", "track_id"),
        ("playlist_builder_sessions", "last_processed_track_id"),
    ]

    total_updated = 0

    for table_name, column_name in fk_updates:
        # Check if table exists and has records to update
        cursor = conn.execute(f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE {column_name} = ?
        """, (old_track_id,))
        count = cursor.fetchone()[0]

        if count > 0:
            if dry_run:
                logger.info(f"[DRY RUN] Would update {count} rows in {table_name}.{column_name}")
            else:
                conn.execute(f"""
                    UPDATE {table_name}
                    SET {column_name} = ?
                    WHERE {column_name} = ?
                """, (new_track_id, old_track_id))
                logger.info(f"Updated {count} rows in {table_name}.{column_name}")
            total_updated += count

    # Special case: playlist_comparison_history has TEXT columns for track IDs
    text_columns = [
        ("playlist_comparison_history", "track_a_id"),
        ("playlist_comparison_history", "track_b_id"),
        ("playlist_comparison_history", "winner_id"),
    ]

    for table_name, column_name in text_columns:
        cursor = conn.execute(f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE {column_name} = ?
        """, (str(old_track_id),))
        count = cursor.fetchone()[0]

        if count > 0:
            if dry_run:
                logger.info(f"[DRY RUN] Would update {count} rows in {table_name}.{column_name} (TEXT)")
            else:
                conn.execute(f"""
                    UPDATE {table_name}
                    SET {column_name} = ?
                    WHERE {column_name} = ?
                """, (str(new_track_id), str(old_track_id)))
                logger.info(f"Updated {count} rows in {table_name}.{column_name} (TEXT)")
            total_updated += count

    if total_updated == 0 and not dry_run:
        logger.info(f"No FK references found for track {old_track_id}")


def clear_soundcloud_local_path(conn, track_id: int, dry_run: bool) -> None:
    """Clear local_path on the original SoundCloud track."""
    if dry_run:
        logger.info(f"[DRY RUN] Would clear local_path on SoundCloud track {track_id}")
        return

    conn.execute("""
        UPDATE tracks
        SET local_path = NULL
        WHERE id = ?
    """, (track_id,))
    logger.info(f"Cleared local_path on SoundCloud track {track_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SoundCloud tracks with local paths to separate local records"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing to database"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SoundCloud/Local Track Migration Script")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be committed")
        logger.info("")

    with get_db_connection() as conn:
        # Pre-migration verification
        logger.info("Running pre-migration verification...")
        track_count, track_ids = verify_pre_migration(conn)

        if track_count == 0:
            logger.info("Nothing to migrate. Exiting.")
            return

        logger.info("")
        logger.info(f"Will migrate {track_count} tracks")
        logger.info("")

        # Begin migration (atomic transaction)
        try:
            if not args.dry_run:
                conn.execute("BEGIN TRANSACTION")

            migrated = 0
            for track_id in track_ids:
                # Create new local track
                new_local_id = migrate_track(conn, track_id, args.dry_run)

                if new_local_id:
                    # Update FK references
                    update_fk_tables(conn, track_id, new_local_id, args.dry_run)

                    # Clear local_path on original SoundCloud track
                    clear_soundcloud_local_path(conn, track_id, args.dry_run)

                    migrated += 1
                    logger.info("")

            if args.dry_run:
                logger.info("=" * 60)
                logger.info(f"DRY RUN COMPLETE - Would migrate {track_count} tracks")
                logger.info("Run without --dry-run to apply changes")
            else:
                # Commit transaction
                conn.commit()
                logger.info("=" * 60)
                logger.info(f"Migration complete - migrated {migrated} tracks")
                logger.info("")

                # Post-migration verification
                logger.info("Running post-migration verification...")
                verify_post_migration(conn, track_ids)

        except Exception as e:
            if not args.dry_run:
                conn.rollback()
                logger.exception("Migration failed - rolled back all changes")
            raise

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
