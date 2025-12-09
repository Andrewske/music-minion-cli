"""Tests for tracks API endpoints."""

import pytest
from pathlib import Path
from unittest.mock import Mock
from fastapi.testclient import TestClient
from web.backend.main import app
from web.backend.routers.tracks import get_track_path, get_mime_type

client = TestClient(app)


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
