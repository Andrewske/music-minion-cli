"""Pure functional queue manager for rolling window playback system.

This module provides queue initialization, dynamic refilling, shuffle toggling,
and persistence without any global state.
"""

import json
import random
import sqlite3
from typing import Optional, TYPE_CHECKING
from loguru import logger

# Avoid circular import
if TYPE_CHECKING:
    from .routers.player import PlayContext


# Public API Functions


def initialize_queue(
    context: "PlayContext",
    db_conn,
    window_size: int = 100,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None
) -> list[int]:
    """Generate initial queue of track IDs.

    Shuffle ON: Random selection
    Shuffle OFF: Sorted by track_number or sort_spec

    Args:
        context: Playback context (playlist/builder/comparison)
        db_conn: Database connection
        window_size: Max tracks to return
        shuffle: Whether to randomize selection
        sort_spec: Optional dict with 'field' and 'direction' keys

    Returns:
        List of track IDs (max window_size tracks)
    """
    try:
        # Resolve context to all available track IDs
        all_track_ids = _resolve_context_to_track_ids(context, db_conn)

        if not all_track_ids:
            logger.warning(f"No tracks found for context: {context.type}")
            return []

        # If playlist smaller than window, return all
        if len(all_track_ids) <= window_size:
            if shuffle:
                shuffled = all_track_ids.copy()
                random.shuffle(shuffled)
                return shuffled
            else:
                # Already sorted from resolve function
                return all_track_ids

        # Shuffle mode: random selection
        if shuffle:
            return random.sample(all_track_ids, window_size)

        # Sorted mode: take first window_size tracks
        if sort_spec:
            sorted_ids = _get_sorted_tracks_from_playlist(
                context, sort_spec, limit=window_size, offset=0, db_conn=db_conn
            )
            return sorted_ids
        else:
            # Default: sort by track_number
            return all_track_ids[:window_size]

    except Exception as e:
        logger.exception(f"Error initializing queue: {e}")
        return []


def get_next_track(
    context: "PlayContext",
    exclusion_ids: list[int],
    db_conn,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None,
    position_in_sorted: Optional[int] = None
) -> Optional[int]:
    """Pull 1 track from playlist, respecting exclusions.

    Shuffle ON: SELECT ... ORDER BY RANDOM() WHERE id NOT IN (...) LIMIT 1
    Shuffle OFF: Get next in sorted sequence

    Args:
        context: Playback context
        exclusion_ids: Track IDs to exclude
        db_conn: Database connection
        shuffle: Whether to randomize selection
        sort_spec: Optional sort specification
        position_in_sorted: Current position in sorted playlist (for shuffle OFF)

    Returns:
        Single track ID, or None if no tracks available
    """
    try:
        if shuffle:
            # Random selection with exclusions
            return _get_random_track_from_playlist(context, exclusion_ids, db_conn)
        else:
            # Get next in sorted sequence
            if sort_spec:
                offset = position_in_sorted + 1 if position_in_sorted is not None else 0
                sorted_ids = _get_sorted_tracks_from_playlist(
                    context, sort_spec, limit=1, offset=offset, db_conn=db_conn
                )
                return sorted_ids[0] if sorted_ids else None
            else:
                # Default sequential playback by track_number
                all_track_ids = _resolve_context_to_track_ids(context, db_conn)
                # Filter out exclusions
                available = [tid for tid in all_track_ids if tid not in exclusion_ids]
                return available[0] if available else None

    except Exception as e:
        logger.exception(f"Error fetching next track: {e}")
        return None


