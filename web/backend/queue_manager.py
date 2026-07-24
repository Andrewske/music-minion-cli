"""Pure functional queue manager for rolling window playback system.

This module provides queue initialization, dynamic refilling, shuffle toggling,
and persistence without any global state.
"""

import json
import random
import sqlite3
from typing import Optional
from loguru import logger

from .schemas import PlayContext


# Rolling-window sizing (shared by player.py — do not re-hardcode these numbers).
WINDOW_SIZE = 100  # target number of tracks materialized in the queue window
REFILL_THRESHOLD = 50  # refill back up to WINDOW_SIZE when fewer than this remain ahead


# ---------------------------------------------------------------------------
# Resolved-context cache
#
# _resolve_context_to_track_ids() is expensive for smart playlists (runs
# evaluate_filters over the whole library) and was previously re-run on every
# skip (once for the refill pick, again for total_size in sorted mode). Cache
# the resolved track-id list for the single active context.
#
# Write-through refresh: initialize_queue() and rebuild_queue() always resolve
# fresh and overwrite the cache, so /play, toggle-shuffle, set-sort and
# organizer loop restarts all repopulate it. A context-key mismatch (context
# change) also triggers a fresh resolve. invalidate_context_cache() is called
# by player.py when a track is pruned as dead or an organizer pool changes.
# ---------------------------------------------------------------------------
_context_cache_key: Optional[tuple] = None
_context_cache_ids: list[int] = []


def _context_cache_signature(context: PlayContext) -> tuple:
    """Hashable identity of a playback context for cache keying.

    getattr defaults keep this tolerant of test doubles that omit fields.
    """
    track_ids = getattr(context, "track_ids", None)
    return (
        context.type,
        getattr(context, "playlist_id", None),
        getattr(context, "builder_id", None),
        getattr(context, "session_id", None),
        getattr(context, "bucket_id", None),
        tuple(track_ids) if track_ids else None,
    )


def invalidate_context_cache() -> None:
    """Drop the cached resolved context (next access re-resolves)."""
    global _context_cache_key, _context_cache_ids
    _context_cache_key = None
    _context_cache_ids = []


def _refresh_context_ids(context: PlayContext, db_conn) -> list[int]:
    """Resolve context fresh and overwrite the cache (write-through)."""
    global _context_cache_key, _context_cache_ids
    ids = _resolve_context_to_track_ids(context, db_conn)
    _context_cache_key = _context_cache_signature(context)
    _context_cache_ids = ids
    return ids


def _get_context_ids_cached(context: PlayContext, db_conn) -> list[int]:
    """Return resolved track IDs for context, using the cache when the context matches."""
    if _context_cache_key == _context_cache_signature(context):
        return _context_cache_ids
    return _refresh_context_ids(context, db_conn)


# Public API Functions


