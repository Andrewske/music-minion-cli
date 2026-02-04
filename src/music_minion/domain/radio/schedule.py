"""
Schedule management for radio stations.

Handles time range entries that define when different stations play.
"""

from datetime import datetime, time
from typing import Any, Optional

from loguru import logger

from music_minion.core.db_adapter import get_radio_db_connection

from .models import ScheduleEntry


def _row_to_schedule_entry(row: dict[str, Any]) -> ScheduleEntry:
    """Convert database row to ScheduleEntry dataclass."""
    return ScheduleEntry(
        id=row["id"],
        station_id=row["station_id"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        target_station_id=row["target_station_id"],
        position=row["position"],
    )


def time_in_range(start: str, end: str, check_time: time) -> bool:
    """Check if a time falls within a range, handling midnight wrap.

    Args:
        start: Start time in "HH:MM" format
        end: End time in "HH:MM" format
        check_time: Time to check

    Returns:
        True if check_time is within [start, end)

    Examples:
        time_in_range("09:00", "17:00", time(12, 0))  # True
        time_in_range("22:00", "06:00", time(23, 30))  # True (overnight)
        time_in_range("22:00", "06:00", time(3, 0))   # True (overnight)
        time_in_range("09:00", "17:00", time(17, 0))  # False (end is exclusive)
    """
    start_time = _parse_time(start)
    end_time = _parse_time(end)

    if start_time <= end_time:
        # Normal range (e.g., 09:00 to 17:00)
        return start_time <= check_time < end_time
    else:
        # Overnight range (e.g., 22:00 to 06:00)
        return check_time >= start_time or check_time < end_time


def _parse_time(time_str: str) -> time:
    """Parse "HH:MM" string to time object."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def add_schedule_entry(
    station_id: int,
    start_time: str,
    end_time: str,
    target_station_id: int,
    position: Optional[int] = None,
) -> ScheduleEntry:
    """Add a schedule entry to a station.

    Args:
        station_id: The meta-station that owns this schedule
        start_time: Start time in "HH:MM" format
        end_time: End time in "HH:MM" format
        target_station_id: Station to play during this time range
        position: Order for overlapping ranges (defaults to next available)

    Returns:
        The created ScheduleEntry

    Raises:
        ValueError: If station references itself or times are invalid
    """
    if station_id == target_station_id:
        raise ValueError("Station cannot reference itself in schedule")

    _validate_time_format(start_time)
    _validate_time_format(end_time)

    with get_radio_db_connection() as conn:
        # Get next position if not specified
        if position is None:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) as next_pos FROM station_schedule WHERE station_id = ?",
                (station_id,),
            )
            position = cursor.fetchone()["next_pos"]

        cursor = conn.execute(
            """
            INSERT INTO station_schedule (station_id, start_time, end_time, target_station_id, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            (station_id, start_time, end_time, target_station_id, position),
        )
        conn.commit()
        entry_id = cursor.lastrowid

        cursor = conn.execute(
            "SELECT * FROM station_schedule WHERE id = ?",
            (entry_id,),
        )
        row = cursor.fetchone()
        entry = _row_to_schedule_entry(dict(row))
        logger.info(
            f"Added schedule entry {entry_id}: {start_time}-{end_time} -> station {target_station_id}"
        )
        return entry


def _validate_time_format(time_str: str) -> None:
    """Validate time string is in HH:MM format."""
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError()
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError(
            f"Invalid time format: '{time_str}'. Expected 'HH:MM' (e.g., '09:00')"
        )


def get_schedule_entries(station_id: int) -> list[ScheduleEntry]:
    """Get all schedule entries for a station.

    Args:
        station_id: Station ID

    Returns:
        List of schedule entries, ordered by position
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM station_schedule WHERE station_id = ? ORDER BY position",
            (station_id,),
        )
        return [_row_to_schedule_entry(dict(row)) for row in cursor.fetchall()]


def get_schedule_for_time(
    station_id: int, current_time: datetime
) -> Optional[ScheduleEntry]:
    """Find the active schedule entry for a given time.

    Args:
        station_id: Station ID
        current_time: Time to check

    Returns:
        The matching ScheduleEntry or None if no schedule covers this time
    """
    entries = get_schedule_entries(station_id)
    check_time = current_time.time()

    # Find first matching entry (ordered by position)
    for entry in entries:
        if time_in_range(entry.start_time, entry.end_time, check_time):
            return entry

    return None


def get_schedule_entry(entry_id: int) -> Optional[ScheduleEntry]:
    """Get a specific schedule entry by ID.

    Args:
        entry_id: Schedule entry ID

    Returns:
        ScheduleEntry or None if not found
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM station_schedule WHERE id = ?",
            (entry_id,),
        )
        row = cursor.fetchone()
        return _row_to_schedule_entry(dict(row)) if row else None


def update_schedule_entry(
    entry_id: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    target_station_id: Optional[int] = None,
    position: Optional[int] = None,
) -> bool:
    """Update a schedule entry.

    Args:
        entry_id: Schedule entry ID
        start_time: New start time (optional)
        end_time: New end time (optional)
        target_station_id: New target station (optional)
        position: New position (optional)

    Returns:
        True if updated, False if entry not found

    Raises:
        ValueError: If times are invalid or creates self-reference
    """
    if start_time is not None:
        _validate_time_format(start_time)
    if end_time is not None:
        _validate_time_format(end_time)

    # Check for self-reference if updating target
    if target_station_id is not None:
        entry = get_schedule_entry(entry_id)
        if entry and entry.station_id == target_station_id:
            raise ValueError("Station cannot reference itself in schedule")

    updates: list[str] = []
    params: list[Any] = []

    if start_time is not None:
        updates.append("start_time = ?")
        params.append(start_time)
    if end_time is not None:
        updates.append("end_time = ?")
        params.append(end_time)
    if target_station_id is not None:
        updates.append("target_station_id = ?")
        params.append(target_station_id)
    if position is not None:
        updates.append("position = ?")
        params.append(position)

    if not updates:
        return True  # Nothing to update

    params.append(entry_id)

    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            f"UPDATE station_schedule SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"Updated schedule entry {entry_id}")
        return updated


def delete_schedule_entry(entry_id: int) -> bool:
    """Delete a schedule entry.

    Args:
        entry_id: Schedule entry ID

    Returns:
        True if deleted, False if entry not found
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM station_schedule WHERE id = ?",
            (entry_id,),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted schedule entry {entry_id}")
        return deleted


def reorder_schedule_entries(station_id: int, entry_ids: list[int]) -> bool:
    """Reorder schedule entries for a station.

    Args:
        station_id: Station ID
        entry_ids: List of entry IDs in desired order

    Returns:
        True if reordered successfully
    """
    with get_radio_db_connection() as conn:
        conn.execute("BEGIN")
        try:
            for position, entry_id in enumerate(entry_ids):
                conn.execute(
                    "UPDATE station_schedule SET position = ? WHERE id = ? AND station_id = ?",
                    (position, entry_id, station_id),
                )
            conn.commit()
            logger.info(f"Reordered schedule entries for station {station_id}")
            return True
        except Exception:
            conn.rollback()
            raise
