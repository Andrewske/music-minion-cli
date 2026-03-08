"""Bucket session query functions for playlist organization."""

import random
import uuid
from typing import Any

from loguru import logger

from music_minion.core.database import get_db_connection
from .emojis import (
    add_emoji_to_track_mutation,
    remove_emoji_from_track_mutation,
)


def get_or_create_session(playlist_id: int) -> dict[str, Any]:
    """Get active session for playlist or create new one.

    Idempotent: partial unique index guarantees single active session.
    On resume: reconciles bucket_tracks against current playlist_tracks
      - Removes orphaned tracks (no longer in playlist)
      - New playlist tracks appear in unassigned_track_ids

    Args:
        playlist_id: ID of the playlist

    Returns:
        Session dict with id, playlist_id, status, buckets, unassigned_track_ids
    """
    with get_db_connection() as conn:
        # Try to get existing active session
        cursor = conn.execute(
            """
            SELECT id, playlist_id, status
            FROM bucket_sessions
            WHERE playlist_id = ? AND status = 'active'
            """,
            (playlist_id,),
        )
        session = cursor.fetchone()

        if session:
            session_id = session["id"]
            logger.info(f"Resuming existing bucket session {session_id}")

            # Reconcile: remove bucket_tracks that are no longer in playlist
            conn.execute(
                """
                DELETE FROM bucket_tracks
                WHERE bucket_id IN (
                    SELECT id FROM buckets WHERE session_id = ?
                )
                AND track_id NOT IN (
                    SELECT track_id FROM playlist_tracks WHERE playlist_id = ?
                )
                """,
                (session_id, playlist_id),
            )
            conn.commit()

            result = get_session_with_data(session_id)
            # Session must exist since we just found it
            assert result is not None
            return result

        # Create new session
        session_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO bucket_sessions (id, playlist_id, status)
            VALUES (?, ?, 'active')
            """,
            (session_id, playlist_id),
        )
        conn.commit()

        logger.info(
            f"Created new bucket session {session_id} for playlist {playlist_id}"
        )

        return {
            "id": session_id,
            "playlist_id": playlist_id,
            "status": "active",
            "buckets": [],
            "unassigned_track_ids": _get_unassigned_track_ids(
                conn, session_id, playlist_id
            ),
        }


def get_session_with_data(session_id: str) -> dict[str, Any] | None:
    """Get session with all buckets and track assignments.

    Args:
        session_id: UUID of the session

    Returns:
        Session dict with id, playlist_id, status, buckets, unassigned_track_ids,
        or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, playlist_id, status
            FROM bucket_sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        session = cursor.fetchone()

        if not session:
            return None

        playlist_id = session["playlist_id"]

        # Get all buckets with their track IDs
        buckets_cursor = conn.execute(
            """
            SELECT b.id, b.name, b.emoji_id, b.position,
                   bpl.playlist_id as linked_playlist_id,
                   p.name as linked_playlist_name
            FROM buckets b
            LEFT JOIN bucket_playlist_links bpl ON b.id = bpl.bucket_id
            LEFT JOIN playlists p ON bpl.playlist_id = p.id
            WHERE b.session_id = ?
            ORDER BY b.position ASC
            """,
            (session_id,),
        )
        buckets = []
        for bucket_row in buckets_cursor.fetchall():
            bucket_id = bucket_row["id"]

            # Get track IDs for this bucket in order
            tracks_cursor = conn.execute(
                """
                SELECT track_id
                FROM bucket_tracks
                WHERE bucket_id = ?
                ORDER BY position ASC
                """,
                (bucket_id,),
            )
            track_ids = [row["track_id"] for row in tracks_cursor.fetchall()]

            buckets.append(
                {
                    "id": bucket_id,
                    "name": bucket_row["name"],
                    "emoji_id": bucket_row["emoji_id"],
                    "position": bucket_row["position"],
                    "track_ids": track_ids,
                    "linked_playlist_id": bucket_row["linked_playlist_id"],
                    "linked_playlist_name": bucket_row["linked_playlist_name"],
                }
            )

        return {
            "id": session_id,
            "playlist_id": playlist_id,
            "status": session["status"],
            "buckets": buckets,
            "unassigned_track_ids": _get_unassigned_track_ids(
                conn, session_id, playlist_id
            ),
        }