def initialize_queue(
    context: PlayContext,
    db_conn,
    window_size: int = WINDOW_SIZE,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None,
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
        # Resolve context to all available track IDs (refreshes the context cache)
        all_track_ids = _refresh_context_ids(context, db_conn)

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
    context: PlayContext,
    exclusion_ids: list[int],
    db_conn,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None,
    position_in_sorted: Optional[int] = None,
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
            # Get next in sorted sequence. position_in_sorted IS the offset of
            # the next row to read (see get_next_tracks invariant) — no +1.
            if sort_spec:
                offset = position_in_sorted if position_in_sorted is not None else 0
                sorted_ids = _get_sorted_tracks_from_playlist(
                    context, sort_spec, limit=1, offset=offset, db_conn=db_conn
                )
                return sorted_ids[0] if sorted_ids else None
            else:
                # Default sequential playback by track_number
                all_track_ids = _resolve_context_to_track_ids(context, db_conn)
                # Filter out exclusions
                available = [tid for tid in all_track_ids if tid not in exclusion_ids]

                # NEW: Loop restart for organizer context
                if not available and all_track_ids and context.type == "organizer":
                    # All tracks excluded - return None to signal queue rebuild needed
                    # Caller should detect None and call rebuild_queue() to clear exclusions
                    logger.info("Organizer loop exhausted - triggering queue rebuild")
                    return None

                return available[0] if available else None

    except Exception as e:
        logger.exception(f"Error fetching next track: {e}")
        return None


def get_next_tracks(
    context: PlayContext,
    count: int,
    exclusion_ids: list[int],
    db_conn,
    shuffle: bool = True,
    sort_spec: Optional[dict] = None,
    position_in_sorted: Optional[int] = None,
) -> tuple[list[int], Optional[int]]:
    """Pull up to `count` tracks from the context in ONE query — batch refill.

    Replaces per-skip get_next_track() calls: player.py calls this once when
    the window drops below REFILL_THRESHOLD and tops it back up to WINDOW_SIZE.

    SORTED-MODE INVARIANT (position_in_playlist / position_in_sorted):
        position = number of rows of the context's sorted order already
        materialized into the queue window, i.e. the exact SQL OFFSET at which
        the NEXT refill must read. It advances by the number of rows FETCHED
        (not by a fixed window) and wraps modulo the context's total size so
        the playlist loops.

        The old code violated this twice: get_next_track read at OFFSET
        position+1 (skipping one row), and player.py then advanced position by
        +100 per single-track refill — so after the first refill each
        subsequent refill jumped 100 rows ahead, skipping ~99 of every 100
        tracks in sorted mode.

    Shuffle mode:
        Manual playlist/builder: single ORDER BY RANDOM() LIMIT count with
        NOT IN exclusions and unavailable_at filtering.
        Smart playlist / comparison / organizer: random.sample over the cached
        resolved ids (no evaluate_filters per pick).

    Args:
        context: Playback context
        count: Max tracks to return
        exclusion_ids: Track IDs to exclude (upcoming queue window)
        db_conn: Database connection
        shuffle: Whether to randomize selection
        sort_spec: Optional sort specification
        position_in_sorted: Sorted-order offset per the invariant above

    Returns:
        (track_ids, new_position_in_sorted). new_position is None in shuffle
        mode (caller keeps its current value). In sorted mode it advances by
        rows fetched even if all fetched rows were excluded, so the cursor
        never stalls.
    """
    if count <= 0:
        return [], None if shuffle else position_in_sorted

    try:
        if shuffle:
            return _get_random_tracks_from_context(
                context, exclusion_ids, count, db_conn
            ), None

        # Sorted mode
        all_track_ids = _get_context_ids_cached(context, db_conn)
        total = len(all_track_ids)
        if total == 0:
            return [], position_in_sorted

        position = (position_in_sorted or 0) % total
        if sort_spec:
            fetched = _get_sorted_tracks_from_playlist(
                context, sort_spec, limit=count, offset=position, db_conn=db_conn
            )
        else:
            # Default order: context position order (same order initialize_queue used)
            fetched = all_track_ids[position : position + count]

        new_position = (position + len(fetched)) % total if fetched else position
        excluded = set(exclusion_ids)
        return [tid for tid in fetched if tid not in excluded], new_position

    except Exception:
        logger.exception("Error fetching next tracks batch")
        return [], None if shuffle else position_in_sorted


def rebuild_queue(
    context: PlayContext,
    current_track_id: int,
    queue: list[int],
    queue_index: int,
    db_conn,
    shuffle: bool,
    sort_spec: Optional[dict] = None,
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
        # Preserve history: tracks already played + current track, minus any that went
        # dead upstream mid-session (else a dead track survives every rebuild + replays).
        dead = get_unavailable_ids(queue[0 : queue_index + 1], db_conn)
        preserved = [tid for tid in queue[0 : queue_index + 1] if tid not in dead]
        logger.info(f"Preserving {len(preserved)} tracks (history + current)")

        # Build exclusion list from preserved tracks
        exclusion_ids = preserved.copy()

        # Generate new future tracks to reach WINDOW_SIZE
        new_future_size = WINDOW_SIZE - len(preserved)
        if new_future_size <= 0:
            # Queue is already full with history
            return preserved

        # Use initialize_queue logic but with exclusions (refreshes context cache)
        all_track_ids = _refresh_context_ids(context, db_conn)
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
                    context,
                    sort_spec,
                    limit=len(all_track_ids),
                    offset=0,
                    db_conn=db_conn,
                )
                filtered = [tid for tid in sorted_ids if tid not in exclusion_ids]
                new_tracks = filtered[:new_future_size]
            else:
                # Sequential by track_number
                new_tracks = available_ids[:new_future_size]

        # Concatenate preserved + new tracks
        rebuilt = preserved + new_tracks
        logger.info(
            f"Rebuilt queue: {len(preserved)} preserved + {len(new_tracks)} new = {len(rebuilt)} total"
        )
        return rebuilt

    except Exception as e:
        logger.exception(f"Error rebuilding queue: {e}")
        # Return preserved tracks on error
        return queue[0 : queue_index + 1]


def save_queue_state(
    context: PlayContext,
    queue_ids: list[int],
    queue_index: int,
    shuffle: bool,
    sort_spec: Optional[dict],
    db_conn,
    position_in_playlist: Optional[int] = None,
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
                queue_index, position_in_playlist, context_session_id, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                context.type,
                _get_context_id(context),
                shuffle,
                sort_field,
                sort_direction,
                queue_json,
                queue_index,
                position_in_playlist,
                context.session_id if context.type == "organizer" else None,
            ),
        )
        db_conn.commit()
        logger.info(
            f"Saved queue state: {len(queue_ids)} tracks, index={queue_index}, shuffle={shuffle}"
        )

    except sqlite3.Error:
        logger.exception("Failed to save queue state")
        # Don't raise - persistence failing shouldn't crash playback


