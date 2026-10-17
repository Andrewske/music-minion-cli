"""
Regression test: CSV import (_upsert_tracks_to_playlist) must commit its track
writes and add tracks to the playlist on the SAME connection. Previously the
INSERT/UPDATEs were never committed and add_track_to_playlist opened a second
connection, so new tracks were invisible to it and counted as duplicates.
"""

from pathlib import Path

import pytest

import music_minion.core.database as db_module
from music_minion.core.database import get_db_connection, init_database
from music_minion.domain.playlists.crud import create_playlist
from music_minion.domain.playlists.importers import _upsert_tracks_to_playlist


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "music_minion.db"
    monkeypatch.setattr(db_module, "get_database_path", lambda: db_path)
    init_database()
    return db_path


def test_upsert_adds_new_tracks_and_commits(temp_db: Path) -> None:
    playlist_id = create_playlist(name="csv-test", playlist_type="manual")
    tracks = [
        {"local_path": "/music/a.mp3", "title": "A", "artist": "X"},
        {"local_path": "/music/b.mp3", "title": "B", "artist": "Y"},
    ]

    added, dupes = _upsert_tracks_to_playlist(playlist_id, tracks)

    assert (added, dupes) == (2, 0)
    with get_db_connection() as conn:
        n_tracks = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        n_members = conn.execute(
            "SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()[0]
    assert n_tracks == 2
    assert n_members == 2


def test_upsert_existing_track_update_is_committed(temp_db: Path) -> None:
    playlist_id = create_playlist(name="csv-test-2", playlist_type="manual")
    _upsert_tracks_to_playlist(playlist_id, [{"local_path": "/music/a.mp3", "title": "Old"}])

    added, dupes = _upsert_tracks_to_playlist(
        playlist_id, [{"local_path": "/music/a.mp3", "title": "New"}]
    )

    assert (added, dupes) == (0, 1)
    with get_db_connection() as conn:
        title = conn.execute(
            "SELECT title FROM tracks WHERE local_path = ?", ("/music/a.mp3",)
        ).fetchone()[0]
    assert title == "New"
