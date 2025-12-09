"""
Tests for rating database functions, specifically NULL local_path filtering.
"""

import pytest
import sqlite3
from pathlib import Path
import tempfile
import os

from music_minion.domain.rating.database import get_filtered_tracks
from music_minion.core.database import get_db_connection, get_database_path


@pytest.fixture
def test_db():
    """Create a temporary test database with sample tracks."""
    # Use a temporary database for testing
    original_db_path = get_database_path()
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = Path(temp_db.name)
    temp_db.close()

    # Override database path for testing
    import music_minion.core.database as db_module

    original_get_db_path = db_module.get_database_path
    db_module.get_database_path = lambda: temp_db_path

    # Create schema and insert test data
    with get_db_connection() as conn:
        # Create minimal tracks table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT,
                genre TEXT,
                year INTEGER,
                bpm INTEGER,
                local_path TEXT,
                soundcloud_id TEXT,
                spotify_id TEXT,
                youtube_id TEXT,
                source TEXT DEFAULT 'local',
                duration REAL
            )
        """
        )

        # Create elo_ratings table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS elo_ratings (
                track_id INTEGER PRIMARY KEY,
                rating REAL DEFAULT 1500.0,
                comparison_count INTEGER DEFAULT 0
            )
        """
        )

        # Insert test tracks
        test_tracks = [
            # Valid tracks with local paths
            (1, "Track 1", "Artist A", "/path/to/track1.mp3", "local"),
            (2, "Track 2", "Artist B", "/path/to/track2.opus", "local"),
            # Invalid tracks (NULL local_path)
            (3, "Track 3", "Artist C", None, "soundcloud"),
            (4, "Track 4", "Artist D", None, "spotify"),
            # Invalid track (empty string local_path)
            (5, "Track 5", "Artist E", "", "local"),
            # Valid track with whitespace path (should be filtered)
            (6, "Track 6", "Artist F", "   ", "local"),
            # More valid tracks
            (7, "Track 7", "Artist G", "/path/to/track7.m4a", "local"),
        ]

        conn.executemany(
            """
            INSERT INTO tracks (id, title, artist, local_path, source)
            VALUES (?, ?, ?, ?, ?)
        """,
            test_tracks,
        )

        conn.commit()

    yield temp_db_path

    # Cleanup
    db_module.get_database_path = original_get_db_path
    os.unlink(temp_db_path)


def test_get_filtered_tracks_excludes_null_paths(test_db):
    """Verify tracks with NULL local_path are excluded."""
    tracks = get_filtered_tracks()

    # Should only return tracks 1, 2, 7 (valid local paths)
    assert len(tracks) == 3, f"Expected 3 tracks, got {len(tracks)}"

    # Verify all returned tracks have non-null, non-empty paths
    for track in tracks:
        assert track["local_path"], f"Track {track['id']} has invalid path"
        assert track["local_path"].strip(), f"Track {track['id']} has whitespace path"

    # Verify specific tracks are included/excluded
    track_ids = {track["id"] for track in tracks}
    assert track_ids == {1, 2, 7}, f"Expected {{1, 2, 7}}, got {track_ids}"


def test_get_filtered_tracks_with_filters_still_excludes_null_paths(test_db):
    """Verify NULL path filtering works with other filters."""
    # This would return all tracks if not for NULL path filter
    tracks = get_filtered_tracks(source_filter="local")

    # Should only return tracks 1, 2, 7 (source='local' AND valid path)
    assert len(tracks) == 3

    # Verify tracks 5 and 6 (empty/whitespace paths) are excluded
    track_ids = {track["id"] for track in tracks}
    assert 5 not in track_ids, "Track 5 (empty path) should be excluded"
    assert 6 not in track_ids, "Track 6 (whitespace path) should be excluded"


def test_get_filtered_tracks_default_ratings(test_db):
    """Verify tracks without elo_ratings get default 1500.0 rating."""
    tracks = get_filtered_tracks()

    # All tracks should have default rating of 1500.0 since we didn't insert ratings
    for track in tracks:
        assert track["rating"] == 1500.0, f"Track {track['id']} has wrong default rating"
        assert (
            track["comparison_count"] == 0
        ), f"Track {track['id']} has wrong default comparison_count"