def update_queue_position(
    queue_index: int, position_in_playlist: Optional[int], db_conn
) -> None:
    """Persist only the queue cursor — cheap per-skip write.

    save_queue_state() reserializes the entire queue-ID JSON; doing that on
    every skip is the bulk of per-skip DB churn. Skips that don't change the
    queue contents only need the two cursor columns updated.
    """
    try:
        db_conn.execute(
            """
            UPDATE player_queue_state
            SET queue_index = ?, position_in_playlist = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (queue_index, position_in_playlist),
        )
        db_conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update queue position")
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
                   queue_index, position_in_playlist, context_session_id
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
                "direction": row["sort_direction"] or "asc",
            }

        # Reconstruct PlayContext
        context = _reconstruct_play_context(
            row["context_type"],
            row["context_id"],
            row["shuffle_enabled"],
            row["context_session_id"],
        )

        state = {
            "queue_ids": queue_ids,
            "queue_index": row["queue_index"],
            "shuffle_enabled": bool(row["shuffle_enabled"]),
            "sort_spec": sort_spec,
            "context": context,
            "position_in_playlist": row["position_in_playlist"],
        }

        logger.info(
            f"Loaded queue state: {len(queue_ids)} tracks, index={row['queue_index']}"
        )
        return state

    except sqlite3.Error:
        logger.exception("Error loading queue state")
        return None
    except (json.JSONDecodeError, KeyError):
        logger.exception("Error deserializing queue state")
        return None


# Internal Helper Functions


def _build_random_query_with_exclusions(
    playlist_id: int, exclusion_ids: list[int], limit: int = 1
):
    """Build SQL query for random track selection with exclusions.

    Args:
        playlist_id: Playlist or builder ID
        exclusion_ids: Track IDs to exclude
        limit: Max tracks to select

    Returns:
        Tuple of (query_string, params_list)
    """
    if exclusion_ids:
        placeholders = ",".join("?" * len(exclusion_ids))
        query = f"""
            SELECT pt.track_id FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ?
            AND t.unavailable_at IS NULL
            AND pt.track_id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
        """
        params = [playlist_id] + exclusion_ids + [limit]
    else:
        query = """
            SELECT pt.track_id FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ?
            AND t.unavailable_at IS NULL
            ORDER BY RANDOM()
            LIMIT ?
        """
        params = [playlist_id, limit]
    return query, params


def _get_random_from_manual_playlist(
    playlist_id: int, exclusion_ids: list[int], db_conn, limit: int = 1
) -> list[int]:
    """Get random tracks from manual playlist in a single SQL query.

    Args:
        playlist_id: Playlist ID
        exclusion_ids: Track IDs to exclude
        db_conn: Database connection
        limit: Max tracks to select

    Returns:
        Up to `limit` random track IDs (may be empty)
    """
    query, params = _build_random_query_with_exclusions(
        playlist_id, exclusion_ids, limit
    )
    cursor = db_conn.execute(query, params)
    return [row["track_id"] for row in cursor.fetchall()]


def _sample_excluding(
    track_ids: list[int], exclusion_ids: list[int], count: int
) -> list[int]:
    """Random sample of up to `count` ids from track_ids minus exclusions."""
    excluded = set(exclusion_ids)
    available = [tid for tid in track_ids if tid not in excluded]
    if not available:
        return []
    return random.sample(available, min(count, len(available)))


def _get_random_tracks_from_context(
    context: PlayContext, exclusion_ids: list[int], count: int, db_conn
) -> list[int]:
    """Random selection of up to `count` tracks from a context, one query max.

    Manual playlist/builder: single ORDER BY RANDOM() LIMIT count SQL query
    (unavailable_at filtered in SQL). Smart playlist / comparison / organizer:
    random.sample over the cached resolved ids (already unavailable-filtered
    by _resolve_context_to_track_ids) — no evaluate_filters per pick.

    Returns:
        Up to `count` random track IDs (empty when exhausted/unsupported)
    """
    try:
        if context.type == "playlist" and context.playlist_id:
            cursor = db_conn.execute(
                "SELECT type FROM playlists WHERE id = ?", (context.playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                return []

            if row["type"] == "smart":
                return _sample_excluding(
                    _get_context_ids_cached(context, db_conn), exclusion_ids, count
                )
            return _get_random_from_manual_playlist(
                context.playlist_id, exclusion_ids, db_conn, limit=count
            )

        elif context.type == "builder" and context.builder_id:
            return _get_random_from_manual_playlist(
                context.builder_id, exclusion_ids, db_conn, limit=count
            )

        elif context.type == "comparison" and context.track_ids:
            return _sample_excluding(context.track_ids, exclusion_ids, count)

        elif context.type == "organizer" and context.session_id:
            # Organizer pool (unassigned or bucket tracks) resolved+filtered by
            # _resolve_context_to_track_ids; cache invalidated on pool changes.
            return _sample_excluding(
                _get_context_ids_cached(context, db_conn), exclusion_ids, count
            )

        else:
            logger.warning(
                f"Unsupported context type for random tracks: {context.type}"
            )
            return []

    except Exception:
        logger.exception("Error getting random tracks")
        return []


def _get_random_track_from_playlist(
    context: PlayContext, exclusion_ids: list[int], db_conn
) -> Optional[int]:
    """Single random track from context, respecting exclusions.

    Returns:
        Random track ID, or None if no tracks available
    """
    ids = _get_random_tracks_from_context(context, exclusion_ids, 1, db_conn)
    return ids[0] if ids else None


def _get_sorted_tracks_from_playlist(
    context: PlayContext, sort_spec: dict, limit: int, offset: int, db_conn
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
            "track_number": "tracks.track_number",
        }

        sql_field = field_mapping.get(sort_field, "tracks.track_number")

        # Build query based on context type
        if context.type == "playlist" and context.playlist_id:
            # Check if smart playlist
            cursor = db_conn.execute(
                "SELECT type FROM playlists WHERE id = ?", (context.playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                return []

            if row["type"] == "smart":
                # Smart playlist: sort the cached resolved ids in Python
                # (avoids re-running evaluate_filters; ids already
                # unavailable-filtered so offsets match the resolved total)
                track_ids = _get_context_ids_cached(context, db_conn)

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
                    track_ids,
                )
                rows = cursor.fetchall()

                # Sort in Python
                sorted_rows = sorted(
                    rows,
                    key=lambda r: r["sort_value"],
                    reverse=(sort_direction == "DESC"),
                )
                sorted_ids = [r["id"] for r in sorted_rows]
                return sorted_ids[offset : offset + limit]

            else:
                # Manual playlist (unavailable_at filtered so LIMIT/OFFSET
                # positions line up with _resolve_context_to_track_ids counts)
                query = f"""
                    SELECT pt.track_id
                    FROM playlist_tracks pt
                    JOIN tracks ON pt.track_id = tracks.id
                    LEFT JOIN track_ratings ON tracks.id = track_ratings.track_id
                    WHERE pt.playlist_id = ?
                    AND tracks.unavailable_at IS NULL
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
                AND tracks.unavailable_at IS NULL
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
                context.track_ids,
            )
            rows = cursor.fetchall()

            # Sort in Python
            sorted_rows = sorted(
                rows, key=lambda r: r["sort_value"], reverse=(sort_direction == "DESC")
            )
            sorted_ids = [r["id"] for r in sorted_rows]
            return sorted_ids[offset : offset + limit]

        else:
            logger.warning(
                f"Unsupported context type for sorted tracks: {context.type}"
            )
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