def _get_unassigned_track_ids(conn, session_id: str, playlist_id: int) -> list[int]:
    """Get track IDs from playlist that are not in any bucket.

    Args:
        conn: Database connection
        session_id: UUID of the session
        playlist_id: ID of the playlist

    Returns:
        List of track IDs not assigned to any bucket
    """
    cursor = conn.execute(
        """
        SELECT pt.track_id
        FROM playlist_tracks pt
        WHERE pt.playlist_id = ?
        AND pt.track_id NOT IN (
            SELECT bt.track_id
            FROM bucket_tracks bt
            JOIN buckets b ON bt.bucket_id = b.id
            WHERE b.session_id = ?
        )
        ORDER BY pt.position ASC
        """,
        (playlist_id, session_id),
    )
    return [row["track_id"] for row in cursor.fetchall()]


def create_bucket(
    session_id: str, name: str, emoji_id: str | None, position: int
) -> dict[str, Any]:
    """Create a new bucket in the session.

    Args:
        session_id: UUID of the session
        name: Display name for the bucket
        emoji_id: Optional emoji to auto-add to tracks
        position: Order position in the bucket list

    Returns:
        Bucket dict with id, name, emoji_id, position, track_ids
    """
    with get_db_connection() as conn:
        bucket_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO buckets (id, session_id, name, emoji_id, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            (bucket_id, session_id, name, emoji_id, position),
        )
        conn.commit()

        logger.info(f"Created bucket {bucket_id} '{name}' in session {session_id}")

        return {
            "id": bucket_id,
            "name": name,
            "emoji_id": emoji_id,
            "position": position,
            "track_ids": [],
            "linked_playlist_id": None,
            "linked_playlist_name": None,
        }


def update_bucket(
    bucket_id: str, name: str | None, emoji_id: str | None
) -> dict[str, Any] | None:
    """Update bucket name/emoji.

    Emoji change propagation:
      1. If old emoji exists: remove from all bucket tracks (by source_id=bucket_id)
      2. If new emoji set: add to all bucket tracks with source_type='bucket', source_id=bucket_id
      3. Batch operations with executemany() for efficiency

    Args:
        bucket_id: UUID of the bucket
        name: New name (or None to keep existing)
        emoji_id: New emoji (or None to keep existing, or empty string to clear)

    Returns:
        Updated bucket dict or None if not found
    """
    with get_db_connection() as conn:
        # Get current bucket state
        cursor = conn.execute(
            """
            SELECT id, session_id, name, emoji_id, position
            FROM buckets
            WHERE id = ?
            """,
            (bucket_id,),
        )
        bucket = cursor.fetchone()

        if not bucket:
            return None

        old_emoji_id = bucket["emoji_id"]
        new_name = name if name is not None else bucket["name"]
        new_emoji_id = emoji_id if emoji_id is not None else old_emoji_id

        # Handle emoji change propagation
        if emoji_id is not None and old_emoji_id != new_emoji_id:
            # Get all tracks in this bucket
            tracks_cursor = conn.execute(
                """
                SELECT track_id FROM bucket_tracks WHERE bucket_id = ?
                """,
                (bucket_id,),
            )
            track_ids = [row["track_id"] for row in tracks_cursor.fetchall()]

            # Remove old emoji from all tracks (if exists)
            if old_emoji_id and track_ids:
                logger.info(
                    f"Removing emoji {old_emoji_id} from {len(track_ids)} tracks"
                )
                for track_id in track_ids:
                    remove_emoji_from_track_mutation(
                        track_id, old_emoji_id, conn, source_id=bucket_id, force=True
                    )

            # Add new emoji to all tracks (if set)
            if new_emoji_id and track_ids:
                logger.info(f"Adding emoji {new_emoji_id} to {len(track_ids)} tracks")
                for track_id in track_ids:
                    add_emoji_to_track_mutation(
                        track_id,
                        new_emoji_id,
                        conn,
                        source_type="bucket",
                        source_id=bucket_id,
                    )

        # Update bucket record
        conn.execute(
            """
            UPDATE buckets
            SET name = ?, emoji_id = ?
            WHERE id = ?
            """,
            (new_name, new_emoji_id, bucket_id),
        )
        conn.commit()

        # Get updated track IDs
        tracks_cursor = conn.execute(
            """
            SELECT track_id FROM bucket_tracks
            WHERE bucket_id = ?
            ORDER BY position ASC
            """,
            (bucket_id,),
        )
        track_ids = [row["track_id"] for row in tracks_cursor.fetchall()]

        # Get link information
        link_cursor = conn.execute(
            """
            SELECT bpl.playlist_id, p.name
            FROM bucket_playlist_links bpl
            LEFT JOIN playlists p ON bpl.playlist_id = p.id
            WHERE bpl.bucket_id = ?
            """,
            (bucket_id,),
        )
        link_row = link_cursor.fetchone()

        return {
            "id": bucket_id,
            "name": new_name,
            "emoji_id": new_emoji_id,
            "position": bucket["position"],
            "track_ids": track_ids,
            "linked_playlist_id": link_row["playlist_id"] if link_row else None,
            "linked_playlist_name": link_row["name"] if link_row else None,
        }


