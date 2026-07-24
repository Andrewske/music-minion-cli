"""Tests for queue_manager.get_next_tracks (batch refill) and the
sorted-mode position invariant.

Invariant under test: position_in_sorted is the SQL OFFSET of the NEXT row of
the context's sorted order to materialize; it advances by rows FETCHED and
wraps modulo the context total.
"""

import sqlite3
from dataclasses import dataclass
from typing import Literal, Optional

import pytest

from backend import queue_manager


@dataclass
class _Ctx:
    """Minimal PlayContext stand-in (matches fields queue_manager reads)."""

    type: Literal[
        "playlist", "track", "builder", "search", "comparison", "organizer"
    ] = "playlist"
    playlist_id: Optional[int] = 1
    builder_id: Optional[int] = None
    track_ids: Optional[list[int]] = None
    shuffle: bool = True
    session_id: Optional[str] = None
    bucket_id: Optional[str] = None


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Module-level context cache must not leak across tests."""
    queue_manager.invalidate_context_cache()
    yield
    queue_manager.invalidate_context_cache()


@pytest.fixture
def test_db():
    """In-memory DB: 20-track manual playlist, titles sort t01..t20."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE tracks (
            id INTEGER PRIMARY KEY, title TEXT, artist TEXT, bpm INTEGER,
            year INTEGER, track_number INTEGER, unavailable_at TIMESTAMP
        )
        """
    )
    conn.execute("CREATE TABLE playlists (id INTEGER PRIMARY KEY, name TEXT, type TEXT)")
    conn.execute(
        "CREATE TABLE playlist_tracks (playlist_id INTEGER, track_id INTEGER, position INTEGER)"
    )
    conn.execute(
        "CREATE TABLE track_ratings (track_id INTEGER PRIMARY KEY, elo_rating INTEGER DEFAULT 1500)"
    )
    conn.execute("INSERT INTO playlists VALUES (1, 'P', 'manual')")
    for i in range(1, 21):
        conn.execute(
            "INSERT INTO tracks (id, title, track_number) VALUES (?, ?, ?)",
            (i, f"t{i:02d}", i),
        )
        conn.execute("INSERT INTO playlist_tracks VALUES (1, ?, ?)", (i, i))
    conn.commit()
    yield conn
    conn.close()


TITLE_ASC = {"field": "title", "direction": "asc"}


# ---------- shuffle batch ----------


def test_shuffle_batch_returns_count_distinct_excluding(test_db):
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(), count=5, exclusion_ids=[1, 2, 3], db_conn=test_db, shuffle=True
    )
    assert len(ids) == 5
    assert len(set(ids)) == 5
    assert not set(ids) & {1, 2, 3}
    assert new_pos is None  # shuffle mode: caller keeps its position


def test_shuffle_batch_respects_unavailable(test_db):
    test_db.execute("UPDATE tracks SET unavailable_at = '2026-01-01' WHERE id <= 15")
    test_db.commit()
    ids, _ = queue_manager.get_next_tracks(
        _Ctx(), count=10, exclusion_ids=[], db_conn=test_db, shuffle=True
    )
    assert set(ids) <= {16, 17, 18, 19, 20}
    assert len(ids) == 5  # only 5 available — returns what exists


def test_shuffle_batch_zero_count(test_db):
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(), count=0, exclusion_ids=[], db_conn=test_db, shuffle=True
    )
    assert ids == []
    assert new_pos is None


# ---------- sorted batch: position invariant ----------


def test_sorted_batch_fetches_at_offset_and_advances_by_fetched(test_db):
    """position IS the next offset; advances by rows fetched (not +window)."""
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(),
        count=4,
        exclusion_ids=[],
        db_conn=test_db,
        shuffle=False,
        sort_spec=TITLE_ASC,
        position_in_sorted=3,
    )
    assert ids == [4, 5, 6, 7]  # sorted rows 3..6 (0-based), no +1 skip
    assert new_pos == 7


def test_sorted_batch_wraps_modulo_total(test_db):
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(),
        count=5,
        exclusion_ids=[],
        db_conn=test_db,
        shuffle=False,
        sort_spec=TITLE_ASC,
        position_in_sorted=18,
    )
    assert ids == [19, 20]  # only 2 rows left before the end
    assert new_pos == 0  # wrapped: next refill loops from the top


def test_sorted_batch_no_gap_across_consecutive_refills(test_db):
    """Two consecutive refills must cover a contiguous sorted range."""
    ctx = _Ctx()
    ids1, pos1 = queue_manager.get_next_tracks(
        ctx, 4, [], test_db, shuffle=False, sort_spec=TITLE_ASC, position_in_sorted=0
    )
    ids2, pos2 = queue_manager.get_next_tracks(
        ctx, 4, [], test_db, shuffle=False, sort_spec=TITLE_ASC, position_in_sorted=pos1
    )
    assert ids1 + ids2 == [1, 2, 3, 4, 5, 6, 7, 8]
    assert pos2 == 8


def test_sorted_batch_position_advances_even_when_all_excluded(test_db):
    """Excluded rows still consume position — the cursor never stalls."""
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(),
        count=3,
        exclusion_ids=[6, 7, 8],
        db_conn=test_db,
        shuffle=False,
        sort_spec=TITLE_ASC,
        position_in_sorted=5,
    )
    assert ids == []
    assert new_pos == 8


def test_sorted_batch_default_order_uses_playlist_position(test_db):
    """No sort_spec: slices the context's position order at the offset."""
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(),
        count=3,
        exclusion_ids=[],
        db_conn=test_db,
        shuffle=False,
        sort_spec=None,
        position_in_sorted=10,
    )
    assert ids == [11, 12, 13]
    assert new_pos == 13


