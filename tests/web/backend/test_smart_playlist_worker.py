"""Background smart playlist refresh and the refresh-on-read endpoints."""

from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from music_minion.domain.playlists import filters
from music_minion.domain.playlists.crud import create_playlist
from web.backend import smart_playlist_worker
from web.backend.main import app

client = TestClient(app)


def _setup() -> tuple[int, int]:
    """A 'dubstep' smart playlist and a house track outside it."""
    with get_db_connection() as conn:
        track_id = conn.execute(
            "INSERT INTO tracks (title, artist, genre, local_path, source)"
            " VALUES ('Song', 'Artist', 'house', '/music/song.mp3', 'local')"
        ).lastrowid
        conn.commit()
    playlist_id = create_playlist("Dub", playlist_type="smart", library="local")
    filters.add_filter(playlist_id, "genre", "equals", "dubstep")
    return playlist_id, track_id


def _retag(track_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute("UPDATE tracks SET genre = 'dubstep' WHERE id = ?", (track_id,))
        conn.commit()


def _members(playlist_id: int) -> list[int]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT track_id FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,)
        ).fetchall()
    return [r[0] for r in rows]


def test_tick_refreshes_stale_playlists() -> None:
    playlist_id, track_id = _setup()
    _retag(track_id)

    assert smart_playlist_worker.run_tick() >= 1
    assert _members(playlist_id) == [track_id]
    assert smart_playlist_worker.run_tick() == 0


def test_tracks_endpoint_refreshes_stale_playlist() -> None:
    playlist_id, track_id = _setup()
    _retag(track_id)

    body = client.get(f"/api/playlists/{playlist_id}/tracks").json()

    assert [t["id"] for t in body["tracks"]] == [track_id]


def test_playlist_list_endpoint_refreshes_counts() -> None:
    playlist_id, track_id = _setup()
    _retag(track_id)

    playlists = client.get("/api/playlists", params={"library": "local"}).json()[
        "playlists"
    ]

    assert next(p for p in playlists if p["id"] == playlist_id)["track_count"] == 1