def delete_bucket(bucket_id: str) -> bool:
    """Delete bucket, remove its emojis from tracks, return tracks to unassigned.

    Args:
        bucket_id: UUID of the bucket

    Returns:
        True if deleted, False if not found
    """
    with get_db_connection() as conn:
        # Get bucket info
        cursor = conn.execute(
            """
            SELECT id, emoji_id, session_id
            FROM buckets
            WHERE id = ?
            """,
            (bucket_id,),
        )
        bucket = cursor.fetchone()

        if not bucket:
            return False

        emoji_id = bucket["emoji_id"]

        # Get all tracks in this bucket
        tracks_cursor = conn.execute(
            """
            SELECT track_id FROM bucket_tracks WHERE bucket_id = ?
            """,
            (bucket_id,),
        )
        track_ids = [row["track_id"] for row in tracks_cursor.fetchall()]

        # Remove bucket's emoji from all tracks (if exists)
        if emoji_id and track_ids:
            logger.info(
                f"Removing bucket emoji {emoji_id} from {len(track_ids)} tracks"
            )
            for track_id in track_ids:
                remove_emoji_from_track_mutation(
                    track_id, emoji_id, conn, source_id=bucket_id, force=True
                )

        # Delete bucket (cascade will delete bucket_tracks)
        conn.execute("DELETE FROM buckets WHERE id = ?", (bucket_id,))
        conn.commit()

        logger.info(f"Deleted bucket {bucket_id}")
        return True


def move_bucket(bucket_id: str, direction: str) -> bool:
    """Swap bucket position with neighbor.

    Args:
        bucket_id: UUID of the bucket
        direction: 'up' or 'down'

    Returns:
        True if moved, False if not possible or not found
    """
    if direction not in ("up", "down"):
        return False

    with get_db_connection() as conn:
        # Get current bucket
        cursor = conn.execute(
            """
            SELECT id, session_id, position
            FROM buckets
            WHERE id = ?
            """,
            (bucket_id,),
        )
        bucket = cursor.fetchone()

        if not bucket:
            return False

        session_id = bucket["session_id"]
        current_position = bucket["position"]

        # Find neighbor based on direction
        if direction == "up":
            neighbor_cursor = conn.execute(
                """
                SELECT id, position FROM buckets
                WHERE session_id = ? AND position < ?
                ORDER BY position DESC
                LIMIT 1
                """,
                (session_id, current_position),
            )
        else:
            neighbor_cursor = conn.execute(
                """
                SELECT id, position FROM buckets
                WHERE session_id = ? AND position > ?
                ORDER BY position ASC
                LIMIT 1
                """,
                (session_id, current_position),
            )

        neighbor = neighbor_cursor.fetchone()
        if not neighbor:
            return False  # No neighbor to swap with

        # Swap positions
        conn.execute(
            "UPDATE buckets SET position = ? WHERE id = ?",
            (neighbor["position"], bucket_id),
        )
        conn.execute(
            "UPDATE buckets SET position = ? WHERE id = ?",
            (current_position, neighbor["id"]),
        )
        conn.commit()

        logger.info(f"Moved bucket {bucket_id} {direction}")
        return True