def rebuild_queue(
    context: "PlayContext",
    current_track_id: int,
    queue: list[int],
    queue_index: int,
    db_conn,
    shuffle: bool,
    sort_spec: Optional[dict] = None
) -> list[int]:
    """Rebuild queue preserving current track and history.

    Used when toggling shuffle or changing sort.
    Keeps tracks[0:queue_index+1], rebuilds tracks[queue_index+1:]

    Args:
        context: Playback context
        current_track_id: Currently playing track
        queue: Current queue of track IDs
        queue_index: Current position in queue
        db_conn: Database connection
        shuffle: New shuffle state
        sort_spec: New sort specification

    Returns:
        New complete queue (history + current + new future tracks)
    """
    try:
        # Preserve history: tracks already played + current track
        preserved = queue[0:queue_index + 1]
        logger.info(f"Preserving {len(preserved)} tracks (history + current)")

        # Build exclusion list from preserved tracks
        exclusion_ids = preserved.copy()

        # Generate new future tracks (~99 tracks to reach window_size=100)
        new_future_size = 100 - len(preserved)
        if new_future_size <= 0:
            # Queue is already full with history
            return preserved

        # Use initialize_queue logic but with exclusions
        all_track_ids = _resolve_context_to_track_ids(context, db_conn)
        available_ids = [tid for tid in all_track_ids if tid not in exclusion_ids]

        if not available_ids:
            logger.warning("No available tracks for queue rebuild")
            return preserved

        new_tracks = []
        if shuffle:
            # Random selection
            sample_size = min(new_future_size, len(available_ids))
            new_tracks = random.sample(available_ids, sample_size)
        else:
            # Sorted selection
            if sort_spec:
                # Get sorted tracks, filter exclusions, take new_future_size
                sorted_ids = _get_sorted_tracks_from_playlist(
                    context, sort_spec, limit=len(all_track_ids), offset=0, db_conn=db_conn
                )
                filtered = [tid for tid in sorted_ids if tid not in exclusion_ids]
                new_tracks = filtered[:new_future_size]
            else:
                # Sequential by track_number
                new_tracks = available_ids[:new_future_size]

        # Concatenate preserved + new tracks
        rebuilt = preserved + new_tracks
        logger.info(f"Rebuilt queue: {len(preserved)} preserved + {len(new_tracks)} new = {len(rebuilt)} total")
        return rebuilt

    except Exception as e:
        logger.exception(f"Error rebuilding queue: {e}")
        # Return preserved tracks on error
        return queue[0:queue_index + 1]


