"""Comprehensive unit tests for queue_manager module.

Tests pure functional queue management: initialization, dynamic refilling,
shuffle toggling, and state persistence.
"""

import pytest
import sqlite3
from unittest import mock

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


# Test: Different context types

def test_initialize_queue_comparison_context(test_db):
    """Should handle comparison context with track_ids."""
    context = MockPlayContext(
        type="comparison",
        track_ids=[1, 2, 3, 4, 5]
    )

    queue = queue_manager.initialize_queue(context, test_db, window_size=10, shuffle=True)

    # Should return tracks from track_ids list
    assert len(queue) == 5
    assert all(tid in [1, 2, 3, 4, 5] for tid in queue)


def test_initialize_queue_builder_context(test_db):
    """Should handle builder context."""
    # Create builder playlist
    test_db.execute("INSERT INTO playlists VALUES (99, 'Builder', 'manual')")
    for i in range(1, 11):
        test_db.execute("INSERT INTO playlist_tracks VALUES (99, ?, ?)", (i, i))
    test_db.commit()

    context = MockPlayContext(
        type="builder",
        playlist_id=None,
        builder_id=99
    )

    queue = queue_manager.initialize_queue(context, test_db, window_size=10, shuffle=True)

    assert len(queue) == 10


def test_get_next_track_builder_context(test_db):
    """Should get next track from builder context."""
    # Create builder playlist
    test_db.execute("INSERT INTO playlists VALUES (99, 'Builder', 'manual')")
    for i in range(1, 21):
        test_db.execute("INSERT INTO playlist_tracks VALUES (99, ?, ?)", (i, i))
    test_db.commit()

    context = MockPlayContext(
        type="builder",
        playlist_id=None,
        builder_id=99
    )

    track_id = queue_manager.get_next_track(context, [1, 2, 3], test_db, shuffle=True)

    assert track_id is not None
    assert track_id not in [1, 2, 3]
    assert 4 <= track_id <= 20


def test_get_next_track_comparison_context(test_db):
    """Should get next track from comparison context track_ids."""
    context = MockPlayContext(
        type="comparison",
        track_ids=[10, 20, 30, 40, 50]
    )

    track_id = queue_manager.get_next_track(context, [10, 20], test_db, shuffle=True)

    assert track_id is not None
    assert track_id in [30, 40, 50]


def test_get_next_track_sorted_builder(test_db):
    """Should get sorted tracks from builder context."""
    # Create builder playlist with varied BPMs
    test_db.execute("INSERT INTO playlists VALUES (99, 'Builder', 'manual')")
    for i in range(1, 11):
        test_db.execute("INSERT INTO playlist_tracks VALUES (99, ?, ?)", (i, i))
    test_db.commit()

    context = MockPlayContext(
        type="builder",
        playlist_id=None,
        builder_id=99
    )

    sort_spec = {"field": "bpm", "direction": "asc"}
    track_id = queue_manager.get_next_track(
        context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=0
    )

    assert track_id is not None


def test_initialize_queue_sorted_with_elo_rating(test_db, mock_context):
    """Should sort by ELO rating when specified."""
    # Add some ratings
    for i in range(1, 11):
        test_db.execute("INSERT INTO track_ratings VALUES (?, ?)", (i, 1500 + i * 10))
    test_db.commit()

    sort_spec = {"field": "elo_rating", "direction": "desc"}
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=5, shuffle=False, sort_spec=sort_spec)

    # Verify descending ELO order
    ratings = [test_db.execute("SELECT elo_rating FROM track_ratings WHERE track_id = ?", (tid,)).fetchone()["elo_rating"] for tid in queue]
    assert ratings == sorted(ratings, reverse=True)


def test_rebuild_queue_sorted_mode(test_db, mock_context):
    """Should rebuild queue in sorted mode with sort spec."""
    original_queue = list(range(1, 101))
    queue_index = 50

    sort_spec = {"field": "bpm", "direction": "asc"}
    new_queue = queue_manager.rebuild_queue(
        mock_context, 51, original_queue, queue_index,
        test_db, shuffle=False, sort_spec=sort_spec
    )

    # History preserved
    assert new_queue[0:51] == original_queue[0:51]
    # Should have new tracks added
    assert len(new_queue) >= 100


def test_get_next_track_sequential_without_sort_spec(test_db, mock_context):
    """Should use sequential playback without sort spec in sorted mode."""
    track_id = queue_manager.get_next_track(
        mock_context, [1, 2, 3], test_db,
        shuffle=False,
        sort_spec=None
    )

    # Should get first non-excluded track
    assert track_id == 4


