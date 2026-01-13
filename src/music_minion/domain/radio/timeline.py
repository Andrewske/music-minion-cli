"""
Deterministic timeline calculation for radio.

The core algorithm that makes "tune in mid-stream" work by calculating
exactly what track and position should be playing at any given time.
"""

import hashlib
import random
from datetime import date, datetime, time, timedelta
from typing import Optional

from loguru import logger

from music_minion.core.db_adapter import get_radio_db_connection
from music_minion.domain.library.models import Track

from .models import NowPlaying
from .schedule import get_schedule_for_time
from .stations import get_station

# Maximum recursion depth for schedule resolution (prevents infinite loops)
MAX_SCHEDULE_DEPTH = 10


def deterministic_shuffle(tracks: list[Track], seed: str) -> list[Track]:
    """Shuffle tracks using a deterministic seed.

    Given the same seed, the same order will always be produced.
    This enables consistent "where would we be" calculations.

    Args:
        tracks: List of tracks to shuffle
        seed: Seed string (typically "{station_id}-{date}")

    Returns:
        New list with tracks in shuffled order
    """
    if not tracks:
        return []

    # Create a deterministic random state from the seed
    seed_hash = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed_hash)

    # Shuffle a copy
    shuffled = list(tracks)
    rng.shuffle(shuffled)
    return shuffled


def get_skipped_tracks(station_id: int, skip_date: date) -> set[int]:
    """Get track IDs that have been skipped for a station on a given date.

    Skipped tracks are excluded from timeline calculations to handle
    unavailable sources gracefully.

    Args:
        station_id: Station ID
        skip_date: Date to check skips for

    Returns:
        Set of skipped track IDs
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT track_id FROM radio_skipped
            WHERE station_id = ? AND skip_date = ? AND track_id IS NOT NULL
            """,
            (station_id, skip_date.isoformat()),
        )
        return {row["track_id"] for row in cursor.fetchall()}


def mark_track_skipped(
    station_id: int,
    track_id: int,
    reason: str,
    source_url: Optional[str] = None,
) -> None:
    """Mark a track as skipped for the current session.

    Skipped tracks will be excluded from timeline calculations until
    daily clearing.

    Args:
        station_id: Station ID
        track_id: Track ID to skip
        reason: Reason for skipping ('unavailable' | 'error')
        source_url: Optional source URL for non-local sources
    """
    with get_radio_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO radio_skipped (station_id, track_id, source_url, reason)
            VALUES (?, ?, ?, ?)
            """,
            (station_id, track_id, source_url, reason),
        )
        conn.commit()
        logger.info(
            f"Marked track {track_id} as skipped for station {station_id}: {reason}"
        )


def clear_daily_skipped(station_id: int) -> int:
    """Clear skipped tracks for a station (typically called on date change).

    Args:
        station_id: Station ID

    Returns:
        Number of entries cleared
    """
    today = date.today()
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM radio_skipped
            WHERE station_id = ? AND skip_date < ?
            """,
            (station_id, today.isoformat()),
        )
        conn.commit()
        cleared = cursor.rowcount
        if cleared > 0:
            logger.info(
                f"Cleared {cleared} old skipped entries for station {station_id}"
            )
        return cleared


def _get_range_start_time(
    station_id: int,
    current_time: datetime,
    depth: int = 0,
) -> datetime:
    """Find when the current time range started for a station.

    For meta-stations with schedules, finds the start of the current time range.
    For regular stations, returns start of day.

    Args:
        station_id: Station ID
        current_time: Current time
        depth: Recursion depth (for cycle detection)

    Returns:
        DateTime when the current range started
    """
    if depth > MAX_SCHEDULE_DEPTH:
        logger.warning(f"Max schedule depth reached for station {station_id}")
        return current_time.replace(hour=0, minute=0, second=0, microsecond=0)

    schedule_entry = get_schedule_for_time(station_id, current_time)
    if schedule_entry:
        # Parse start time and create datetime for today
        parts = schedule_entry.start_time.split(":")
        start_time = time(int(parts[0]), int(parts[1]))
        range_start = current_time.replace(
            hour=start_time.hour,
            minute=start_time.minute,
            second=0,
            microsecond=0,
        )

        # Handle overnight ranges (e.g., 22:00-06:00)
        # If start > current time, the range started yesterday
        if range_start > current_time:
            range_start -= timedelta(days=1)

        return range_start

    # No schedule - range is start of day
    return current_time.replace(hour=0, minute=0, second=0, microsecond=0)


