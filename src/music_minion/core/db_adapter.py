"""
Database adapter that supports both SQLite and PostgreSQL.

Uses DATABASE_URL environment variable to determine which backend to use:
- If DATABASE_URL starts with "postgres://", use PostgreSQL
- Otherwise, use SQLite (default behavior)
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Protocol, Union
from urllib.parse import urlparse

from loguru import logger


class CursorProtocol(Protocol):
    """Protocol for database cursor."""

    def execute(self, query: str, params: tuple = ()) -> "CursorProtocol": ...
    def executemany(self, query: str, params: list[tuple]) -> "CursorProtocol": ...
    def fetchone(self) -> Optional[dict[str, Any]]: ...
    def fetchall(self) -> list[dict[str, Any]]: ...
    @property
    def lastrowid(self) -> Optional[int]: ...
    @property
    def rowcount(self) -> int: ...
    def close(self) -> None: ...


class ConnectionProtocol(Protocol):
    """Protocol for database connection."""

    def execute(self, query: str, params: tuple = ()) -> CursorProtocol: ...
    def executemany(self, query: str, params: list[tuple]) -> CursorProtocol: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


def get_database_url() -> Optional[str]:
    """Get DATABASE_URL from environment."""
    return os.environ.get("DATABASE_URL")


def is_postgres() -> bool:
    """Check if using PostgreSQL."""
    url = get_database_url()
    return url is not None and url.startswith(("postgres://", "postgresql://"))


def _convert_query_placeholders(query: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL %s placeholders."""
    # Simple conversion - doesn't handle ? inside strings
    return query.replace("?", "%s")


class PostgresCursor:
    """Wrapper around psycopg2 cursor to provide dict-like row access."""

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self._columns: Optional[list[str]] = None

    def execute(self, query: str, params: tuple = ()) -> "PostgresCursor":
        # Convert SQLite placeholders to PostgreSQL
        pg_query = _convert_query_placeholders(query)
        self._cursor.execute(pg_query, params)
        if self._cursor.description:
            self._columns = [desc[0] for desc in self._cursor.description]
        return self

    def executemany(self, query: str, params: list[tuple]) -> "PostgresCursor":
        pg_query = _convert_query_placeholders(query)
        self._cursor.executemany(pg_query, params)
        return self

    def _row_to_dict(self, row: Optional[tuple]) -> Optional[dict[str, Any]]:
        if row is None or self._columns is None:
            return None
        return dict(zip(self._columns, row))

    def fetchone(self) -> Optional[dict[str, Any]]:
        row = self._cursor.fetchone()
        return self._row_to_dict(row)

    def fetchall(self) -> list[dict[str, Any]]:
        rows = self._cursor.fetchall()
        if not self._columns:
            return []
        return [dict(zip(self._columns, row)) for row in rows]

    @property
    def lastrowid(self) -> Optional[int]:
        # PostgreSQL doesn't have lastrowid, need to use RETURNING
        return getattr(self._cursor, 'lastrowid', None)

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def close(self) -> None:
        self._cursor.close()


class PostgresConnection:
    """Wrapper around psycopg2 connection."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, query: str, params: tuple = ()) -> PostgresCursor:
        cursor = PostgresCursor(self._conn.cursor())
        cursor.execute(query, params)
        return cursor

    def executemany(self, query: str, params: list[tuple]) -> PostgresCursor:
        cursor = PostgresCursor(self._conn.cursor())
        cursor.executemany(query, params)
        return cursor

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @property
    def total_changes(self) -> int:
        # PostgreSQL doesn't have total_changes
        return 0


@contextmanager
def get_radio_db_connection() -> Iterator[Union[sqlite3.Connection, PostgresConnection]]:
    """
    Get a database connection for the radio module.

    Uses DATABASE_URL if set (PostgreSQL), otherwise falls back to SQLite.
    """
    if is_postgres():
        import psycopg2

        url = get_database_url()
        logger.debug(f"Connecting to PostgreSQL")

        conn = psycopg2.connect(url)
        wrapped = PostgresConnection(conn)
        try:
            yield wrapped
        finally:
            wrapped.close()
    else:
        # Fall back to existing SQLite connection
        from .database import get_db_connection

        with get_db_connection() as conn:
            yield conn


def init_postgres_schema() -> None:
    """Initialize PostgreSQL schema for radio tables."""
    if not is_postgres():
        logger.debug("Not using PostgreSQL, skipping schema init")
        return

    import psycopg2

    url = get_database_url()
    logger.info("Initializing PostgreSQL schema for radio...")

    conn = psycopg2.connect(url)
    cursor = conn.cursor()

    # Create radio tables (PostgreSQL syntax)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            playlist_id INTEGER,
            mode TEXT NOT NULL DEFAULT 'shuffle',
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS station_schedule (
            id SERIAL PRIMARY KEY,
            station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            target_station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            position INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radio_history (
            id SERIAL PRIMARY KEY,
            station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
            track_id INTEGER,
            source_type TEXT NOT NULL,
            source_url TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            position_ms INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radio_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            active_station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
            started_at TIMESTAMP,
            last_track_id INTEGER,
            last_position_ms INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Initialize radio state
    cursor.execute("""
        INSERT INTO radio_state (id, active_station_id, last_position_ms)
        VALUES (1, NULL, 0)
        ON CONFLICT (id) DO NOTHING
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radio_skipped (
            id SERIAL PRIMARY KEY,
            station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            track_id INTEGER,
            source_url TEXT,
            skipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            skip_date DATE DEFAULT CURRENT_DATE,
            reason TEXT
        )
    """)

    # Create tracks table for PostgreSQL (simplified version for radio)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id SERIAL PRIMARY KEY,
            local_path TEXT,
            title TEXT,
            artist TEXT,
            album TEXT,
            genre TEXT,
            year INTEGER,
            duration REAL,
            key_signature TEXT,
            bpm REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create playlists table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'manual',
            description TEXT,
            track_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create playlist_tracks junction table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_tracks (
            id SERIAL PRIMARY KEY,
            playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
            track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (playlist_id, track_id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_station_schedule_station ON station_schedule(station_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_radio_history_station ON radio_history(station_id, started_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_radio_skipped_station_date ON radio_skipped(station_id, skip_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_local_path ON tracks(local_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id, position)")

    conn.commit()
    cursor.close()
    conn.close()

    logger.info("PostgreSQL schema initialized")
