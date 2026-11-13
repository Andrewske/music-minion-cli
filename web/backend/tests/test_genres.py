"""Tests for genre API endpoints."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.id3 import ID3

from music_minion.core.config import Config, MusicConfig
from music_minion.core.database import get_db_connection
from web.backend.deps import get_config
from web.backend.main import app

client = TestClient(app)


def test_create_genre_normalizes_name() -> None:
    response = client.post("/api/genres", json={"name": "  Deep House "})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "deep house"
    assert body["track_count"] == 0


def test_create_genre_returns_existing_on_duplicate() -> None:
    first = client.post("/api/genres", json={"name": "Garage"}).json()
    second = client.post("/api/genres", json={"name": "GARAGE"}).json()
    assert second["id"] == first["id"]


def test_create_genre_rejects_blank_name() -> None:
    response = client.post("/api/genres", json={"name": "   "})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


# One silent MPEG-1 Layer III frame (128 kbps, 44.1 kHz) so mutagen sees a real MP3
_MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 413


@pytest.fixture
def mp3_track(tmp_path: Path) -> Iterator[tuple[int, Path]]:
    path = tmp_path / "song.mp3"
    path.write_bytes(_MP3_FRAME * 10)
    app.dependency_overrides[get_config] = lambda: Config(
        music=MusicConfig(library_paths=[str(tmp_path)])
    )
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (title, local_path, source, file_mtime) VALUES ('G', ?, 'local', 0)",
            (str(path),),
        )
        conn.commit()
    yield cursor.lastrowid, path
    app.dependency_overrides.pop(get_config, None)


def _genre_id(name: str) -> int:
    return client.post("/api/genres", json={"name": name}).json()["id"]


def test_set_genres_writes_primary_to_file_in_library_casing(mp3_track: tuple[int, Path]) -> None:
    track_id, path = mp3_track
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO tracks (title, genre, source) VALUES ('Other', 'Drum & Bass', 'soundcloud')"
        )
        conn.commit()
    ids = [_genre_id("drum & bass"), _genre_id("liquid")]

    response = client.put(f"/api/tracks/{track_id}/genres", json={"genre_ids": ids})

    assert response.status_code == 200
    assert [g["name"] for g in response.json()] == ["drum & bass", "liquid"]
    assert str(ID3(path)["TCON"]) == "Drum & Bass"
    with get_db_connection() as conn:
        row = conn.execute("SELECT genre, file_mtime FROM tracks WHERE id = ?", (track_id,)).fetchone()
    assert row["genre"] == "Drum & Bass"
    assert row["file_mtime"] == pytest.approx(path.stat().st_mtime)


def test_new_genre_is_title_cased_in_file(mp3_track: tuple[int, Path]) -> None:
    track_id, path = mp3_track
    client.put(f"/api/tracks/{track_id}/genres", json={"genre_ids": [_genre_id("wave trap")]})
    assert str(ID3(path)["TCON"]) == "Wave Trap"


def test_failed_file_write_leaves_genres_unchanged(mp3_track: tuple[int, Path]) -> None:
    track_id, path = mp3_track
    path.write_bytes(b"not audio")

    response = client.put(f"/api/tracks/{track_id}/genres", json={"genre_ids": [_genre_id("garage")]})

    assert response.status_code == 500
    assert "genres unchanged" in response.json()["detail"]
    assert client.get(f"/api/tracks/{track_id}/genres").json() == []


def test_track_without_file_updates_db_only() -> None:
    with get_db_connection() as conn:
        cursor = conn.execute("INSERT INTO tracks (title, source) VALUES ('SC', 'soundcloud')")
        conn.commit()
    response = client.put(
        f"/api/tracks/{cursor.lastrowid}/genres", json={"genre_ids": [_genre_id("phonk")]}
    )
    assert response.status_code == 200
    assert response.json()[0]["name"] == "phonk"