def save_queue_state(
    context: "PlayContext",
    queue_ids: list[int],
    queue_index: int,
    shuffle: bool,
    sort_spec: Optional[dict],
    db_conn,
    position_in_playlist: Optional[int] = None
) -> None:
    """Persist queue state to database.

    Uses INSERT OR REPLACE for singleton pattern (id=1).

    Args:
        context: Playback context
        queue_ids: List of track IDs in queue
        queue_index: Current position in queue
        shuffle: Shuffle enabled state
        sort_spec: Optional sort specification dict
        db_conn: Database connection
        position_in_playlist: Position in sorted playlist (for sorted mode tracking)
    """
    try:
        # Serialize data
        queue_json = json.dumps(queue_ids)
        sort_field = sort_spec.get("field") if sort_spec else None
        sort_direction = sort_spec.get("direction") if sort_spec else None

        # Use provided position_in_playlist, or default to None for shuffle mode
        if position_in_playlist is None:
            position_in_playlist = queue_index if not shuffle else None

        # Insert or replace singleton row
        db_conn.execute(
            """
            INSERT OR REPLACE INTO player_queue_state (
                id, context_type, context_id, shuffle_enabled,
                sort_field, sort_direction, queue_track_ids,
                queue_index, position_in_playlist, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                context.type,
                _get_context_id(context),
                shuffle,
                sort_field,
                sort_direction,
                queue_json,
                queue_index,
                position_in_playlist
            )
        )
        db_conn.commit()
        logger.info(f"Saved queue state: {len(queue_ids)} tracks, index={queue_index}, shuffle={shuffle}")

    except sqlite3.Error as e:
        logger.exception("Failed to save queue state")
        # Don't raise - persistence failing shouldn't crash playback


def load_queue_state(db_conn) -> Optional[dict]:
    """Restore queue state from database.

    Returns:
        dict with keys: queue_ids, queue_index, shuffle_enabled,
        sort_spec, context, position_in_playlist, or None if no saved state
    """
    try:
        cursor = db_conn.execute(
            """
            SELECT context_type, context_id, shuffle_enabled,
                   sort_field, sort_direction, queue_track_ids,
                   queue_index, position_in_playlist
            FROM player_queue_state
            WHERE id = 1
            """
        )
        row = cursor.fetchone()

        if not row:
            logger.info("No saved queue state found")
            return None

        # Deserialize queue IDs
        queue_ids = json.loads(row["queue_track_ids"])

        # Reconstruct sort_spec
        sort_spec = None
        if row["sort_field"]:
            sort_spec = {
                "field": row["sort_field"],
                "direction": row["sort_direction"] or "asc"
            }

        # Reconstruct PlayContext
        context = _reconstruct_play_context(
            row["context_type"],
            row["context_id"],
            row["shuffle_enabled"]
        )

        state = {
            "queue_ids": queue_ids,
            "queue_index": row["queue_index"],
            "shuffle_enabled": bool(row["shuffle_enabled"]),
            "sort_spec": sort_spec,
            "context": context,
            "position_in_playlist": row["position_in_playlist"]
        }

        logger.info(f"Loaded queue state: {len(queue_ids)} tracks, index={row['queue_index']}")
        return state

    except sqlite3.Error as e:
        logger.exception("Error loading queue state")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.exception("Error deserializing queue state")
        return None


# Internal Helper Functions


def _get_random_track_from_playlist(
    context: "PlayContext",
    exclusion_ids: list[int],
    db_conn
) -> Optional[int]:
    """SQL: ORDER BY RANDOM() with exclusions.

    Args:
        context: Playback context
        exclusion_ids: Track IDs to exclude
        db_conn: Database connection

    Returns:
        Random track ID, or None if no tracks available
    """
    try:
        # Build query based on context type
        if context.type == "playlist" and context.playlist_id:
            # Check if smart playlist
            cursor = db_conn.execute(
                "SELECT type FROM playlists WHERE id = ?",
                (context.playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            if row["type"] == "smart":
                # Smart playlist: get all matching tracks, then filter/randomize
                from music_minion.domain.playlists.filters import evaluate_filters
                tracks = evaluate_filters(context.playlist_id)
                track_ids = [t["id"] for t in tracks]
                available = [tid for tid in track_ids if tid not in exclusion_ids]
                return random.choice(available) if available else None
            else:
                # Manual playlist
                placeholders = ",".join("?" * len(exclusion_ids))
                query = f"""
                    SELECT track_id FROM playlist_tracks
                    WHERE playlist_id = ?
                    AND track_id NOT IN ({placeholders})
                    ORDER BY RANDOM()
                    LIMIT 1
                """ if exclusion_ids else """
                    SELECT track_id FROM playlist_tracks
                    WHERE playlist_id = ?
                    ORDER BY RANDOM()
                    LIMIT 1
                """
                params = [context.playlist_id] + exclusion_ids if exclusion_ids else [context.playlist_id]
                cursor = db_conn.execute(query, params)

        elif context.type == "builder" and context.builder_id:
            # Builder context
            placeholders = ",".join("?" * len(exclusion_ids))
            query = f"""
                SELECT track_id FROM playlist_tracks
                WHERE playlist_id = ?
                AND track_id NOT IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT 1
            """ if exclusion_ids else """
                SELECT track_id FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY RANDOM()
                LIMIT 1
            """
            params = [context.builder_id] + exclusion_ids if exclusion_ids else [context.builder_id]
            cursor = db_conn.execute(query, params)

        elif context.type == "comparison" and context.track_ids:
            # Comparison context
            available = [tid for tid in context.track_ids if tid not in exclusion_ids]
            return random.choice(available) if available else None

        else:
            logger.warning(f"Unsupported context type for random track: {context.type}")
            return None

        row = cursor.fetchone()
        return row["track_id"] if row else None

    except Exception as e:
        logger.exception(f"Error getting random track: {e}")
        return None


def _get_sorted_tracks_from_playlist(
    context: "PlayContext",
    sort_spec: dict,
    limit: int,
    offset: int,
    db_conn
) -> list[int]:
    """Apply sort spec (field + direction), return track IDs.

    Args:
        context: Playback context
        sort_spec: Dict with 'field' and 'direction' keys
        limit: Max tracks to return
        offset: Number of tracks to skip
        db_conn: Database connection

    Returns:
        List of track IDs
    """
    try:
        sort_field = sort_spec.get("field", "track_number")
        sort_direction = sort_spec.get("direction", "asc").upper()

        # Map sort field to SQL column with COALESCE for NULL handling
        field_mapping = {
            "title": "COALESCE(tracks.title, '')",
            "artist": "COALESCE(tracks.artist, '')",
            "bpm": "COALESCE(tracks.bpm, 120)",
            "year": "COALESCE(tracks.year, 0)",
            "elo_rating": "COALESCE(track_ratings.elo_rating, 1500)",
            "track_number": "tracks.track_number"
        }

        sql_field = field_mapping.get(sort_field, "tracks.track_number")

        # Build query based on context type
        if context.type == "playlist" and context.playlist_id:
            # Check if smart playlist
            cursor = db_conn.execute(
                "SELECT type FROM playlists WHERE id = ?",
                (context.playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                return []

            if row["type"] == "smart":
                # Smart playlist: evaluate filters then sort in Python
                from music_minion.domain.playlists.filters import evaluate_filters
                tracks = evaluate_filters(context.playlist_id)
                track_ids = [t["id"] for t in tracks]

                # Fetch sort field values for sorting
                if not track_ids:
                    return []

                placeholders = ",".join("?" * len(track_ids))
                cursor = db_conn.execute(
                    f"""
                    SELECT tracks.id, {sql_field} as sort_value
                    FROM tracks
                    LEFT JOIN track_ratings ON tracks.id = track_ratings.track_id
                    WHERE tracks.id IN ({placeholders})
                    """,
                    track_ids
                )
                rows = cursor.fetchall()

                # Sort in Python
                sorted_rows = sorted(
                    rows,
                    key=lambda r: r["sort_value"],
                    reverse=(sort_direction == "DESC")
                )
                sorted_ids = [r["id"] for r in sorted_rows]
                return sorted_ids[offset:offset + limit]

            else:
                # Manual playlist
                query = f"""
                    SELECT pt.track_id
                    FROM playlist_tracks pt
                    JOIN tracks ON pt.track_id = tracks.id
                    LEFT JOIN track_ratings ON tracks.id = track_ratings.track_id
                    WHERE pt.playlist_id = ?
                    ORDER BY {sql_field} {sort_direction}
                    LIMIT ? OFFSET ?
                """
                cursor = db_conn.execute(query, (context.playlist_id, limit, offset))

        elif context.type == "builder" and context.builder_id:
            # Builder context
            query = f"""
                SELECT pt.track_id
                FROM playlist_tracks pt
                JOIN tracks ON pt.track_id = tracks.id
                LEFT JOIN track_ratings ON tracks.id = track_ratings.track_id
                WHERE pt.playlist_id = ?
                ORDER BY {sql_field} {sort_direction}
                LIMIT ? OFFSET ?
            """
            cursor = db_conn.execute(query, (context.builder_id, limit, offset))

        elif context.type == "comparison" and context.track_ids:
            # Comparison context - fetch and sort in Python
            if not context.track_ids:
                return []

            placeholders = ",".join("?" * len(context.track_ids))
            cursor = db_conn.execute(
                f"""
                SELECT tracks.id, {sql_field} as sort_value
                FROM tracks
                LEFT JOIN track_ratings ON tracks.id = track_ratings.track_id
                WHERE tracks.id IN ({placeholders})
                """,
                context.track_ids
            )
            rows = cursor.fetchall()

            # Sort in Python
            sorted_rows = sorted(
                rows,
                key=lambda r: r["sort_value"],
                reverse=(sort_direction == "DESC")
            )
            sorted_ids = [r["id"] for r in sorted_rows]
            return sorted_ids[offset:offset + limit]

        else:
            logger.warning(f"Unsupported context type for sorted tracks: {context.type}")
            return []

        # Fetch results for SQL-based queries
        rows = cursor.fetchall()
        return [row["track_id"] for row in rows]

    except Exception as e:
        logger.exception(f"Error getting sorted tracks: {e}")
        return []


def _build_exclusion_list(queue: list[int], queue_index: int) -> list[int]:
    """Extract IDs from queue[queue_index:].

    Args:
        queue: Current queue of track IDs
        queue_index: Current position in queue

    Returns:
        List of track IDs to exclude (remaining tracks in queue)
    """
    return queue[queue_index:]


def _resolve_context_to_track_ids(
    context: "PlayContext",
    db_conn
) -> list[int]:
    """Handle playlist/builder/smart playlist context.

    For smart playlists: Evaluate filters dynamically.
    For manual playlists: Query playlist_tracks table.
    For builder: Query current builder tracks.

    Args:
        context: Playback context
        db_conn: Database connection

    Returns:
        List of all track IDs in context (not limited)
    """
    try:
        if context.type == "track":
            # Single track playback
            return [context.track_ids[0]] if context.track_ids else []

        elif context.type == "playlist" and context.playlist_id:
            # Check if it's a smart playlist
            cursor = db_conn.execute(
                "SELECT type FROM playlists WHERE id = ?",
                (context.playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Playlist {context.playlist_id} not found")
                return []

            if row["type"] == "smart":
                # Smart playlist - evaluate filters dynamically
                from music_minion.domain.playlists.filters import evaluate_filters
                tracks = evaluate_filters(context.playlist_id)
                return [t["id"] for t in tracks]
            else:
                # Manual playlist - query from playlist_tracks table
                cursor = db_conn.execute(
                    """
                    SELECT track_id FROM playlist_tracks
                    WHERE playlist_id = ?
                    ORDER BY position
                    """,
                    (context.playlist_id,)
                )
                return [row["track_id"] for row in cursor.fetchall()]

        elif context.type == "builder" and context.builder_id:
            # Builder context is playlist in builder mode
            cursor = db_conn.execute(
                """
                SELECT track_id FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
                """,
                (context.builder_id,)
            )
            return [row["track_id"] for row in cursor.fetchall()]

        elif context.type == "comparison" and context.track_ids:
            return context.track_ids

        elif context.type == "search":
            # TODO: Implement search query execution
            logger.warning("Search context not yet implemented")
            return []

        else:
            logger.warning(f"Unsupported context type: {context.type}")
            return []

    except Exception as e:
        logger.exception(f"Error resolving context to track IDs: {e}")
        return []


def _get_context_id(context: "PlayContext") -> Optional[int]:
    """Extract context ID based on context type.

    Args:
        context: Playback context

    Returns:
        Context ID (playlist_id/builder_id) or None
    """
    if context.type == "playlist":
        return context.playlist_id
    elif context.type == "builder":
        return context.builder_id
    else:
        return None


def _reconstruct_play_context(
    context_type: str,
    context_id: Optional[int],
    shuffle: bool
) -> "PlayContext":
    """Reconstruct PlayContext from database fields.

    Args:
        context_type: Type of context (playlist/builder/comparison)
        context_id: ID of playlist/builder
        shuffle: Shuffle enabled state

    Returns:
        PlayContext instance
    """
    # Import at runtime to avoid circular import
    from .routers.player import PlayContext

    if context_type == "playlist":
        return PlayContext(
            type="playlist",
            playlist_id=context_id,
            shuffle=shuffle
        )
    elif context_type == "builder":
        return PlayContext(
            type="builder",
            builder_id=context_id,
            shuffle=shuffle
        )
    elif context_type == "comparison":
        # Note: track_ids not persisted, will need to be refreshed
        return PlayContext(
            type="comparison",
            track_ids=[],
            shuffle=shuffle
        )
    else:
        # Default to playlist
        return PlayContext(
            type="playlist",
            shuffle=shuffle
        )
