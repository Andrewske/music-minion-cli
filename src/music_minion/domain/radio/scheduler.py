"""
Radio scheduler service for Liquidsoap integration.

Manages track selection and provides the API endpoint interface
for Liquidsoap to request the next track to play.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from loguru import logger

from music_minion.core.db_adapter import get_radio_db_connection
from music_minion.domain.library.models import Track

from .models import NowPlaying
from .stations import get_active_station
from .timeline import calculate_now_playing, mark_track_skipped


@dataclass
class SchedulerState:
    """Tracks current scheduler state for smooth transitions.

    Used to detect track changes between requests and avoid
    duplicate history entries.
    """

    current_track_id: Optional[int] = None
    current_started_at: Optional[datetime] = None
    last_request_time: Optional[datetime] = None


# Module-level state (will be replaced by proper state management later)
_scheduler_state = SchedulerState()


def get_next_track_path() -> Optional[str]:
    """Get the next track path for Liquidsoap.

    Called by the API endpoint when Liquidsoap requests a new track.
    Uses deterministic timeline calculation to determine what should
    be playing at the current moment.

    Returns:
        File path to play, or None if nothing available
    """
    global _scheduler_state

    station = get_active_station()
    if not station:
        logger.debug("No active station")
        return None

    now = datetime.now()
    now_playing = calculate_now_playing(station.id, now)

    if not now_playing:
        logger.warning(f"No tracks available for station {station.name}")
        return None

    track = now_playing.track

    # Check if this is a new track or continuation
    if _scheduler_state.current_track_id != track.id:
        # New track - log and update state
        logger.info(f"Now playing: {track.artist} - {track.title}")
        _record_history(
            station.id, track, now_playing.source_type, now_playing.position_ms
        )
        _scheduler_state = SchedulerState(
            current_track_id=track.id,
            current_started_at=now,
            last_request_time=now,
        )
    else:
        # Same track - just update request time
        _scheduler_state.last_request_time = now

    # For local files, return the path
    if track.local_path:
        return track.local_path

    # For streaming tracks (SoundCloud, YouTube, etc.), resolve URL via yt-dlp
    if track.source_url:
        from .stream_resolver import resolve_stream_url

        stream_url = resolve_stream_url(track.source_url)
        if stream_url:
            logger.debug(f"Resolved stream URL for track {track.id}: {track.source_url}")
            return stream_url
        else:
            # Stream resolution failed - mark as skipped and try next
            logger.warning(
                f"Failed to resolve stream URL for track {track.id}, marking as skipped"
            )
            mark_track_skipped(station.id, track.id, reason="unavailable")
            # Reset state and try to get next track
            _scheduler_state = SchedulerState()
            return get_next_track_path()

    # No local path and no streaming URL - track has no playable source
    logger.warning(f"Track has no playable source: {track}")
    return None


def _record_history(
    station_id: int,
    track: Track,
    source_type: str,
    position_ms: int,
) -> None:
    """Record track to radio_history table.

    Args:
        station_id: Station ID
        track: Track being played
        source_type: Source type (local, youtube, spotify, soundcloud)
        position_ms: Starting position in track
    """
    # For streaming tracks, record the source URL for debugging/history
    source_url = track.source_url if source_type != "local" else None

    with get_radio_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO radio_history (station_id, track_id, source_type, source_url, started_at, position_ms)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            (station_id, track.id, source_type, source_url, position_ms),
        )
        conn.commit()
        logger.debug(
            f"Recorded history: station={station_id}, track={track.id}, "
            f"source={source_type}, position={position_ms}ms"
        )


def handle_track_unavailable(track_id: int, reason: str = "unavailable") -> Optional[str]:
    """Handle when a track is unavailable (file missing, etc).

    Marks it as skipped and returns the next track. This allows
    Liquidsoap to gracefully skip broken tracks without manual intervention.

    Args:
        track_id: Track ID that is unavailable
        reason: Reason for skipping ('unavailable' | 'error')

    Returns:
        File path of the next track, or None if nothing available
    """
    station = get_active_station()
    if not station:
        return None

    mark_track_skipped(station.id, track_id, reason)
    logger.warning(f"Marked track {track_id} as skipped: {reason}")

    # Reset scheduler state to force recalculation
    global _scheduler_state
    _scheduler_state = SchedulerState()

    # Get next track
    return get_next_track_path()


def get_current_state() -> Optional[NowPlaying]:
    """Get current now-playing state for API/UI.

    Returns:
        Current NowPlaying state, or None if no station active
    """
    station = get_active_station()
    if not station:
        return None

    return calculate_now_playing(station.id, datetime.now())


def get_scheduler_info() -> dict:
    """Get current scheduler state for debugging.

    Returns:
        Dict with scheduler state information
    """
    return {
        "current_track_id": _scheduler_state.current_track_id,
        "current_started_at": (
            _scheduler_state.current_started_at.isoformat()
            if _scheduler_state.current_started_at
            else None
        ),
        "last_request_time": (
            _scheduler_state.last_request_time.isoformat()
            if _scheduler_state.last_request_time
            else None
        ),
    }


def reset_scheduler_state() -> None:
    """Reset scheduler state (useful for testing or manual reset).

    Clears the current track tracking, forcing a fresh calculation
    on the next request.
    """
    global _scheduler_state
    _scheduler_state = SchedulerState()
    logger.info("Scheduler state reset")
