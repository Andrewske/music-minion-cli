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


@dataclass(frozen=True)
class HistoryEntry:
    """A single playback history entry."""

    id: int
    station_id: int
    station_name: str
    track: Track
    source_type: str  # 'local' | 'youtube' | 'spotify' | 'soundcloud'
    started_at: datetime
    ended_at: Optional[datetime]
    position_ms: int


@dataclass(frozen=True)
class TrackPlayStats:
    """Statistics for a specific track's playback."""

    track: Track
    play_count: int
    total_duration_seconds: int  # Total time spent listening


@dataclass(frozen=True)
class StationStats:
    """Aggregated statistics for a station."""

    station_id: int
    station_name: str
    total_plays: int
    total_minutes: int
    unique_tracks: int
    days_queried: int


def get_history_entries(
    station_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[HistoryEntry]:
    """Get playback history entries with filtering and pagination.

    Args:
        station_id: Filter by station ID (None = all stations)
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
                rh.station_id,
                s.name as station_name,
                rh.track_id,
                t.local_path,
                t.title,
                t.artist,
                t.album,
                t.duration,
                rh.source_type,
                rh.started_at,
                rh.ended_at,
                rh.position_ms
            FROM radio_history rh
            LEFT JOIN stations s ON rh.station_id = s.id
            LEFT JOIN tracks t ON rh.track_id = t.id
            WHERE 1=1
        """
        params = []

        if station_id is not None:
            query += " AND rh.station_id = ?"
            params.append(station_id)

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
                station_id=row["station_id"],
                station_name=row["station_name"] or "Unknown Station",
                track=track,
                source_type=row["source_type"],
                started_at=_parse_timestamp(row["started_at"]),
                ended_at=_parse_timestamp(row["ended_at"]) if row["ended_at"] else None,
                position_ms=row["position_ms"],
            )
            entries.append(entry)

        logger.debug(
            f"Retrieved {len(entries)} history entries "
            f"(station={station_id}, limit={limit}, offset={offset})"
        )
        return entries


def get_station_stats(station_id: int, days: int = 30) -> Optional[StationStats]:
    """Get aggregated statistics for a station.

    Args:
        station_id: Station ID
        days: Number of days to include (default 30)

    Returns:
        StationStats object, or None if station not found
    """
    with get_radio_db_connection() as conn:
        # Calculate date range
        start_date = (datetime.now() - timedelta(days=days)).date()

        # Get station name
        cursor = conn.execute("SELECT name FROM stations WHERE id = ?", (station_id,))
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Station {station_id} not found")
            return None

        station_name = row["name"]

        # Get stats
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total_plays,
                SUM(CAST((t.duration / 60) AS INTEGER)) as total_minutes,
                COUNT(DISTINCT rh.track_id) as unique_tracks
            FROM radio_history rh
            LEFT JOIN tracks t ON rh.track_id = t.id
            WHERE rh.station_id = ?
              AND DATE(rh.started_at) >= ?
            """,
            (station_id, start_date.isoformat()),
        )
        row = cursor.fetchone()

        return StationStats(
            station_id=station_id,
            station_name=station_name,
            total_plays=row["total_plays"] or 0,
            total_minutes=row["total_minutes"] or 0,
            unique_tracks=row["unique_tracks"] or 0,
            days_queried=days,
        )


def get_most_played_tracks(
    station_id: Optional[int] = None,
    limit: int = 10,
    days: int = 30,
) -> list[TrackPlayStats]:
    """Get most played tracks with play counts.

    Args:
        station_id: Filter by station ID (None = all stations)
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
                SUM(CAST(t.duration AS INTEGER)) as total_duration_seconds
            FROM radio_history rh
            JOIN tracks t ON rh.track_id = t.id
            WHERE DATE(rh.started_at) >= ?
        """
        params = [start_date.isoformat()]

        if station_id is not None:
            query += " AND rh.station_id = ?"
            params.append(station_id)

        query += """
            GROUP BY t.id, t.local_path, t.title, t.artist, t.album, t.duration
            ORDER BY play_count DESC
            LIMIT ?
        """
        params.append(limit)

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
            f"(station={station_id}, days={days}, limit={limit})"
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
