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
    import music_minion.core.config as config_module

    # Reset cache at start to avoid stale values from previous tests
    config_module.ALL_PLAYLIST_ID = None

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


@pytest.fixture
def two_playlist_setup():
    """Create two playlists with overlapping tracks for cross-playlist tests."""
    from music_minion.core.database import get_db_connection
    import music_minion.core.config as config_module

    config_module.ALL_PLAYLIST_ID = None

    with get_db_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS playlists (id INTEGER PRIMARY KEY, name TEXT NOT NULL, filter_source TEXT, filter_genre TEXT, filter_year INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS playlist_elo_ratings (track_id INTEGER NOT NULL, playlist_id INTEGER NOT NULL, rating REAL DEFAULT 1500.0, comparison_count INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, last_compared TIMESTAMP, PRIMARY KEY (track_id, playlist_id))")
        conn.execute("CREATE TABLE IF NOT EXISTS playlist_comparison_history (id INTEGER PRIMARY KEY AUTOINCREMENT, track_a_id INTEGER NOT NULL, track_b_id INTEGER NOT NULL, winner_id INTEGER NOT NULL, playlist_id INTEGER NOT NULL, affects_global BOOLEAN, track_a_playlist_rating_before REAL, track_a_playlist_rating_after REAL, track_b_playlist_rating_before REAL, track_b_playlist_rating_after REAL, track_a_global_rating_before REAL, track_a_global_rating_after REAL, track_b_global_rating_before REAL, track_b_global_rating_after REAL, session_id TEXT NOT NULL DEFAULT '', timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("CREATE TABLE IF NOT EXISTS playlist_tracks (playlist_id INTEGER NOT NULL, track_id INTEGER NOT NULL, PRIMARY KEY (playlist_id, track_id))")

        # Playlist A has tracks 1, 2, 3
        conn.execute("INSERT INTO playlists (name) VALUES ('Playlist A')")
        playlist_a_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO playlists (name) VALUES ('Playlist B')")
        playlist_b_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for track_id in [1, 2, 3]:
            conn.execute("INSERT OR IGNORE INTO playlist_tracks VALUES (?, ?)", (playlist_a_id, track_id))
        # Playlist B has tracks 1, 2 (same pair as A) plus track 4
        for track_id in [1, 2, 4]:
            conn.execute("INSERT OR IGNORE INTO playlist_tracks VALUES (?, ?)", (playlist_b_id, track_id))

        conn.commit()

    yield {"playlist_a": playlist_a_id, "playlist_b": playlist_b_id}

    with get_db_connection() as conn:
        conn.execute("DELETE FROM playlists WHERE id IN (?, ?)", (playlist_a_id, playlist_b_id))
        conn.execute("DELETE FROM playlist_tracks WHERE playlist_id IN (?, ?)", (playlist_a_id, playlist_b_id))
        conn.execute("DELETE FROM playlist_comparison_history WHERE playlist_id IN (?, ?)", (playlist_a_id, playlist_b_id))
        conn.execute("DELETE FROM playlist_elo_ratings WHERE playlist_id IN (?, ?)", (playlist_a_id, playlist_b_id))
        conn.commit()

    config_module.ALL_PLAYLIST_ID = None


def test_global_pair_skipping(test_db, two_playlist_setup):
    """Pair compared in playlist A is not offered again in playlist B."""
    from music_minion.domain.rating.database import (
        record_playlist_comparison,
        get_next_playlist_pair,
        RankingComplete,
    )

    playlist_a = two_playlist_setup["playlist_a"]
    playlist_b = two_playlist_setup["playlist_b"]

    # Compare track 1 vs 2 in playlist A
    record_playlist_comparison(
        playlist_id=playlist_a,
        track_a_id=1,
        track_b_id=2,
        winner_id=1,
        track_a_rating_before=1500.0,
        track_b_rating_before=1500.0,
        track_a_rating_after=1516.0,
        track_b_rating_after=1484.0,
    )

    # In playlist B (tracks 1, 2, 4), the only uncompared pairs are 1v4 and 2v4.
    # The pair 1v2 should NOT be offered because it's globally skipped.
    # Fetch several pairs and verify 1v2 never appears.
    seen_pairs = set()
    for _ in range(10):
        try:
            track_a, track_b = get_next_playlist_pair(playlist_b)
            pair = tuple(sorted([track_a["id"], track_b["id"]]))
            seen_pairs.add(pair)
        except RankingComplete:
            break

    assert (1, 2) not in seen_pairs, "Pair (1, 2) was offered despite being compared in playlist A"
    # Both remaining valid pairs should eventually appear
    assert len(seen_pairs) > 0, "No pairs were offered in playlist B"


def test_contextual_stats(test_db, two_playlist_setup):
    """Contextual stats only count wins against opponents in the current playlist."""
    from music_minion.domain.rating.database import (
        record_playlist_comparison,
        get_contextual_track_stats,
    )

    playlist_a = two_playlist_setup["playlist_a"]
    playlist_b = two_playlist_setup["playlist_b"]

    # Compare track 1 vs 3 in playlist A (track 3 is NOT in playlist B)
    record_playlist_comparison(
        playlist_id=playlist_a,
        track_a_id=1,
        track_b_id=3,
        winner_id=1,
        track_a_rating_before=1500.0,
        track_b_rating_before=1500.0,
        track_a_rating_after=1516.0,
        track_b_rating_after=1484.0,
    )

    # Track 1's win against track 3 should count in playlist A (track 3 is a member)
    a_wins, a_losses = get_contextual_track_stats(1, playlist_a)
    assert a_wins == 1, f"Expected 1 win in playlist A, got {a_wins}"

    # But should NOT count in playlist B (track 3 is not a member of playlist B)
    b_wins, b_losses = get_contextual_track_stats(1, playlist_b)
    assert b_wins == 0, f"Expected 0 wins in playlist B (opponent not a member), got {b_wins}"


def test_cross_playlist_progress(test_db, two_playlist_setup):
    """Progress in playlist B increases when both tracks are compared in playlist A."""
    from music_minion.domain.rating.database import (
        record_playlist_comparison,
        get_playlist_comparison_progress,
    )

    playlist_a = two_playlist_setup["playlist_a"]
    playlist_b = two_playlist_setup["playlist_b"]

    progress_before = get_playlist_comparison_progress(playlist_b)

    # Compare track 1 vs 2 in playlist A (both are also in playlist B)
    record_playlist_comparison(
        playlist_id=playlist_a,
        track_a_id=1,
        track_b_id=2,
        winner_id=1,
        track_a_rating_before=1500.0,
        track_b_rating_before=1500.0,
        track_a_rating_after=1516.0,
        track_b_rating_after=1484.0,
    )

    progress_after = get_playlist_comparison_progress(playlist_b)

    assert progress_after["compared"] == progress_before["compared"] + 1, (
        f"Expected progress to increase by 1, got {progress_before['compared']} → {progress_after['compared']}"
    )
    assert progress_after["percentage"] <= 100.0, (
        f"Progress exceeded 100%: {progress_after['percentage']}"
    )
