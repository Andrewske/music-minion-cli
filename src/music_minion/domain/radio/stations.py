"""
Station management for radio.

CRUD operations for radio stations using functional patterns.
"""

from datetime import datetime
from typing import Any, Optional

from loguru import logger

from music_minion.core.db_adapter import get_radio_db_connection, is_postgres

from .models import Station


def _parse_datetime(val: Any) -> datetime:
    """Parse datetime from either string (SQLite) or datetime object (PostgreSQL)."""
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _row_to_station(row: dict[str, Any]) -> Station:
    """Convert database row to Station dataclass."""
    return Station(
        id=row["id"],
        name=row["name"],
        playlist_id=row["playlist_id"],
        mode=row["mode"],
        is_active=bool(row["is_active"]),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def create_station(
    name: str,
    playlist_id: Optional[int] = None,
    mode: str = "shuffle",
) -> Station:
    """Create a new radio station.

    Args:
        name: Unique station name
        playlist_id: Optional playlist to associate with this station
        mode: Playback mode - 'shuffle' or 'queue'

    Returns:
        The created Station

    Raises:
        ValueError: If name already exists or mode is invalid
    """
    if mode not in ("shuffle", "queue"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'shuffle' or 'queue'")

    with get_radio_db_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO stations (name, playlist_id, mode, is_active)
                VALUES (?, ?, ?, FALSE)
                """,
                (name, playlist_id, mode),
            )
            conn.commit()
            station_id = cursor.lastrowid

            # Fetch the created station to get timestamps
            cursor = conn.execute(
                "SELECT * FROM stations WHERE id = ?",
                (station_id,),
            )
            row = cursor.fetchone()
            station = _row_to_station(dict(row))
            logger.info(f"Created station '{name}' with id {station_id}")
            return station

        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Station '{name}' already exists")
            raise


def get_station(station_id: int) -> Optional[Station]:
    """Get a station by ID.

    Args:
        station_id: Station ID

    Returns:
        Station or None if not found
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM stations WHERE id = ?",
            (station_id,),
        )
        row = cursor.fetchone()
        return _row_to_station(dict(row)) if row else None


def get_station_by_name(name: str) -> Optional[Station]:
    """Get a station by name.

    Args:
        name: Station name

    Returns:
        Station or None if not found
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM stations WHERE name = ?",
            (name,),
        )
        row = cursor.fetchone()
        return _row_to_station(dict(row)) if row else None


def get_all_stations() -> list[Station]:
    """Get all radio stations.

    Returns:
        List of all stations, ordered by name
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM stations ORDER BY name",
        )
        return [_row_to_station(dict(row)) for row in cursor.fetchall()]


def get_active_station() -> Optional[Station]:
    """Get the currently active station.

    Returns:
        Active station or None if no station is active
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM stations WHERE is_active = TRUE",
        )
        row = cursor.fetchone()
        return _row_to_station(dict(row)) if row else None


def activate_station(station_id: int) -> bool:
    """Activate a station (deactivating any previously active station).

    Args:
        station_id: Station ID to activate

    Returns:
        True if activated successfully, False if station not found
    """
    with get_radio_db_connection() as conn:
        conn.execute("BEGIN")
        try:
            # Verify station exists
            cursor = conn.execute(
                "SELECT id FROM stations WHERE id = ?",
                (station_id,),
            )
            if not cursor.fetchone():
                conn.rollback()
                return False

            # Deactivate all stations
            conn.execute("UPDATE stations SET is_active = FALSE")

            # Activate the target station
            conn.execute(
                """
                UPDATE stations
                SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (station_id,),
            )

            # Update radio_state table
            conn.execute(
                """
                INSERT INTO radio_state (id, active_station_id, started_at, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    active_station_id = excluded.active_station_id,
                    started_at = excluded.started_at,
                    updated_at = excluded.updated_at
                """,
                (station_id,),
            )

            conn.commit()
            logger.info(f"Activated station {station_id}")
            return True

        except Exception:
            conn.rollback()
            raise


def deactivate_all_stations() -> bool:
    """Deactivate all stations (stop radio).

    Returns:
        True if any station was deactivated
    """
    with get_radio_db_connection() as conn:
        conn.execute("BEGIN")
        try:
            cursor = conn.execute(
                "UPDATE stations SET is_active = FALSE WHERE is_active = TRUE"
            )
            deactivated = cursor.rowcount > 0

            # Clear radio_state
            conn.execute(
                """
                UPDATE radio_state
                SET active_station_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """
            )

            conn.commit()
            if deactivated:
                logger.info("Deactivated all stations")
            return deactivated

        except Exception:
            conn.rollback()
            raise


def update_station(
    station_id: int,
    name: Optional[str] = None,
    playlist_id: Optional[int] = None,
    mode: Optional[str] = None,
) -> bool:
    """Update a station's properties.

    Args:
        station_id: Station ID to update
        name: New name (optional)
        playlist_id: New playlist ID (optional, use -1 to clear)
        mode: New mode - 'shuffle' or 'queue' (optional)

    Returns:
        True if updated successfully, False if station not found

    Raises:
        ValueError: If name already exists or mode is invalid
    """
    if mode is not None and mode not in ("shuffle", "queue"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'shuffle' or 'queue'")

    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if playlist_id is not None:
        updates.append("playlist_id = ?")
        params.append(None if playlist_id == -1 else playlist_id)
    if mode is not None:
        updates.append("mode = ?")
        params.append(mode)

    if not updates:
        return True  # Nothing to update

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(station_id)

    with get_radio_db_connection() as conn:
        try:
            cursor = conn.execute(
                f"UPDATE stations SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Updated station {station_id}")
            return updated

        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError(f"Station '{name}' already exists")
            raise


def delete_station(station_id: int) -> bool:
    """Delete a station.

    This will cascade delete related schedule entries and history.

    Args:
        station_id: Station ID to delete

    Returns:
        True if deleted successfully, False if station not found
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM stations WHERE id = ?",
            (station_id,),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted station {station_id}")
        return deleted


def record_now_playing(station_id: int, track_id: int) -> None:
    """Record what track Liquidsoap is actually playing.

    Called when Liquidsoap requests a track via /next-track.
    This allows /now-playing to show what's actually playing
    rather than what the deterministic timeline calculates.

    Args:
        station_id: Station ID
        track_id: Track ID being played
    """
    with get_radio_db_connection() as conn:
        conn.execute(
            """
            UPDATE radio_state
            SET last_track_id = ?,
                last_position_ms = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (track_id,),
        )
        conn.commit()
        logger.debug(f"Recorded now playing: station={station_id}, track={track_id}")


def get_actual_now_playing() -> Optional[tuple[int, datetime]]:
    """Get the track ID and start time of what's actually playing.

    Returns:
        Tuple of (track_id, started_at) or None if nothing playing
    """
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT last_track_id, updated_at
            FROM radio_state
            WHERE id = 1 AND last_track_id IS NOT NULL
            """
        )
        row = cursor.fetchone()
        if row and row["last_track_id"]:
            updated_at = row["updated_at"]
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            return (row["last_track_id"], updated_at)
        return None
