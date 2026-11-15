"""Tests for DJ-set metadata on playlists (soundcloud_url, recording, emoji)."""

import pytest
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection
from music_minion.domain.playlists.crud import create_playlist
from web.backend.main import app

client = TestClient(app)

SET_FIELDS = ("soundcloud_url", "recording_track_id", "emoji_id")


@pytest.fixture
def recording_id() -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (title, artist, local_path, source)"
            " VALUES ('Mix', 'Kevin', '/music/mix.mp3', 'local')"
        )
        conn.commit()
        return cursor.lastrowid


def _listed(playlist_id: int) -> dict:
    playlists = client.get("/api/playlists").json()["playlists"]
    return next(p for p in playlists if p["id"] == playlist_id)


def test_new_playlist_returns_null_set_fields() -> None:
    created = client.post("/api/playlists", json={"name": "Fresh"}).json()
    assert all(created[field] is None for field in SET_FIELDS)
    assert all(_listed(created["id"])[field] is None for field in SET_FIELDS)


def test_patch_sets_fields_and_list_returns_them(recording_id: int) -> None:
    playlist_id = create_playlist("Friday Set", playlist_type="manual")
    body = {
        "soundcloud_url": "https://soundcloud.com/kevin/friday-set",
        "recording_track_id": recording_id,
        "emoji_id": "custom_disco",
    }

    response = client.patch(f"/api/playlists/{playlist_id}", json=body)

    assert response.status_code == 200
    assert {k: response.json()[k] for k in SET_FIELDS} == body
    assert {k: _listed(playlist_id)[k] for k in SET_FIELDS} == body


def test_patch_only_touches_sent_fields(recording_id: int) -> None:
    playlist_id = create_playlist("Partial", playlist_type="manual")
    client.patch(
        f"/api/playlists/{playlist_id}",
        json={"emoji_id": "🔥", "recording_track_id": recording_id},
    )

    response = client.patch(f"/api/playlists/{playlist_id}", json={"emoji_id": None})

    assert response.json()["emoji_id"] is None
    assert response.json()["recording_track_id"] == recording_id


def test_patch_unknown_recording_track_is_400() -> None:
    playlist_id = create_playlist("Bad Rec", playlist_type="manual")
    response = client.patch(
        f"/api/playlists/{playlist_id}", json={"recording_track_id": 999999}
    )
    assert response.status_code == 400


def test_patch_missing_playlist_is_404() -> None:
    response = client.patch("/api/playlists/999999", json={"emoji_id": "🔥"})
    assert response.status_code == 404


def test_organizer_track_payload_includes_emojis(recording_id: int) -> None:
    """The organizer card reads emojis from /playlists/{id}/tracks."""
    playlist_id = create_playlist("Emoji Set", playlist_type="manual")
    client.post(f"/api/playlists/{playlist_id}/tracks/{recording_id}")
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO track_emojis (id, track_id, emoji_id) VALUES ('e1', ?, '🔥')",
            (recording_id,),
        )
        conn.commit()

    tracks = client.get(f"/api/playlists/{playlist_id}/tracks?limit=10000").json()
    assert tracks.get("tracks"), tracks
    assert tracks["tracks"][0]["emojis"] == ["🔥"]


def test_deleting_recording_track_nulls_the_link(recording_id: int) -> None:
    playlist_id = create_playlist("Rec Gone", playlist_type="manual")
    client.patch(
        f"/api/playlists/{playlist_id}", json={"recording_track_id": recording_id}
    )

    with get_db_connection() as conn:
        conn.execute("DELETE FROM tracks WHERE id = ?", (recording_id,))
        conn.commit()

    assert _listed(playlist_id)["recording_track_id"] is None
