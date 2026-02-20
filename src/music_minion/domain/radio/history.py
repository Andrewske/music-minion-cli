"""
Radio playback history queries and analytics.

Provides functions for querying radio_history table with filtering,
pagination, and aggregation for stats and analytics.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from loguru import logger

from music_minion.core.db_adapter import get_radio_db_connection
from music_minion.domain.library.models import Track


def start_play(track_id: int, source_type: str = "local") -> int:
    """Insert a new history entry when a track starts playing. Returns history_id."""
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO radio_history (track_id, source_type, started_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (track_id, source_type)
        )
        conn.commit()
        return cursor.lastrowid


def end_play(history_id: int, duration_ms: int, reason: str = "skip") -> None:
    """Update history entry with end time, listening duration, and end reason.

    Args:
        history_id: ID of the history entry to close
        duration_ms: Total time spent listening in milliseconds (accounts for seeking)
        reason: Why playback ended - 'skip', 'completed', or 'new_play'
    """
    with get_radio_db_connection() as conn:
        conn.execute(
            """
            UPDATE radio_history
            SET ended_at = CURRENT_TIMESTAMP, position_ms = ?, end_reason = ?
            WHERE id = ?
            """,
            (duration_ms, reason, history_id)
        )
        conn.commit()


# NOTE: position_ms column stores DURATION (actual listening time), not position.
# Name kept for backwards compatibility with existing data.


@dataclass(frozen=True)
class HistoryEntry:
    """A single playback history entry."""

    id: int
    track: Track
    source_type: str  # 'local' | 'youtube' | 'spotify' | 'soundcloud'
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: int  # Renamed from position_ms for clarity
    end_reason: Optional[str] = None  # 'skip', 'completed', 'new_play'


@dataclass(frozen=True)
class TrackPlayStats:
    """Statistics for a specific track's playback."""

    track: Track
    play_count: int
    total_duration_seconds: int  # Total time spent listening


@dataclass(frozen=True)
class Stats:
    """Aggregated statistics for radio playback history."""

    total_plays: int
    total_minutes: int  # Actual listening time
    unique_tracks: int
    days_queried: int


# Legacy alias for backwards compatibility
StationStats = Stats


def get_history_entries(
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[HistoryEntry]:
    """Get playback history entries with filtering and pagination.

    Args:
        limit: Maximum number of entries to return
        offset: Number of entries to skip (for pagination)
        start_date: Filter entries on or after this date (YYYY-MM-DD)
        end_date: Filter entries before this date (YYYY-MM-DD)

    Returns:
        List of HistoryEntry objects, ordered by started_at DESC
    """
    with get_radio_db_connection() as conn:
        query = """
            SELECT
                rh.id,
                rh.track_id,
                t.local_path,
                t.title,
                t.artist,
                t.album,
                t.duration,
                rh.source_type,
                rh.started_at,
                rh.ended_at,
                rh.position_ms,
                rh.end_reason
            FROM radio_history rh
            LEFT JOIN tracks t ON rh.track_id = t.id
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND DATE(rh.started_at) >= ?"
            params.append(start_date)

        if end_date:
            query += " AND DATE(rh.started_at) < ?"
            params.append(end_date)

        query += " ORDER BY rh.started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        entries = []
        for row in rows:
            # Create Track object (handle missing tracks gracefully)
            track = Track(
                id=row["track_id"],
                local_path=row["local_path"],
                title=row["title"] or "Unknown Track",
                artist=row["artist"] or "Unknown Artist",
                album=row["album"],
                duration=row["duration"],
            )

            entry = HistoryEntry(
                id=row["id"],
                track=track,
                source_type=row["source_type"],
                started_at=_parse_timestamp(row["started_at"]),
                ended_at=_parse_timestamp(row["ended_at"]) if row["ended_at"] else None,
                duration_ms=row["position_ms"],
                end_reason=row["end_reason"] if "end_reason" in row.keys() else None,
            )
            entries.append(entry)

        logger.debug(
            f"Retrieved {len(entries)} history entries "
            f"(limit={limit}, offset={offset})"
        )
        return entries


def get_stats(days: int = 30) -> Stats:
    """Get aggregated statistics for radio playback history.

    Args:
        days: Number of days to include (default 30)

    Returns:
        Stats object with aggregated playback statistics
    """
    with get_radio_db_connection() as conn:
        start_date = (datetime.now() - timedelta(days=days)).date()
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total_plays,
                COALESCE(SUM(position_ms) / 60000, 0) as total_minutes,
                COUNT(DISTINCT track_id) as unique_tracks
            FROM radio_history
            WHERE DATE(started_at) >= ?
            """,
            (start_date.isoformat(),)
        )
        row = cursor.fetchone()
        return Stats(
            total_plays=row["total_plays"] or 0,
            total_minutes=row["total_minutes"] or 0,
            unique_tracks=row["unique_tracks"] or 0,
            days_queried=days,
        )


# Legacy alias for backwards compatibility
def get_station_stats(station_id: int, days: int = 30) -> Optional[Stats]:
    """DEPRECATED: Use get_stats() instead.

    Get aggregated statistics (ignores station_id for backwards compatibility).
    """
    logger.warning("get_station_stats() is deprecated, use get_stats() instead")
    return get_stats(days)


def get_most_played_tracks(
    limit: int = 10,
    days: int = 30,
) -> list[TrackPlayStats]:
    """Get most played tracks with play counts.

    Args:
        limit: Maximum number of tracks to return
        days: Number of days to include (default 30)

    Returns:
        List of TrackPlayStats, ordered by play_count DESC
    """
    with get_radio_db_connection() as conn:
        start_date = (datetime.now() - timedelta(days=days)).date()

        query = """
            SELECT
                t.id,
                t.local_path,
                t.title,
                t.artist,
                t.album,
                t.duration,
                COUNT(*) as play_count,
                SUM(rh.position_ms) / 1000 as total_duration_seconds
            FROM radio_history rh
            JOIN tracks t ON rh.track_id = t.id
            WHERE DATE(rh.started_at) >= ?
            GROUP BY t.id, t.local_path, t.title, t.artist, t.album, t.duration
            ORDER BY play_count DESC
            LIMIT ?
        """
        params = [start_date.isoformat(), limit]

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        stats = []
        for row in rows:
            track = Track(
                id=row["id"],
                local_path=row["local_path"],
                title=row["title"] or "Unknown Track",
                artist=row["artist"] or "Unknown Artist",
                album=row["album"],
                duration=row["duration"],
            )

            stat = TrackPlayStats(
                track=track,
                play_count=row["play_count"],
                total_duration_seconds=row["total_duration_seconds"] or 0,
            )
            stats.append(stat)

        logger.debug(
            f"Retrieved {len(stats)} top tracks "
            f"(days={days}, limit={limit})"
        )
        return stats


def _parse_timestamp(ts) -> datetime:
    """Parse timestamp from string or return datetime as-is."""
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now()
