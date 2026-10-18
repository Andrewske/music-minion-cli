"""Tests for database functions."""

from music_minion.core.database import get_db_connection, get_unique_genres


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
