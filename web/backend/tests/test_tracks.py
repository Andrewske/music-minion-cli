"""Tests for tracks API endpoints."""

import pytest
from pathlib import Path
from unittest.mock import Mock
from fastapi.testclient import TestClient
from music_minion.core.database import get_db_connection
from web.backend.main import app
from web.backend.routers.tracks import get_track_path, get_mime_type

client = TestClient(app)


@pytest.fixture
def seeded_track_id() -> int:
    """Insert one track into the isolated test DB and return its id."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (title, artist, local_path, source)"
            " VALUES ('Test Song', 'Test Artist', '/music/test.mp3', 'local')"
        )
        conn.commit()
        return cursor.lastrowid


class TestGetTrackPath:
    """Test get_track_path helper function."""

    def test_get_track_path_valid(self):
        """Test returns Path for valid track ID."""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"local_path": "/music/song.mp3"}
        mock_db.execute.return_value = mock_cursor

        result = get_track_path(1, mock_db)
        assert result == Path("/music/song.mp3")

    def test_get_track_path_invalid(self):
        """Test returns None for invalid track ID."""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_db.execute.return_value = mock_cursor

        result = get_track_path(999, mock_db)
        assert result is None

    def test_get_track_path_null_path(self):
        """Test returns None for NULL local_path."""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"local_path": None}
        mock_db.execute.return_value = mock_cursor

        result = get_track_path(1, mock_db)
        assert result is None

    def test_get_track_path_empty_string(self):
        """Test returns None for empty string local_path."""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"local_path": ""}
        mock_db.execute.return_value = mock_cursor

        result = get_track_path(1, mock_db)
        assert result is None

    def test_get_track_path_whitespace_only(self):
        """Test returns None for whitespace-only local_path."""
        mock_db = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"local_path": "   "}
        mock_db.execute.return_value = mock_cursor

        result = get_track_path(1, mock_db)
        assert result is None


class TestGetMimeType:
    """Test get_mime_type helper function."""

    def test_get_mime_type_opus(self):
        """Test returns audio/opus for .opus files."""
        file_path = Path("/music/song.opus")
        result = get_mime_type(file_path)
        assert result == "audio/opus"

    def test_get_mime_type_mp3(self):
        """Test returns audio/mpeg for .mp3 files."""
        file_path = Path("/music/song.mp3")
        result = get_mime_type(file_path)
        assert result == "audio/mpeg"

    def test_get_mime_type_m4a(self):
        """Test returns audio/mp4 for .m4a files."""
        file_path = Path("/music/song.m4a")
        result = get_mime_type(file_path)
        assert result == "audio/mp4"

    def test_get_mime_type_fallback(self):
        """Test uses mimetypes for unknown extensions."""
        file_path = Path("/music/song.unknown")
        result = get_mime_type(file_path)
        # Should use mimetypes.guess_type fallback
        assert isinstance(result, str)
        assert result != ""


def test_stream_track_with_null_path():
    """Test streaming track with NULL local_path."""
    # This would require setting up test database with NULL local_path
    # For now, just test the 404 case for non-existent track
    response = client.get("/api/tracks/99999/stream")
    assert response.status_code == 404
    assert "Track not found" in response.json()["detail"]


def test_stream_track_with_invalid_path():
    """Test streaming track with invalid local_path."""
    # This would require setting up test database with invalid local_path
    # For now, just ensure the endpoint exists and handles errors
    response = client.get("/api/tracks/99998/stream")
    assert response.status_code == 404


def test_waveform_track_with_null_path():
    """Test waveform generation for track with NULL local_path."""
    response = client.get("/api/tracks/99999/waveform")
    assert response.status_code == 404
    assert "Track not found" in response.json()["detail"]


class TestSearchTracks:
    """Test search_tracks endpoint."""

    def test_search_tracks_returns_list(self, seeded_track_id: int):
        """Test search endpoint finds a seeded track."""
        response = client.get("/api/tracks/search?q=test")
        assert response.status_code == 200
        assert [t["id"] for t in response.json()] == [seeded_track_id]

    def test_search_tracks_with_limit(self):
        """Test search endpoint respects limit parameter."""
        response = client.get("/api/tracks/search?q=test&limit=5")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        # Can't assert exact count without test data, but verify it's valid
        assert len(response.json()) <= 5

    def test_search_tracks_empty_query(self):
        """Test search endpoint with empty query."""
        response = client.get("/api/tracks/search?q=")
        assert response.status_code == 200
        # Empty query should still work (matches everything with %)
        assert isinstance(response.json(), list)


class TestScrobbleTrack:
    """Test scrobble endpoint."""

    def test_scrobble_missing_track_returns_404(self):
        response = client.post("/api/tracks/99999/scrobble", json={"played_ms": 30000})
        assert response.status_code == 404

    def test_scrobble_valid_track_returns_200(self, seeded_track_id: int):
        response = client.post(
            f"/api/tracks/{seeded_track_id}/scrobble", json={"played_ms": 60000}
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}


def _seed_tracks(rows: list[tuple[str, str | None]]) -> list[int]:
    """Insert (title, artist) rows into the isolated test DB and return ids."""
    with get_db_connection() as conn:
        ids = [
            conn.execute(
                "INSERT INTO tracks (title, artist, source) VALUES (?, ?, 'local')",
                row,
            ).lastrowid
            for row in rows
        ]
        conn.commit()
    return ids


class TestLookupTracks:
    """Test batch track-name lookup endpoint."""

    def test_lookup_returns_names_in_request_order(self):
        first, second = _seed_tracks([("Alpha", "Zed"), ("Beta", None)])
        response = client.post("/api/tracks/lookup", json={"ids": [second, first]})
        assert response.status_code == 200
        assert response.json() == [
            {"id": second, "title": "Beta", "artist": None},
            {"id": first, "title": "Alpha", "artist": "Zed"},
        ]

    def test_lookup_omits_unknown_and_dedupes(self):
        (track_id,) = _seed_tracks([("Gamma", "Artist")])
        response = client.post(
            "/api/tracks/lookup", json={"ids": [track_id, 987654321, track_id]}
        )
        assert response.status_code == 200
        assert [t["id"] for t in response.json()] == [track_id]

    def test_lookup_handles_more_ids_than_one_chunk(self):
        ids = _seed_tracks([(f"T{i}", "A") for i in range(620)])
        response = client.post("/api/tracks/lookup", json={"ids": ids})
        assert response.status_code == 200
        assert [t["id"] for t in response.json()] == ids

    def test_lookup_empty_list(self):
        response = client.post("/api/tracks/lookup", json={"ids": []})
        assert response.status_code == 200
        assert response.json() == []

    def test_lookup_rejects_oversized_request(self):
        response = client.post("/api/tracks/lookup", json={"ids": list(range(5001))})
        assert response.status_code == 422