def _resolve_target_station(
    station_id: int,
    current_time: datetime,
    depth: int = 0,
) -> tuple[int, datetime]:
    """Resolve a station through its schedule to find the actual playing station.

    For meta-stations, follows schedule references to find the leaf station.
    Returns the resolved station ID and the range start time.

    Args:
        station_id: Station ID to resolve
        current_time: Current time
        depth: Recursion depth (for cycle detection)

    Returns:
        Tuple of (resolved_station_id, range_start_time)
    """
    if depth > MAX_SCHEDULE_DEPTH:
        logger.warning(f"Max schedule depth reached resolving station {station_id}")
        return station_id, current_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    schedule_entry = get_schedule_for_time(station_id, current_time)
    if schedule_entry:
        # Get range start for this schedule entry
        range_start = _get_range_start_time(station_id, current_time, depth)
        # Recurse into target station
        return _resolve_target_station(
            schedule_entry.target_station_id,
            current_time,
            depth + 1,
        )

    # This is a leaf station (no schedule) - return it with range start
    range_start = _get_range_start_time(station_id, current_time, depth)
    return station_id, range_start


def _get_playlist_tracks_as_models(
    playlist_id: int,
    exclude_ids: set[int],
) -> list[Track]:
    """Get playlist tracks as Track models, excluding specific IDs.

    Args:
        playlist_id: Playlist ID
        exclude_ids: Track IDs to exclude

    Returns:
        List of Track objects
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute("""
            SELECT t.id, t.local_path, t.title, t.artist, t.album, t.genre,
                   t.year, t.duration, t.key_signature, t.bpm
            FROM tracks t
            JOIN playlist_tracks pt ON t.id = pt.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
        """, (playlist_id,))

        tracks = []
        for row in cursor.fetchall():
            if row["id"] not in exclude_ids:
                track = Track(
                    id=row["id"],
                    local_path=row["local_path"],
                    title=row["title"],
                    artist=row["artist"],
                    album=row["album"],
                    genre=row["genre"],
                    year=row["year"],
                    duration=row["duration"],
                    key=row["key_signature"],
                    bpm=row["bpm"],
                )
                tracks.append(track)
        return tracks


def calculate_now_playing(
    station_id: int,
    current_time: datetime,
) -> Optional[NowPlaying]:
    """Calculate what should be playing at a given time.

    This is the core deterministic algorithm that enables "tune in mid-stream".
    Given a station and time, calculates exactly what track and position
    should be playing.

    Args:
        station_id: Station ID
        current_time: Time to calculate for

    Returns:
        NowPlaying with current track, position, and upcoming queue,
        or None if no tracks available
    """
    station = get_station(station_id)
    if not station:
        logger.warning(f"Station {station_id} not found")
        return None

    # Resolve through schedule to find actual playing station
    resolved_station_id, _ = _resolve_target_station(station_id, current_time)
    resolved_station = get_station(resolved_station_id)
    if not resolved_station:
        logger.warning(f"Resolved station {resolved_station_id} not found")
        return None

    # Get range start for the resolved station
    range_start = _get_range_start_time(resolved_station_id, current_time)

    # Meta-stations without playlists just delegate to schedule
    if resolved_station.playlist_id is None:
        logger.warning(f"Station {resolved_station_id} has no playlist")
        return None

    # Get tracks, excluding skipped ones
    skipped_ids = get_skipped_tracks(resolved_station_id, current_time.date())
    tracks = _get_playlist_tracks_as_models(resolved_station.playlist_id, skipped_ids)

    if not tracks:
        logger.warning(f"No tracks available for station {resolved_station_id}")
        return None

    # Apply shuffle if needed (deterministic daily seed)
    if resolved_station.mode == "shuffle":
        seed = f"{resolved_station_id}-{current_time.date()}"
        tracks = deterministic_shuffle(tracks, seed)

    # Calculate position in the playlist loop
    total_duration_ms = sum((t.duration or 0) * 1000 for t in tracks)
    if total_duration_ms == 0:
        logger.warning(
            f"Playlist has zero total duration for station {resolved_station_id}"
        )
        return None

    elapsed_ms = (current_time - range_start).total_seconds() * 1000
    position_in_loop = elapsed_ms % total_duration_ms

    # Walk through to find current track
    accumulated_ms = 0.0
    for i, track in enumerate(tracks):
        track_duration_ms = (track.duration or 0) * 1000
        if accumulated_ms + track_duration_ms > position_in_loop:
            position_ms = int(position_in_loop - accumulated_ms)
            next_track = tracks[(i + 1) % len(tracks)] if len(tracks) > 1 else None

            # Get upcoming tracks (next 5)
            upcoming = []
            for j in range(1, 6):
                if len(tracks) > j:
                    upcoming.append(tracks[(i + j) % len(tracks)])

            # Determine source type
            source_type = _determine_source_type(track)

            return NowPlaying(
                track=track,
                position_ms=position_ms,
                next_track=next_track,
                upcoming=upcoming,
                station_id=resolved_station_id,
                source_type=source_type,
            )
        accumulated_ms += track_duration_ms

    # Should not reach here, but fallback to first track
    logger.warning(f"Position calculation overflow for station {resolved_station_id}")
    return NowPlaying(
        track=tracks[0],
        position_ms=0,
        next_track=tracks[1] if len(tracks) > 1 else None,
        upcoming=tracks[1:6],
        station_id=resolved_station_id,
        source_type=_determine_source_type(tracks[0]),
    )


def _determine_source_type(track: Track) -> str:
    """Determine the source type for a track.

    Args:
        track: Track to check

    Returns:
        Source type: 'local' | 'youtube' | 'spotify' | 'soundcloud'
    """
    if track.youtube_id:
        return "youtube"
    if track.spotify_id:
        return "spotify"
    if track.soundcloud_id:
        return "soundcloud"
    return "local"


def get_next_track(
    station_id: int,
    current_time: datetime,
) -> Optional[Track]:
    """Get the next track that should play.

    Convenience function that extracts just the track from calculate_now_playing.

    Args:
        station_id: Station ID
        current_time: Current time

    Returns:
        The track that should be playing, or None if unavailable
    """
    now_playing = calculate_now_playing(station_id, current_time)
    return now_playing.track if now_playing else None


def get_upcoming_tracks(
    station_id: int,
    current_time: datetime,
    count: int = 10,
) -> list[Track]:
    """Get upcoming tracks for a station.

    Args:
        station_id: Station ID
        current_time: Current time
        count: Number of upcoming tracks to return

    Returns:
        List of upcoming tracks
    """
    now_playing = calculate_now_playing(station_id, current_time)
    if not now_playing:
        return []

    # Start with the tracks from NowPlaying
    result = list(now_playing.upcoming)

    # If we need more, we need to recalculate with extended lookahead
    if len(result) < count:
        station = get_station(now_playing.station_id)
        if station and station.playlist_id:
            skipped_ids = get_skipped_tracks(
                now_playing.station_id, current_time.date()
            )
            tracks = _get_playlist_tracks_as_models(station.playlist_id, skipped_ids)

            if station.mode == "shuffle":
                seed = f"{now_playing.station_id}-{current_time.date()}"
                tracks = deterministic_shuffle(tracks, seed)

            # Find current track index and extend upcoming
            for i, track in enumerate(tracks):
                if track.id == now_playing.track.id:
                    for j in range(1, count + 1):
                        if j <= len(result):
                            continue
                        result.append(tracks[(i + j) % len(tracks)])
                    break

    return result[:count]