def shuffle_bucket_tracks(bucket_id: str) -> list[int]:
    """Randomize track order within bucket, return new order.

    Args:
        bucket_id: UUID of the bucket

    Returns:
        New list of track IDs in shuffled order (empty if bucket not found)
    """
    with get_db_connection() as conn:
        # Get all tracks in bucket
        cursor = conn.execute(
            """
            SELECT id, track_id FROM bucket_tracks
            WHERE bucket_id = ?
            ORDER BY position ASC
            """,
            (bucket_id,),
        )
        tracks = cursor.fetchall()

        if not tracks:
            return []

        # Shuffle track IDs
        track_entries = [(row["id"], row["track_id"]) for row in tracks]
        random.shuffle(track_entries)

        # Update positions
        for new_position, (track_entry_id, _) in enumerate(track_entries):
            conn.execute(
                """
                UPDATE bucket_tracks SET position = ? WHERE id = ?
                """,
                (new_position, track_entry_id),
            )
        conn.commit()

        new_order = [track_id for _, track_id in track_entries]
        logger.info(f"Shuffled {len(new_order)} tracks in bucket {bucket_id}")
        return new_order


def assign_track_to_bucket(bucket_id: str, track_id: int) -> dict[str, Any] | None:
    """Assign track to bucket.

    Steps:
    1. Add to bucket at end
    2. If bucket has emoji, add it to track with source_id=bucket_id
    3. Sync to linked playlist if bucket is linked

    Args:
        bucket_id: UUID of the bucket
        track_id: ID of the track to assign

    Returns:
        Dict with bucket_id, track_id, position, or None if bucket not found
    """
    with get_db_connection() as conn:
        # Get bucket info
        cursor = conn.execute(
            """
            SELECT id, session_id, emoji_id
            FROM buckets
            WHERE id = ?
            """,
            (bucket_id,),
        )
        bucket = cursor.fetchone()

        if not bucket:
            return None

        emoji_id = bucket["emoji_id"]

        # Get next position in this bucket
        position_cursor = conn.execute(
            """
            SELECT COALESCE(MAX(position), -1) + 1 as next_position
            FROM bucket_tracks
            WHERE bucket_id = ?
            """,
            (bucket_id,),
        )
        next_position = position_cursor.fetchone()["next_position"]

        # Add track to bucket
        bucket_track_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO bucket_tracks (id, bucket_id, track_id, position)
            VALUES (?, ?, ?, ?)
            """,
            (bucket_track_id, bucket_id, track_id, next_position),
        )

        # Add bucket's emoji to track (if exists)
        if emoji_id:
            add_emoji_to_track_mutation(
                track_id, emoji_id, conn, source_type="bucket", source_id=bucket_id
            )

        conn.commit()

        # Sync to linked playlist (if bucket is linked)
        sync_track_to_linked_playlist(bucket_id, track_id)

        logger.info(f"Assigned track {track_id} to bucket {bucket_id}")
        return {
            "bucket_id": bucket_id,
            "track_id": track_id,
            "position": next_position,
        }


def unassign_track(bucket_id: str, track_id: int) -> bool:
    """Remove track from bucket, remove bucket's emoji from track.

    Args:
        bucket_id: UUID of the bucket
        track_id: ID of the track to unassign

    Returns:
        True if unassigned, False if not found
    """
    with get_db_connection() as conn:
        # Get bucket's emoji
        cursor = conn.execute(
            """
            SELECT emoji_id FROM buckets WHERE id = ?
            """,
            (bucket_id,),
        )
        bucket = cursor.fetchone()

        if not bucket:
            return False

        # Check if track is in this bucket
        track_cursor = conn.execute(
            """
            SELECT id FROM bucket_tracks
            WHERE bucket_id = ? AND track_id = ?
            """,
            (bucket_id, track_id),
        )
        if not track_cursor.fetchone():
            return False

        # Remove bucket's emoji from track (if exists)
        if bucket["emoji_id"]:
            remove_emoji_from_track_mutation(
                track_id, bucket["emoji_id"], conn, source_id=bucket_id, force=True
            )

        # Remove from bucket
        conn.execute(
            """
            DELETE FROM bucket_tracks
            WHERE bucket_id = ? AND track_id = ?
            """,
            (bucket_id, track_id),
        )
        conn.commit()

        # Unsync from linked playlist (if bucket is linked)
        unsync_track_from_linked_playlist(bucket_id, track_id)

        logger.info(f"Unassigned track {track_id} from bucket {bucket_id}")
        return True


def reorder_bucket_tracks(bucket_id: str, track_ids: list[int]) -> bool:
    """Update position values for tracks in bucket.

    Args:
        bucket_id: UUID of the bucket
        track_ids: List of track IDs in new order

    Returns:
        True if reordered, False if bucket not found
    """
    with get_db_connection() as conn:
        # Verify bucket exists
        cursor = conn.execute(
            "SELECT id FROM buckets WHERE id = ?",
            (bucket_id,),
        )
        if not cursor.fetchone():
            return False

        # Update positions using executemany
        position_data = [
            (position, bucket_id, track_id)
            for position, track_id in enumerate(track_ids)
        ]
        conn.executemany(
            """
            UPDATE bucket_tracks
            SET position = ?
            WHERE bucket_id = ? AND track_id = ?
            """,
            position_data,
        )
        conn.commit()

        logger.info(f"Reordered {len(track_ids)} tracks in bucket {bucket_id}")
        return True


def apply_session(session_id: str) -> bool:
    """Apply bucket order to playlist.

    Steps:
    1. Get all tracks from buckets in order (bucket position, then track position)
    2. Get unassigned tracks in their original relative order
    3. Update playlist_tracks positions: bucket tracks first, then unassigned appended
    4. Mark session as 'applied'

    Unassigned tracks are NOT removed - they are appended after all bucket tracks.

    Args:
        session_id: UUID of the session

    Returns:
        True if applied, False if session not found
    """
    with get_db_connection() as conn:
        # Get session
        cursor = conn.execute(
            """
            SELECT id, playlist_id, status
            FROM bucket_sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        session = cursor.fetchone()

        if not session:
            return False

        if session["status"] != "active":
            logger.warning(
                f"Cannot apply session {session_id}: status is {session['status']}"
            )
            return False

        playlist_id = session["playlist_id"]

        # Get all tracks from buckets in order
        bucket_tracks_cursor = conn.execute(
            """
            SELECT bt.track_id
            FROM buckets b
            JOIN bucket_tracks bt ON b.id = bt.bucket_id
            WHERE b.session_id = ?
            ORDER BY b.position ASC, bt.position ASC
            """,
            (session_id,),
        )

        # Deduplicate: track appears at position of first bucket it's in
        seen = set()
        ordered_track_ids = []
        for row in bucket_tracks_cursor.fetchall():
            if row["track_id"] not in seen:
                ordered_track_ids.append(row["track_id"])
                seen.add(row["track_id"])

        # Get unassigned tracks in their original order
        unassigned_cursor = conn.execute(
            """
            SELECT pt.track_id
            FROM playlist_tracks pt
            WHERE pt.playlist_id = ?
            AND pt.track_id NOT IN (
                SELECT bt.track_id
                FROM bucket_tracks bt
                JOIN buckets b ON bt.bucket_id = b.id
                WHERE b.session_id = ?
            )
            ORDER BY pt.position ASC
            """,
            (playlist_id, session_id),
        )
        unassigned_track_ids = [row["track_id"] for row in unassigned_cursor.fetchall()]

        # Combine: bucket tracks first, then unassigned
        all_track_ids = ordered_track_ids + unassigned_track_ids

        # Update playlist_tracks positions
        position_data = [
            (position, playlist_id, track_id)
            for position, track_id in enumerate(all_track_ids)
        ]
        conn.executemany(
            """
            UPDATE playlist_tracks
            SET position = ?
            WHERE playlist_id = ? AND track_id = ?
            """,
            position_data,
        )

        conn.commit()

        logger.info(
            f"Applied order for session {session_id}: "
            f"{len(ordered_track_ids)} bucket tracks, "
            f"{len(unassigned_track_ids)} unassigned tracks"
        )
        return True


