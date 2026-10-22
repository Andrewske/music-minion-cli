"""Tests for database functions."""

import pytest

from music_minion.core.database import (
    SCHEMA_VERSION,
    get_db_connection,
    get_unique_genres,
    init_database,
)


def test_get_unique_genres() -> None:
    """Counts genres, skips NULL/empty, sorts by count desc."""
    genres = ["House", "Techno", "House", "DnB", "House", "Techno", None, ""]
    with get_db_connection() as conn:
        conn.executemany(
            "INSERT INTO tracks (title, genre) VALUES (?, ?)",
            [(f"t{i}", g) for i, g in enumerate(genres)],
        )
        conn.commit()

    assert get_unique_genres() == [("House", 3), ("Techno", 2), ("DnB", 1)]


def _set_schema_version(version: int) -> None:
    with get_db_connection() as conn:
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()


def _schema_version() -> int:
    with get_db_connection() as conn:
        return conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]


def test_init_database_refuses_newer_schema() -> None:
    """Older code must not stamp its version over a DB newer code migrated."""
    _set_schema_version(SCHEMA_VERSION + 1)

    with pytest.raises(RuntimeError, match=f"v{SCHEMA_VERSION + 1}"):
        init_database()

    assert _schema_version() == SCHEMA_VERSION + 1


def test_init_database_accepts_current_schema() -> None:
    init_database()

    assert _schema_version() == SCHEMA_VERSION
