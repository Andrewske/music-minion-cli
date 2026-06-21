"""
Regression tests for playlist track_count: get_all_playlists must report the
LIVE count from playlist_tracks, not the denormalized playlists.track_count
column (which can drift when a write path forgets to update it).
"""

import tempfile
from pathlib import Path

import pytest

from music_minion.core.database import get_db_connection, get_database_path
from music_minion.domain.playlists.crud import get_all_playlists


@pytest.fixture
def test_db():
    """Temp DB with minimal playlists + playlist_tracks schema."""
    import music_minion.core.database as db_module

    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = Path(temp_db.name)
    temp_db.close()

    original_get_db_path = db_module.get_database_path
    db_module.get_database_path = lambda: temp_db_path

    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE playlists (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'manual',
                description TEXT,
                track_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                last_played_at TEXT,
                library TEXT NOT NULL DEFAULT 'local',
                pin_order INTEGER,
                soundcloud_playlist_id TEXT,
                discovery_source TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE playlist_tracks (
                playlist_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                position INTEGER NOT NULL
            )
            """
        )
        conn.commit()

    try:
        yield temp_db_path
    finally:
        db_module.get_database_path = original_get_db_path
        if temp_db_path.exists():
            temp_db_path.unlink()


def _insert_playlist(name: str, stored_count: int) -> int:
    """Insert a playlist with a deliberately wrong stored track_count."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO playlists (name, type, track_count, library) VALUES (?, 'manual', ?, 'local')",
            (name, stored_count),
        )
        conn.commit()
        return cursor.lastrowid


def _add_tracks(playlist_id: int, track_ids: list[int]) -> None:
    with get_db_connection() as conn:
        conn.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            [(playlist_id, tid, i) for i, tid in enumerate(track_ids)],
        )
        conn.commit()


def test_get_all_playlists_uses_live_count(test_db):
    """Live count from playlist_tracks must win over a stale stored column."""
    pid = _insert_playlist("drifted", stored_count=99)
    _add_tracks(pid, [1, 2, 3])

    playlists = get_all_playlists(library="local")

    row = next(p for p in playlists if p["id"] == pid)
    assert row["track_count"] == 3  # live, not the poisoned 99


def test_get_all_playlists_empty_playlist_counts_zero(test_db):
    """A playlist with no rows reports 0 even if the stored column lies."""
    pid = _insert_playlist("empty", stored_count=50)

    playlists = get_all_playlists(library="local")

    row = next(p for p in playlists if p["id"] == pid)
    assert row["track_count"] == 0