def test_load_queue_state_with_builder_context(test_db):
    """Should restore builder context from database."""
    # Create table and builder playlist
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

    test_db.execute("INSERT INTO playlists VALUES (99, 'Builder', 'manual')")
    test_db.commit()

    context = MockPlayContext(type="builder", builder_id=99, playlist_id=None)
    queue_manager.save_queue_state(context, [1, 2, 3], 0, True, None, test_db)

    state = queue_manager.load_queue_state(test_db)
    assert state is not None
    assert state["context"].type == "builder"
    assert state["context"].builder_id == 99


def test_initialize_queue_when_window_larger_than_playlist_shuffle(test_db, mock_context):
    """Should shuffle and return all tracks when playlist smaller than window."""
    # Create small playlist
    test_db.execute("DELETE FROM playlist_tracks WHERE playlist_id = 1")
    for i in range(1, 6):  # Only 5 tracks
        test_db.execute("INSERT INTO playlist_tracks VALUES (1, ?, ?)", (i, i))
    test_db.commit()

    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    # Should return all 5 tracks
    assert len(queue) == 5
    # Should be shuffled (unique)
    assert len(set(queue)) == 5


def test_get_next_track_comparison_all_excluded(test_db):
    """Should return None when all comparison tracks are excluded."""
    context = MockPlayContext(
        type="comparison",
        track_ids=[1, 2, 3]
    )

    track_id = queue_manager.get_next_track(context, [1, 2, 3], test_db, shuffle=True)
    assert track_id is None