def test_sorted_batch_skips_unavailable_consistently(test_db):
    """unavailable_at rows are invisible to both offsets and totals."""
    test_db.execute("UPDATE tracks SET unavailable_at = '2026-01-01' WHERE id = 1")
    test_db.commit()
    ids, new_pos = queue_manager.get_next_tracks(
        _Ctx(),
        count=3,
        exclusion_ids=[],
        db_conn=test_db,
        shuffle=False,
        sort_spec=TITLE_ASC,
        position_in_sorted=0,
    )
    assert ids == [2, 3, 4]  # track 1 is dead → row 0 of the order is track 2
    assert new_pos == 3


# ---------- context cache ----------


def test_context_cache_reused_then_invalidated(test_db):
    ctx = _Ctx()
    first = queue_manager._get_context_ids_cached(ctx, test_db)
    assert first == list(range(1, 21))

    # Mutate DB behind the cache — cached result is intentionally reused
    test_db.execute("DELETE FROM playlist_tracks WHERE track_id > 10")
    test_db.commit()
    assert queue_manager._get_context_ids_cached(ctx, test_db) == first

    # Explicit invalidation re-resolves
    queue_manager.invalidate_context_cache()
    assert queue_manager._get_context_ids_cached(ctx, test_db) == list(range(1, 11))


def test_context_cache_misses_on_context_change(test_db):
    test_db.execute("INSERT INTO playlists VALUES (2, 'Q', 'manual')")
    test_db.execute("INSERT INTO playlist_tracks VALUES (2, 1, 1)")
    test_db.commit()

    assert len(queue_manager._get_context_ids_cached(_Ctx(playlist_id=1), test_db)) == 20
    assert len(queue_manager._get_context_ids_cached(_Ctx(playlist_id=2), test_db)) == 1


def test_initialize_queue_refreshes_cache(test_db):
    """initialize_queue is write-through: it always re-resolves."""
    ctx = _Ctx()
    queue_manager._get_context_ids_cached(ctx, test_db)
    test_db.execute("DELETE FROM playlist_tracks WHERE track_id > 5")
    test_db.commit()

    queue = queue_manager.initialize_queue(ctx, test_db, shuffle=True)
    assert set(queue) == {1, 2, 3, 4, 5}
    # And the cache now reflects the fresh resolve
    assert queue_manager._get_context_ids_cached(ctx, test_db) == [1, 2, 3, 4, 5]