def get_unavailable_ids(track_ids: list[int], db_conn) -> set[int]:
    """Return the subset of track_ids marked tracks.unavailable_at (dead upstream).

    Empty set if list empty or none dead.
    """
    if not track_ids:
        return set()
    placeholders = ",".join("?" * len(track_ids))
    cursor = db_conn.execute(
        f"SELECT id FROM tracks WHERE id IN ({placeholders}) AND unavailable_at IS NOT NULL",
        track_ids,
    )
    return {row["id"] for row in cursor.fetchall()}


def _filter_unavailable(track_ids: list[int], db_conn) -> list[int]:
    """Drop tracks with tracks.unavailable_at set (dead upstream sources).

    Preserves order. No-op if list empty.
    """
    dead = get_unavailable_ids(track_ids, db_conn)
    if not dead:
        return track_ids
    logger.info(f"Excluding {len(dead)} unavailable tracks from queue")
    return [tid for tid in track_ids if tid not in dead]


def _resolve_context_to_track_ids(context: PlayContext, db_conn) -> list[int]:
    """Handle playlist/builder/smart playlist context.

    For smart playlists: Evaluate filters dynamically.
    For manual playlists: Query playlist_tracks table.
    For builder: Query current builder tracks.

    Args:
        context: Playback context
        db_conn: Database connection

    Returns:
        List of all track IDs in context (not limited).
        Tracks marked unavailable_at are excluded for non-single-track contexts.
    """
    try:
        if context.type == "track":
            # Single track playback - honor explicit user request, don't filter
            return [context.track_ids[0]] if context.track_ids else []

        elif context.type == "playlist" and context.playlist_id:
            # Check if it's a smart playlist
            cursor = db_conn.execute(
                "SELECT type FROM playlists WHERE id = ?", (context.playlist_id,)
            )
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Playlist {context.playlist_id} not found")
                return []

            if row["type"] == "smart":
                # Smart playlist - evaluate filters dynamically
                from music_minion.domain.playlists.filters import evaluate_filters

                tracks = evaluate_filters(context.playlist_id)
                return _filter_unavailable([t["id"] for t in tracks], db_conn)
            else:
                # Manual playlist - query from playlist_tracks table
                cursor = db_conn.execute(
                    """
                    SELECT track_id FROM playlist_tracks
                    WHERE playlist_id = ?
                    ORDER BY position
                    """,
                    (context.playlist_id,),
                )
                return _filter_unavailable(
                    [row["track_id"] for row in cursor.fetchall()], db_conn
                )

        elif context.type == "builder" and context.builder_id:
            # Builder context is playlist in builder mode
            cursor = db_conn.execute(
                """
                SELECT track_id FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
                """,
                (context.builder_id,),
            )
            return _filter_unavailable(
                [row["track_id"] for row in cursor.fetchall()], db_conn
            )

        elif context.type in ("comparison", "feed") and context.track_ids:
            return context.track_ids

        elif context.type == "organizer" and context.session_id:
            # Organizer context - return bucket tracks or unassigned tracks
            from .queries.buckets import get_session_with_data

            session = get_session_with_data(context.session_id)
            if session and session["status"] == "active":
                if context.bucket_id:
                    bucket = next(
                        (b for b in session["buckets"] if b["id"] == context.bucket_id),
                        None,
                    )
                    if bucket:
                        return _filter_unavailable(bucket["track_ids"], db_conn)
                return _filter_unavailable(session["unassigned_track_ids"], db_conn)
            else:
                logger.warning(
                    f"Organizer session {context.session_id} not found or inactive"
                )
                return []

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
    shuffle: bool,
    context_session_id: Optional[str] = None,
) -> PlayContext:
    """Reconstruct PlayContext from database fields.

    Args:
        context_type: Type of context (playlist/builder/comparison/organizer)
        context_id: ID of playlist/builder
        shuffle: Shuffle enabled state
        context_session_id: Session ID for organizer context

    Returns:
        PlayContext instance
    """
    if context_type == "playlist":
        return PlayContext(type="playlist", playlist_id=context_id, shuffle=shuffle)
    elif context_type == "builder":
        return PlayContext(type="builder", builder_id=context_id, shuffle=shuffle)
    elif context_type == "comparison":
        # Note: track_ids not persisted, will need to be refreshed
        return PlayContext(type="comparison", track_ids=[], shuffle=shuffle)
    elif context_type == "organizer":
        # Reconstruct organizer context with session_id from database
        # (requires context_session_id column added in task 00)
        from .queries.buckets import get_session_with_data

        # Validate session still exists and is active
        if context_session_id:
            session = get_session_with_data(context_session_id)
            if session and session["status"] == "active":
                return PlayContext(
                    type="organizer",
                    playlist_id=context_id,
                    session_id=context_session_id,
                    shuffle=shuffle,
                )
            else:
                logger.warning(
                    f"Organizer session {context_session_id} no longer active, falling back to playlist"
                )

        # Fallback to regular playlist if session invalid/missing
        return PlayContext(type="playlist", playlist_id=context_id, shuffle=shuffle)
    else:
        # Default to playlist
        return PlayContext(type="playlist", shuffle=shuffle)
