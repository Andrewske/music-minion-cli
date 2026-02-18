"""Comprehensive unit tests for queue_manager module.

Tests pure functional queue management: initialization, dynamic refilling,
shuffle toggling, and state persistence.
"""

import pytest
import sqlite3

# Import queue_manager - conftest.py handles the circular import setup
from backend import queue_manager
from conftest import MockPlayContext


@pytest.fixture
def test_db():
    """Create in-memory test database with sample tracks."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create minimal schema
    conn.execute("""
        CREATE TABLE tracks (
            id INTEGER PRIMARY KEY,
            title TEXT,
            artist TEXT,
            bpm INTEGER,
            year INTEGER,
            track_number INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE playlists (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE playlist_tracks (
            playlist_id INTEGER,
            track_id INTEGER,
            position INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE track_ratings (
            track_id INTEGER PRIMARY KEY,
            elo_rating INTEGER DEFAULT 1500
        )
    """)

    # Insert 200 test tracks
    for i in range(1, 201):
        conn.execute(
            "INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?)",
            (i, f"Track {i}", f"Artist {i % 10}", 120 + (i % 60), 2020 + (i % 5), i)
        )

    # Create test playlist with all tracks
    conn.execute("INSERT INTO playlists VALUES (1, 'Test Playlist', 'manual')")
    for i in range(1, 201):
        conn.execute(
            "INSERT INTO playlist_tracks VALUES (1, ?, ?)",
            (i, i)
        )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_context():
    """Mock PlayContext for testing.

    This matches the Pydantic model structure from routers.player but as a dataclass
    to avoid circular import issues during testing.
    """
    return MockPlayContext()


# Test: initialize_queue (shuffle mode)

def test_initialize_queue_shuffle_returns_correct_size(test_db, mock_context):
    """Should return requested window size for shuffle mode."""
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert len(queue) == 100
    assert all(isinstance(track_id, int) for track_id in queue)


def test_initialize_queue_shuffle_no_duplicates(test_db, mock_context):
    """Should not have duplicate tracks in initial queue."""
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert len(set(queue)) == 100  # All unique


def test_initialize_queue_small_playlist(test_db, mock_context):
    """Should handle playlists smaller than window size."""
    # Create small playlist
    test_db.execute("DELETE FROM playlist_tracks WHERE playlist_id = 1")
    for i in range(1, 21):  # Only 20 tracks
        test_db.execute("INSERT INTO playlist_tracks VALUES (1, ?, ?)", (i, i))
    test_db.commit()

    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert len(queue) == 20  # Returns all available tracks


# Test: initialize_queue (sorted mode)

def test_initialize_queue_sorted_by_bpm(test_db, mock_context):
    """Should return tracks sorted by BPM ascending."""
    sort_spec = {"field": "bpm", "direction": "asc"}
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    # Verify sorted order
    tracks = [test_db.execute("SELECT bpm FROM tracks WHERE id = ?", (tid,)).fetchone()["bpm"] for tid in queue]
    assert tracks == sorted(tracks)


def test_initialize_queue_sorted_descending(test_db, mock_context):
    """Should respect sort direction."""
    sort_spec = {"field": "year", "direction": "desc"}
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    tracks = [test_db.execute("SELECT year FROM tracks WHERE id = ?", (tid,)).fetchone()["year"] for tid in queue]
    assert tracks == sorted(tracks, reverse=True)


# Test: get_next_track (exclusions)

def test_get_next_track_respects_exclusions(test_db, mock_context):
    """Should never return excluded track IDs."""
    exclusions = list(range(1, 101))  # Exclude first 100 tracks

    for _ in range(10):  # Try 10 times
        track_id = queue_manager.get_next_track(mock_context, exclusions, test_db, shuffle=True)
        assert track_id not in exclusions
        assert track_id is not None


def test_get_next_track_returns_none_when_all_excluded(test_db, mock_context):
    """Should return None when all tracks are excluded."""
    exclusions = list(range(1, 201))  # All tracks

    track_id = queue_manager.get_next_track(mock_context, exclusions, test_db, shuffle=True)
    assert track_id is None


def test_get_next_track_sorted_mode_sequential(test_db, mock_context):
    """Should get next track in sorted sequence."""
    sort_spec = {"field": "bpm", "direction": "asc"}

    # Position at track 0, should get track at position 1
    track_id = queue_manager.get_next_track(
        mock_context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=0
    )

    # Should get second track in sorted order
    assert track_id is not None

    # At last position, should return None (no wrap-around)
    track_id_end = queue_manager.get_next_track(
        mock_context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=199
    )
    assert track_id_end is None  # End of playlist


# Test: rebuild_queue

def test_rebuild_queue_preserves_history(test_db, mock_context):
    """Should preserve played tracks and current track."""
    original_queue = list(range(1, 101))  # Tracks 1-100
    queue_index = 50  # Played first 50 tracks
    current_track_id = 51

    new_queue = queue_manager.rebuild_queue(
        mock_context, current_track_id, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # History preserved: tracks 1-51
    assert new_queue[0:51] == original_queue[0:51]

    # New tracks appended (should be ~49 new tracks)
    assert len(new_queue) >= 100


def test_rebuild_queue_generates_new_future(test_db, mock_context):
    """Should generate different tracks ahead after rebuild."""
    original_queue = list(range(1, 101))
    queue_index = 50

    new_queue = queue_manager.rebuild_queue(
        mock_context, 51, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # Future tracks should be different (not guaranteed but very likely with 200 total)
    future_original = original_queue[51:]
    future_new = new_queue[51:]

    assert future_original != future_new


# Test: Persistence (save/load round-trip)

def test_save_load_queue_state_round_trip(test_db, mock_context):
    """Should persist and restore queue state correctly."""
    queue_ids = list(range(1, 101))
    queue_index = 42
    shuffle = True
    sort_spec = None

    # Create table for persistence
    test_db.execute("""
        CREATE TABLE player_queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            context_type TEXT,
            context_id INTEGER,
            shuffle_enabled BOOLEAN,
            sort_field TEXT,
            sort_direction TEXT,
            queue_track_ids TEXT,
            queue_index INTEGER,
            position_in_playlist INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Save
    queue_manager.save_queue_state(mock_context, queue_ids, queue_index, shuffle, sort_spec, test_db)

    # Load
    state = queue_manager.load_queue_state(test_db)

    assert state is not None
    assert state["queue_ids"] == queue_ids
    assert state["queue_index"] == queue_index
    assert state["shuffle_enabled"] == shuffle


def test_load_queue_state_returns_none_when_empty(test_db):
    """Should return None when no saved state exists."""
    test_db.execute("""
        CREATE TABLE player_queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            context_type TEXT,
            context_id INTEGER,
            shuffle_enabled BOOLEAN,
            sort_field TEXT,
            sort_direction TEXT,
            queue_track_ids TEXT,
            queue_index INTEGER,
            position_in_playlist INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    state = queue_manager.load_queue_state(test_db)
    assert state is None


def test_save_queue_state_with_sort_spec(test_db, mock_context):
    """Should persist and restore queue state with sort spec."""
    queue_ids = list(range(1, 101))
    queue_index = 25
    shuffle = False
    sort_spec = {"field": "bpm", "direction": "desc"}

    # Create table for persistence
    test_db.execute("""
        CREATE TABLE player_queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            context_type TEXT,
            context_id INTEGER,
            shuffle_enabled BOOLEAN,
            sort_field TEXT,
            sort_direction TEXT,
            queue_track_ids TEXT,
            queue_index INTEGER,
            position_in_playlist INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Save
    queue_manager.save_queue_state(mock_context, queue_ids, queue_index, shuffle, sort_spec, test_db)

    # Load
    state = queue_manager.load_queue_state(test_db)

    assert state is not None
    assert state["sort_spec"] is not None
    assert state["sort_spec"]["field"] == "bpm"
    assert state["sort_spec"]["direction"] == "desc"


# Test: Edge cases

def test_initialize_queue_empty_playlist(test_db, mock_context):
    """Should handle empty playlists gracefully."""
    # Create empty playlist
    test_db.execute("INSERT INTO playlists VALUES (99, 'Empty Playlist', 'manual')")
    test_db.commit()

    mock_context.playlist_id = 99
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert queue == []


def test_get_next_track_with_empty_exclusions(test_db, mock_context):
    """Should work correctly with empty exclusion list."""
    track_id = queue_manager.get_next_track(mock_context, [], test_db, shuffle=True)
    assert track_id is not None
    assert 1 <= track_id <= 200


def test_rebuild_queue_at_queue_start(test_db, mock_context):
    """Should rebuild correctly when at beginning of queue."""
    original_queue = list(range(1, 101))
    queue_index = 0  # At the very start

    new_queue = queue_manager.rebuild_queue(
        mock_context, 1, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # Only current track preserved
    assert new_queue[0] == 1
    assert len(new_queue) >= 100


def test_rebuild_queue_near_end(test_db, mock_context):
    """Should rebuild correctly when near end of queue."""
    original_queue = list(range(1, 101))
    queue_index = 95  # Near the end

    new_queue = queue_manager.rebuild_queue(
        mock_context, 96, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # History preserved: tracks 1-96
    assert new_queue[0:96] == original_queue[0:96]
    # Should have only added ~4 new tracks (to reach window_size=100)
    assert len(new_queue) >= 100


def test_initialize_queue_sorted_without_spec(test_db, mock_context):
    """Should use default track_number sorting when no spec provided."""
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=None)

    # Should be in sequential order (track IDs 1-10)
    assert queue == list(range(1, 11))


def test_get_next_track_sorted_at_position_zero(test_db, mock_context):
    """Should get second track when position is 0 in sorted mode."""
    sort_spec = {"field": "track_number", "direction": "asc"}

    track_id = queue_manager.get_next_track(
        mock_context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=0
    )

    assert track_id is not None
    # Should be track at position 1 (second track)
    assert track_id == 2


def test_save_queue_state_updates_existing(test_db, mock_context):
    """Should update existing state rather than duplicate rows."""
    # Create table for persistence
    test_db.execute("""
        CREATE TABLE player_queue_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            context_type TEXT,
            context_id INTEGER,
            shuffle_enabled BOOLEAN,
            sort_field TEXT,
            sort_direction TEXT,
            queue_track_ids TEXT,
            queue_index INTEGER,
            position_in_playlist INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Save first state
    queue_manager.save_queue_state(mock_context, [1, 2, 3], 0, True, None, test_db)

    # Save second state (should replace)
    queue_manager.save_queue_state(mock_context, [4, 5, 6], 1, False, {"field": "bpm", "direction": "asc"}, test_db)

    # Verify only one row exists
    cursor = test_db.execute("SELECT COUNT(*) as count FROM player_queue_state")
    row = cursor.fetchone()
    assert row["count"] == 1

    # Verify it's the latest state
    state = queue_manager.load_queue_state(test_db)
    assert state["queue_ids"] == [4, 5, 6]
    assert state["queue_index"] == 1
    assert state["shuffle_enabled"] == False
