"""Tests for adding/removing a track to/from a playlist."""

import pytest
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from music_minion.domain.playlists.crud import create_playlist
from web.backend.main import app

client = TestClient(app)


@pytest.fixture
def track_id() -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (title, artist, local_path, source)"
            " VALUES ('Song', 'Artist', '/music/song.mp3', 'local')"
        )
        conn.commit()
        return cursor.lastrowid


def test_add_list_remove_roundtrip(track_id: int) -> None:
    playlist_id = create_playlist("Set Ideas", playlist_type="manual")

    assert client.post(f"/api/playlists/{playlist_id}/tracks/{track_id}").status_code == 200
    listed = client.get(f"/api/tracks/{track_id}/playlists").json()
    assert listed == [{"id": playlist_id, "name": "Set Ideas"}]

    assert client.delete(f"/api/playlists/{playlist_id}/tracks/{track_id}").status_code == 200
    assert client.get(f"/api/tracks/{track_id}/playlists").json() == []


def test_add_twice_conflicts(track_id: int) -> None:
    playlist_id = create_playlist("Dupes", playlist_type="manual")
    client.post(f"/api/playlists/{playlist_id}/tracks/{track_id}")
    response = client.post(f"/api/playlists/{playlist_id}/tracks/{track_id}")
    assert response.status_code == 409


def test_smart_playlist_rejected(track_id: int) -> None:
    playlist_id = create_playlist("Smart One", playlist_type="smart")
    response = client.post(f"/api/playlists/{playlist_id}/tracks/{track_id}")
    assert response.status_code == 400
    assert "smart" in response.json()["detail"]


def test_missing_playlist_404(track_id: int) -> None:
    assert client.post(f"/api/playlists/999999/tracks/{track_id}").status_code == 404


def test_local_playlist_rejects_track_without_file() -> None:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (title, artist, soundcloud_id, source)"
            " VALUES ('SC Only', 'Artist', '12345', 'soundcloud')"
        )
        conn.commit()
        sc_track_id = cursor.lastrowid
    playlist_id = create_playlist("Serato Set", playlist_type="manual", library="local")

    response = client.post(f"/api/playlists/{playlist_id}/tracks/{sc_track_id}")
    assert response.status_code == 400
    assert "no local file" in response.json()["detail"]


def test_create_playlist_honors_library() -> None:
    response = client.post("/api/playlists", json={"name": "Pinned Local", "library": "local"})
    assert response.status_code == 200
    assert response.json()["library"] == "local"
