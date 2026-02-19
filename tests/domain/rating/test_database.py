"""
Tests for rating database functions.
"""

import pytest
import sqlite3
from pathlib import Path
import tempfile
import os

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


# Legacy tests commented out - get_filtered_tracks was removed from database.py
# def test_get_filtered_tracks_excludes_null_paths(test_db):
#     """Verify tracks with NULL local_path are excluded."""
#     tracks = get_filtered_tracks()
#
#     # Should only return tracks 1, 2, 7 (valid local paths)
#     assert len(tracks) == 3, f"Expected 3 tracks, got {len(tracks)}"
#
#     # Verify all returned tracks have non-null, non-empty paths
#     for track in tracks:
#         assert track["local_path"], f"Track {track['id']} has invalid path"
#         assert track["local_path"].strip(), f"Track {track['id']} has whitespace path"
#
#     # Verify specific tracks are included/excluded
#     track_ids = {track["id"] for track in tracks}
#     assert track_ids == {1, 2, 7}, f"Expected {{1, 2, 7}}, got {track_ids}"
#
#
# def test_get_filtered_tracks_with_filters_still_excludes_null_paths(test_db):
#     """Verify NULL path filtering works with other filters."""
#     # This would return all tracks if not for NULL path filter
#     tracks = get_filtered_tracks(source_filter="local")
#
#     # Should only return tracks 1, 2, 7 (source='local' AND valid path)
#     assert len(tracks) == 3
#
#     # Verify tracks 5 and 6 (empty/whitespace paths) are excluded
#     track_ids = {track["id"] for track in tracks}
#     assert 5 not in track_ids, "Track 5 (empty path) should be excluded"
#     assert 6 not in track_ids, "Track 6 (whitespace path) should be excluded"
#
#
# def test_get_filtered_tracks_default_ratings(test_db):
#     """Verify tracks without elo_ratings get default 1500.0 rating."""
#     tracks = get_filtered_tracks()
#
#     # All tracks should have default rating of 1500.0 since we didn't insert ratings
#     for track in tracks:
#         assert track["rating"] == 1500.0, f"Track {track['id']} has wrong default rating"
#         assert (
#             track["comparison_count"] == 0
#         ), f"Track {track['id']} has wrong default comparison_count"


def test_record_comparison_column_names():
    """Verify INSERT uses correct column names matching schema."""
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute('PRAGMA table_info(playlist_comparison_history)')
        cols = {row['name'] for row in cursor.fetchall()}

    required = {
        'track_a_playlist_rating_before',
        'track_a_playlist_rating_after',
        'track_b_playlist_rating_before',
        'track_b_playlist_rating_after',
        'affects_global',
    }
    assert required.issubset(cols), f"Missing columns: {required - cols}"


@pytest.fixture
def test_playlist():
    """Create a test playlist for comparison tests."""
    from music_minion.core.database import get_db_connection
    from dataclasses import dataclass

    @dataclass
    class TestPlaylist:
        id: int

    with get_db_connection() as conn:
        # Ensure playlists table exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                filter_source TEXT,
                filter_genre TEXT,
                filter_year INTEGER
            )
            """
        )

        # Create "All" playlist (required by record_playlist_comparison)
        conn.execute(
            "INSERT OR IGNORE INTO playlists (name) VALUES ('All')"
        )

        # Create test playlist
        cursor = conn.execute(
            "INSERT INTO playlists (name) VALUES ('Test Playlist')"
        )
        playlist_id = cursor.lastrowid

        # Ensure playlist_elo_ratings table exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS playlist_elo_ratings (
                track_id INTEGER NOT NULL,
                playlist_id INTEGER NOT NULL,
                rating REAL DEFAULT 1500.0,
                comparison_count INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                last_compared TIMESTAMP,
                PRIMARY KEY (track_id, playlist_id)
            )
            """
        )

        # Ensure playlist_comparison_history table exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS playlist_comparison_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_a_id INTEGER NOT NULL,
                track_b_id INTEGER NOT NULL,
                winner_id INTEGER NOT NULL,
                playlist_id INTEGER NOT NULL,
                affects_global BOOLEAN,
                track_a_playlist_rating_before REAL,
                track_a_playlist_rating_after REAL,
                track_b_playlist_rating_before REAL,
                track_b_playlist_rating_after REAL,
                track_a_global_rating_before REAL,
                track_a_global_rating_after REAL,
                track_b_global_rating_before REAL,
                track_b_global_rating_after REAL,
                session_id TEXT NOT NULL DEFAULT '',
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()

    yield TestPlaylist(id=playlist_id)

    # Cleanup
    with get_db_connection() as conn:
        conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.execute("DELETE FROM playlists WHERE name = 'All'")
        conn.execute("DELETE FROM playlist_elo_ratings WHERE playlist_id = ?", (playlist_id,))
        conn.execute("DELETE FROM playlist_comparison_history WHERE playlist_id = ?", (playlist_id,))
        conn.commit()

    # Reset All playlist ID cache
    import music_minion.core.config as config_module
    config_module.ALL_PLAYLIST_ID = None


def test_record_comparison_basic(test_db, test_playlist):
    """Basic recording works without error."""
    from music_minion.domain.rating.database import record_playlist_comparison

    # Should not raise
    record_playlist_comparison(
        playlist_id=test_playlist.id,
        track_a_id=1,
        track_b_id=2,
        winner_id=1,
        track_a_rating_before=1500.0,
        track_b_rating_before=1500.0,
        track_a_rating_after=1516.0,
        track_b_rating_after=1484.0,
    )
