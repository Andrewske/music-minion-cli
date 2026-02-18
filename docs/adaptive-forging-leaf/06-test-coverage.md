---
task: 06-test-coverage
status: done
depends: [02-queue-manager-module]
files:
  - path: web/backend/tests/test_queue_manager.py
    action: create
  - path: web/backend/tests/conftest.py
    action: create
---

# Test Coverage - Queue Manager Unit Tests

## Context
Add comprehensive unit tests for the queue_manager module. Since it's designed as a pure functional module with no global state, it's highly testable in isolation.

## Files to Modify/Create
- web/backend/tests/test_queue_manager.py (new)

## Implementation Details

### Test Setup

Create test fixtures for database and mock context:

```python
import pytest
import sqlite3
from web.backend.queue_manager import (
    initialize_queue,
    get_next_track,
    rebuild_queue,
    save_queue_state,
    load_queue_state,
)

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
            year INTEGER
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

    # Insert 200 test tracks
    for i in range(1, 201):
        conn.execute(
            "INSERT INTO tracks VALUES (?, ?, ?, ?, ?)",
            (i, f"Track {i}", f"Artist {i % 10}", 120 + (i % 60), 2020 + (i % 5))
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
    """Mock PlayContext for testing."""
    from dataclasses import dataclass

    @dataclass
    class PlayContext:
        context_type: str = "playlist"
        context_id: int = 1
        shuffle: bool = True

    return PlayContext()
```

### Test Cases

#### Test: initialize_queue (shuffle mode)

```python
def test_initialize_queue_shuffle_returns_correct_size(test_db, mock_context):
    """Should return requested window size for shuffle mode."""
    queue = initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert len(queue) == 100
    assert all(isinstance(track_id, int) for track_id in queue)

def test_initialize_queue_shuffle_no_duplicates(test_db, mock_context):
    """Should not have duplicate tracks in initial queue."""
    queue = initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert len(set(queue)) == 100  # All unique

def test_initialize_queue_small_playlist(test_db, mock_context):
    """Should handle playlists smaller than window size."""
    # Create small playlist
    test_db.execute("DELETE FROM playlist_tracks WHERE playlist_id = 1")
    for i in range(1, 21):  # Only 20 tracks
        test_db.execute("INSERT INTO playlist_tracks VALUES (1, ?, ?)", (i, i))
    test_db.commit()

    queue = initialize_queue(mock_context, test_db, window_size=100, shuffle=True)

    assert len(queue) == 20  # Returns all available tracks
```

#### Test: initialize_queue (sorted mode)

```python
def test_initialize_queue_sorted_by_bpm(test_db, mock_context):
    """Should return tracks sorted by BPM ascending."""
    sort_spec = {"field": "bpm", "direction": "asc"}
    queue = initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    # Verify sorted order
    tracks = [test_db.execute("SELECT bpm FROM tracks WHERE id = ?", (tid,)).fetchone()["bpm"] for tid in queue]
    assert tracks == sorted(tracks)

def test_initialize_queue_sorted_descending(test_db, mock_context):
    """Should respect sort direction."""
    sort_spec = {"field": "year", "direction": "desc"}
    queue = initialize_queue(mock_context, test_db, window_size=10, shuffle=False, sort_spec=sort_spec)

    tracks = [test_db.execute("SELECT year FROM tracks WHERE id = ?", (tid,)).fetchone()["year"] for tid in queue]
    assert tracks == sorted(tracks, reverse=True)
```

#### Test: get_next_track (exclusions)

```python
def test_get_next_track_respects_exclusions(test_db, mock_context):
    """Should never return excluded track IDs."""
    exclusions = list(range(1, 101))  # Exclude first 100 tracks

    for _ in range(10):  # Try 10 times
        track_id = get_next_track(mock_context, exclusions, test_db, shuffle=True)
        assert track_id not in exclusions
        assert track_id is not None

def test_get_next_track_returns_none_when_all_excluded(test_db, mock_context):
    """Should return None when all tracks are excluded."""
    exclusions = list(range(1, 201))  # All tracks

    track_id = get_next_track(mock_context, exclusions, test_db, shuffle=True)
    assert track_id is None

def test_get_next_track_sorted_mode_circular(test_db, mock_context):
    """Should wrap around to beginning in sorted mode."""
    sort_spec = {"field": "bpm", "direction": "asc"}

    # Position at last track (199, assuming 200 total)
    track_id = get_next_track(
        mock_context, [], test_db,
        shuffle=False,
        sort_spec=sort_spec,
        position_in_playlist=199
    )

    # Should get track at position (199 + 100) % 200 = 99
    assert track_id is not None
```

#### Test: rebuild_queue

```python
def test_rebuild_queue_preserves_history(test_db, mock_context):
    """Should preserve played tracks and current track."""
    original_queue = list(range(1, 101))  # Tracks 1-100
    queue_index = 50  # Played first 50 tracks
    current_track_id = 51

    new_queue = rebuild_queue(
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

    new_queue = rebuild_queue(
        mock_context, 51, original_queue, queue_index,
        test_db, shuffle=True, sort_spec=None
    )

    # Future tracks should be different (not guaranteed but very likely with 200 total)
    future_original = original_queue[51:]
    future_new = new_queue[51:]

    assert future_original != future_new
```

#### Test: Persistence (save/load round-trip)

```python
def test_save_load_queue_state_round_trip(test_db, mock_context):
    """Should persist and restore queue state correctly."""
    queue_ids = list(range(1, 101))
    queue_index = 42
    shuffle = True
    sort_spec = None
    position_in_playlist = 0

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
    save_queue_state(mock_context, queue_ids, queue_index, shuffle, sort_spec, position_in_playlist, test_db)

    # Load
    state = load_queue_state(test_db)

    assert state is not None
    assert state["queue_ids"] == queue_ids
    assert state["queue_index"] == queue_index
    assert state["shuffle_enabled"] == shuffle
    assert state["position_in_playlist"] == position_in_playlist

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

    state = load_queue_state(test_db)
    assert state is None
```

## Running Tests

```bash
# Run all queue manager tests
uv run pytest web/backend/tests/test_queue_manager.py -v

# Run with coverage
uv run pytest web/backend/tests/test_queue_manager.py --cov=web.backend.queue_manager --cov-report=term-missing

# Run specific test
uv run pytest web/backend/tests/test_queue_manager.py::test_get_next_track_respects_exclusions -v
```

## Coverage Goals

- **initialize_queue**: Test both shuffle and sorted modes, edge cases for small playlists
- **get_next_track**: Test exclusion logic, empty results, sorted mode position tracking
- **rebuild_queue**: Test history preservation, future regeneration
- **save/load_queue_state**: Test persistence round-trip, error handling

**Target**: 80%+ coverage of queue_manager.py

## Verification

After implementing tests:

```bash
uv run pytest web/backend/tests/test_queue_manager.py -v
```

**Expected output:**
- All tests pass
- Coverage report shows >80% line coverage
- No warnings or errors