def test_rebuild_queue_with_full_history(test_db, mock_context):
    """Should handle rebuild when history fills entire window."""
    # Queue index at position 99 means we've played 100 tracks
    original_queue = list(range(1, 101))
    queue_index = 99

    new_queue = queue_manager.rebuild_queue(
        mock_context, 100, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # Should preserve all 100 tracks (no room for new ones with window_size=100)
    assert new_queue == original_queue


def test_get_next_track_sorted_comparison_context(test_db):
    """Should handle sorted mode with comparison context."""
    context = MockPlayContext(
        type="comparison",
        track_ids=[5, 15, 25, 35, 45]
    )

    sort_spec = {"field": "bpm", "direction": "asc"}
    track_id = queue_manager.get_next_track(
        context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=0
    )

    assert track_id is not None
    assert track_id in [5, 15, 25, 35, 45]


def test_save_queue_state_with_none_sort_spec(test_db, mock_context):
    """Should handle None sort_spec correctly."""
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

    queue_manager.save_queue_state(mock_context, [1, 2, 3], 0, True, None, test_db)

    cursor = test_db.execute("SELECT sort_field, sort_direction FROM player_queue_state WHERE id = 1")
    row = cursor.fetchone()
    assert row["sort_field"] is None
    assert row["sort_direction"] is None


def test_initialize_queue_sorted_by_artist(test_db, mock_context):
    """Should sort by artist field."""
    sort_spec = {"field": "artist", "direction": "asc"}
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    # Verify sorted order
    artists = [test_db.execute("SELECT artist FROM tracks WHERE id = ?", (tid,)).fetchone()["artist"] for tid in queue]
    assert artists == sorted(artists)


def test_initialize_queue_sorted_by_title(test_db, mock_context):
    """Should sort by title field."""
    sort_spec = {"field": "title", "direction": "asc"}
    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    # Verify sorted order
    titles = [test_db.execute("SELECT title FROM tracks WHERE id = ?", (tid,)).fetchone()["title"] for tid in queue]
    assert titles == sorted(titles)


def test_load_queue_state_with_comparison_context(test_db):
    """Should restore comparison context (with empty track_ids)."""
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

    # Insert a comparison context state
    test_db.execute("""
        INSERT INTO player_queue_state VALUES
        (1, 'comparison', NULL, 1, NULL, NULL, '[1, 2, 3]', 0, NULL, CURRENT_TIMESTAMP)
    """)

    state = queue_manager.load_queue_state(test_db)
    assert state is not None
    assert state["context"].type == "comparison"
    # Note: track_ids will be empty, needs to be refreshed
    assert state["context"].track_ids == []


def test_load_queue_state_unknown_context_type(test_db):
    """Should default to playlist context for unknown types."""
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

    # Insert an unknown context type
    test_db.execute("""
        INSERT INTO player_queue_state VALUES
        (1, 'unknown_type', 42, 1, NULL, NULL, '[1, 2, 3]', 0, NULL, CURRENT_TIMESTAMP)
    """)

    state = queue_manager.load_queue_state(test_db)
    assert state is not None
    # Should default to playlist
    assert state["context"].type == "playlist"


def test_initialize_queue_small_playlist_sorted_without_spec(test_db, mock_context):
    """Should handle small playlist in sorted mode without sort spec."""
    # Create small playlist
    test_db.execute("DELETE FROM playlist_tracks WHERE playlist_id = 1")
    for i in range(1, 11):  # Only 10 tracks
        test_db.execute("INSERT INTO playlist_tracks VALUES (1, ?, ?)", (i, i))
    test_db.commit()

    queue = queue_manager.initialize_queue(mock_context, test_db, window_size=100, shuffle=False, sort_spec=None)

    # Should return all 10 tracks in order
    assert queue == list(range(1, 11))


def test_get_next_track_nonexistent_playlist(test_db):
    """Should handle nonexistent playlist gracefully."""
    context = MockPlayContext(playlist_id=999)  # Doesn't exist

    track_id = queue_manager.get_next_track(context, [], test_db, shuffle=True)
    # Should return None due to empty playlist
    assert track_id is None


def test_initialize_queue_nonexistent_playlist(test_db):
    """Should handle nonexistent playlist gracefully."""
    context = MockPlayContext(playlist_id=999)  # Doesn't exist

    queue = queue_manager.initialize_queue(context, test_db, window_size=100, shuffle=True)
    # Should return empty queue
    assert queue == []


def test_rebuild_queue_nonexistent_playlist(test_db):
    """Should handle errors gracefully and return preserved tracks."""
    context = MockPlayContext(playlist_id=999)  # Doesn't exist

    original_queue = list(range(1, 51))
    queue_index = 25

    new_queue = queue_manager.rebuild_queue(
        context, 26, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # Should return preserved tracks on error
    assert new_queue == original_queue[0:26]


def test_initialize_queue_track_context(test_db):
    """Should handle single track context."""
    context = MockPlayContext(
        type="track",
        track_ids=[42]
    )

    queue = queue_manager.initialize_queue(context, test_db, window_size=100, shuffle=True)

    # Should return single track
    assert queue == [42]


def test_get_next_track_sorted_mode_with_exclusions_sequential(test_db, mock_context):
    """Should filter exclusions in sequential sorted mode."""
    # All tracks 1-3 are excluded, so should get track 4
    track_id = queue_manager.get_next_track(
        mock_context, [1, 2, 3], test_db,
        shuffle=False,
        sort_spec=None
    )

    assert track_id == 4


def test_rebuild_queue_no_available_tracks(test_db, mock_context):
    """Should handle case where no new tracks available."""
    # Create small playlist with only 10 tracks
    test_db.execute("DELETE FROM playlist_tracks WHERE playlist_id = 1")
    for i in range(1, 11):
        test_db.execute("INSERT INTO playlist_tracks VALUES (1, ?, ?)", (i, i))
    test_db.commit()

    # Queue contains all available tracks
    original_queue = list(range(1, 11))
    queue_index = 5

    new_queue = queue_manager.rebuild_queue(
        mock_context, 6, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # Should preserve history, but can't add new tracks (all are in history)
    assert new_queue[0:6] == original_queue[0:6]
    # Length might be just the history if no new tracks available
    assert len(new_queue) >= 6


def test_get_next_track_builder_sorted_by_title(test_db):
    """Should sort builder tracks by title."""
    test_db.execute("INSERT INTO playlists VALUES (99, 'Builder', 'manual')")
    for i in range(1, 11):
        test_db.execute("INSERT INTO playlist_tracks VALUES (99, ?, ?)", (i, i))
    test_db.commit()

    context = MockPlayContext(
        type="builder",
        playlist_id=None,
        builder_id=99
    )

    sort_spec = {"field": "title", "direction": "asc"}
    track_id = queue_manager.get_next_track(
        context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=0
    )

    assert track_id is not None


def test_save_queue_state_with_position_in_playlist(test_db, mock_context):
    """Should save position_in_playlist when shuffle is False."""
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

    # Save with shuffle=False
    queue_manager.save_queue_state(mock_context, [1, 2, 3], 2, False, None, test_db)

    cursor = test_db.execute("SELECT position_in_playlist FROM player_queue_state WHERE id = 1")
    row = cursor.fetchone()
    # When shuffle=False, position_in_playlist should equal queue_index
    assert row["position_in_playlist"] == 2


def test_load_queue_state_with_sort_direction_none(test_db):
    """Should handle None sort_direction by defaulting to asc."""
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

    # Insert state with sort_field but NULL sort_direction
    test_db.execute("""
        INSERT INTO player_queue_state VALUES
        (1, 'playlist', 1, 0, 'bpm', NULL, '[1, 2, 3]', 0, 0, CURRENT_TIMESTAMP)
    """)

    state = queue_manager.load_queue_state(test_db)
    assert state is not None
    assert state["sort_spec"]["field"] == "bpm"
    assert state["sort_spec"]["direction"] == "asc"  # Default


# Test: Smart playlist handling (mocked)

@mock.patch('music_minion.domain.playlists.filters.evaluate_filters')
def test_get_next_track_smart_playlist(mock_evaluate, test_db):
    """Should handle smart playlist by evaluating filters."""
    # Create smart playlist
    test_db.execute("INSERT INTO playlists VALUES (88, 'Smart Test', 'smart')")
    test_db.commit()

    # Mock evaluate_filters to return some tracks
    mock_evaluate.return_value = [
        {"id": 10}, {"id": 20}, {"id": 30}, {"id": 40}
    ]

    context = MockPlayContext(playlist_id=88)

    track_id = queue_manager.get_next_track(context, [10], test_db, shuffle=True)

    assert track_id is not None
    assert track_id in [20, 30, 40]  # Not 10 (excluded)
    mock_evaluate.assert_called_once_with(88)


@mock.patch('music_minion.domain.playlists.filters.evaluate_filters')
def test_initialize_queue_smart_playlist(mock_evaluate, test_db):
    """Should initialize queue from smart playlist."""
    # Create smart playlist
    test_db.execute("INSERT INTO playlists VALUES (88, 'Smart Test', 'smart')")
    test_db.commit()

    # Mock evaluate_filters to return tracks
    mock_evaluate.return_value = [{"id": i} for i in range(1, 51)]

    context = MockPlayContext(playlist_id=88)

    queue = queue_manager.initialize_queue(context, test_db, window_size=20, shuffle=True)

    assert len(queue) == 20
    mock_evaluate.assert_called_once_with(88)


@mock.patch('music_minion.domain.playlists.filters.evaluate_filters')
def test_get_sorted_tracks_smart_playlist(mock_evaluate, test_db):
    """Should sort smart playlist tracks."""
    # Create smart playlist
    test_db.execute("INSERT INTO playlists VALUES (88, 'Smart Test', 'smart')")
    test_db.commit()

    # Mock evaluate_filters
    mock_evaluate.return_value = [{"id": i} for i in range(1, 21)]

    context = MockPlayContext(playlist_id=88)

    sort_spec = {"field": "bpm", "direction": "asc"}
    queue = queue_manager.initialize_queue(context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    assert len(queue) == 10
    # Verify sorted order
    bpms = [test_db.execute("SELECT bpm FROM tracks WHERE id = ?", (tid,)).fetchone()["bpm"] for tid in queue]
    assert bpms == sorted(bpms)


@mock.patch('music_minion.domain.playlists.filters.evaluate_filters')
def test_get_next_track_smart_playlist_sorted(mock_evaluate, test_db):
    """Should get next track from sorted smart playlist."""
    # Create smart playlist
    test_db.execute("INSERT INTO playlists VALUES (88, 'Smart Test', 'smart')")
    test_db.commit()

    # Mock evaluate_filters
    mock_evaluate.return_value = [{"id": i} for i in range(1, 21)]

    context = MockPlayContext(playlist_id=88)

    sort_spec = {"field": "bpm", "direction": "asc"}
    track_id = queue_manager.get_next_track(
        context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_sorted=0
    )

    assert track_id is not None


@mock.patch('music_minion.domain.playlists.filters.evaluate_filters')
def test_rebuild_queue_smart_playlist(mock_evaluate, test_db):
    """Should rebuild queue for smart playlist."""
    # Create smart playlist
    test_db.execute("INSERT INTO playlists VALUES (88, 'Smart Test', 'smart')")
    test_db.commit()

    # Mock evaluate_filters
    mock_evaluate.return_value = [{"id": i} for i in range(1, 101)]

    context = MockPlayContext(playlist_id=88)

    original_queue = list(range(1, 51))
    queue_index = 25

    new_queue = queue_manager.rebuild_queue(
        context, 26, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # History preserved
    assert new_queue[0:26] == original_queue[0:26]
    # New tracks added
    assert len(new_queue) >= 50