def finalize_session(session_id: str) -> bool:
    """Finalize session - mark as applied and clear bucket data.

    This closes out the organizing session. The playlist order has already
    been applied, this just marks the session as done.

    Args:
        session_id: UUID of the session

    Returns:
        True if finalized, False if session not found or not active
    """
    with get_db_connection() as conn:
        # Get session
        cursor = conn.execute(
            """
            SELECT id, status FROM bucket_sessions WHERE id = ?
            """,
            (session_id,),
        )
        session = cursor.fetchone()

        if not session:
            return False

        if session["status"] != "active":
            logger.warning(
                f"Cannot finalize session {session_id}: status is {session['status']}"
            )
            return False

        # Mark session as applied
        conn.execute(
            """
            UPDATE bucket_sessions SET status = 'applied' WHERE id = ?
            """,
            (session_id,),
        )
        conn.commit()

        logger.info(f"Finalized session {session_id}")
        return True


def discard_session(session_id: str) -> bool:
    """Discard session.

    Steps:
    1. Remove all bucket emojis from tracks
    2. Mark session as 'discarded'

    Args:
        session_id: UUID of the session

    Returns:
        True if discarded, False if session not found
    """
    with get_db_connection() as conn:
        # Get session
        cursor = conn.execute(
            """
            SELECT id, status FROM bucket_sessions WHERE id = ?
            """,
            (session_id,),
        )
        session = cursor.fetchone()

        if not session:
            return False

        # Get all buckets with emojis
        buckets_cursor = conn.execute(
            """
            SELECT id, emoji_id FROM buckets
            WHERE session_id = ? AND emoji_id IS NOT NULL
            """,
            (session_id,),
        )

        for bucket in buckets_cursor.fetchall():
            bucket_id = bucket["id"]
            emoji_id = bucket["emoji_id"]

            # Get all tracks in this bucket
            tracks_cursor = conn.execute(
                """
                SELECT track_id FROM bucket_tracks WHERE bucket_id = ?
                """,
                (bucket_id,),
            )

            for track_row in tracks_cursor.fetchall():
                remove_emoji_from_track_mutation(
                    track_row["track_id"],
                    emoji_id,
                    conn,
                    source_id=bucket_id,
                    force=True,
                )

        # Mark session as discarded
        conn.execute(
            """
            UPDATE bucket_sessions SET status = 'discarded' WHERE id = ?
            """,
            (session_id,),
        )
        conn.commit()

        logger.info(f"Discarded session {session_id}")
        return True


def link_bucket_to_playlist(bucket_id: str, playlist_id: int) -> bool:
    """Link bucket to playlist. Returns False if bucket not found.

    Args:
        bucket_id: UUID of the bucket
        playlist_id: ID of the playlist to link to

    Returns:
        True if linked successfully, False if bucket not found
    """
    with get_db_connection() as conn:
        # Verify bucket exists
        cursor = conn.execute(
            "SELECT id FROM buckets WHERE id = ?",
            (bucket_id,),
        )
        if not cursor.fetchone():
            return False

        # Insert or replace link
        link_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT OR REPLACE INTO bucket_playlist_links (id, bucket_id, playlist_id)
            VALUES (?, ?, ?)
            """,
            (link_id, bucket_id, playlist_id),
        )
        conn.commit()

        logger.info(f"Linked bucket {bucket_id} to playlist {playlist_id}")
        return True


def unlink_bucket(bucket_id: str) -> bool:
    """Remove playlist link from bucket.

    Args:
        bucket_id: UUID of the bucket

    Returns:
        True if unlinked (or already unlinked), False if bucket not found
    """
    with get_db_connection() as conn:
        # Verify bucket exists
        cursor = conn.execute(
            "SELECT id FROM buckets WHERE id = ?",
            (bucket_id,),
        )
        if not cursor.fetchone():
            return False

        # Remove link if exists
        conn.execute(
            "DELETE FROM bucket_playlist_links WHERE bucket_id = ?",
            (bucket_id,),
        )
        conn.commit()

        logger.info(f"Unlinked bucket {bucket_id}")
        return True


def get_bucket_link(bucket_id: str) -> int | None:
    """Get linked playlist_id for bucket, or None if unlinked.

    Args:
        bucket_id: UUID of the bucket

    Returns:
        Playlist ID if linked, None if unlinked
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT playlist_id FROM bucket_playlist_links
            WHERE bucket_id = ?
            """,
            (bucket_id,),
        )
        result = cursor.fetchone()
        return result["playlist_id"] if result else None


def sync_track_to_linked_playlist(bucket_id: str, track_id: int) -> bool:
    """Add track to bucket's linked playlist (if linked). Called on bucket assignment.

    Args:
        bucket_id: UUID of the bucket
        track_id: ID of the track to sync

    Returns:
        True if synced (or no link exists), False on error
    """
    with get_db_connection() as conn:
        # Get linked playlist_id
        cursor = conn.execute(
            """
            SELECT playlist_id FROM bucket_playlist_links
            WHERE bucket_id = ?
            """,
            (bucket_id,),
        )
        result = cursor.fetchone()

        if not result:
            # No link, nothing to sync
            return True

        playlist_id = result["playlist_id"]

        # Check if track already in playlist
        existing_cursor = conn.execute(
            """
            SELECT track_id FROM playlist_tracks
            WHERE playlist_id = ? AND track_id = ?
            """,
            (playlist_id, track_id),
        )
        if existing_cursor.fetchone():
            # Already present, nothing to do
            return True

        # Get next position
        position_cursor = conn.execute(
            """
            SELECT COALESCE(MAX(position), -1) + 1 as next_position
            FROM playlist_tracks
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        )
        next_position = position_cursor.fetchone()["next_position"]

        # Add track to playlist
        conn.execute(
            """
            INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (?, ?, ?)
            """,
            (playlist_id, track_id, next_position),
        )
        conn.commit()

        logger.info(
            f"Synced track {track_id} to linked playlist {playlist_id} (bucket {bucket_id})"
        )
        return True


def unsync_track_from_linked_playlist(bucket_id: str, track_id: int) -> bool:
    """Remove track from bucket's linked playlist (if linked). Called on bucket unassignment.

    Args:
        bucket_id: UUID of the bucket
        track_id: ID of the track to unsync

    Returns:
        True if unsynced (or no link exists), False on error
    """
    with get_db_connection() as conn:
        # Get linked playlist_id
        cursor = conn.execute(
            """
            SELECT playlist_id FROM bucket_playlist_links
            WHERE bucket_id = ?
            """,
            (bucket_id,),
        )
        result = cursor.fetchone()

        if not result:
            # No link, nothing to unsync
            return True

        playlist_id = result["playlist_id"]

        # Remove track from playlist
        conn.execute(
            """
            DELETE FROM playlist_tracks
            WHERE playlist_id = ? AND track_id = ?
            """,
            (playlist_id, track_id),
        )
        conn.commit()

        logger.info(
            f"Unsynced track {track_id} from linked playlist {playlist_id} (bucket {bucket_id})"
        )
        return True
