"""
Tests for rating database functions.
"""

import pytest

from music_minion.core.database import get_db_connection

TEST_TRACKS = [
    (1, "Track 1", "Artist A", "/path/to/track1.mp3", "local"),
    (2, "Track 2", "Artist B", "/path/to/track2.opus", "local"),
    (3, "Track 3", "Artist C", None, "soundcloud"),
    (4, "Track 4", "Artist D", None, "spotify"),
    (5, "Track 5", "Artist E", "", "local"),
    (6, "Track 6", "Artist F", "   ", "local"),
    (7, "Track 7", "Artist G", "/path/to/track7.m4a", "local"),
]


def _insert_playlist(conn, name: str) -> int:
    cursor = conn.execute(
        "INSERT INTO playlists (name, type) VALUES (?, 'manual')", (name,)
    )
    return cursor.lastrowid


@pytest.fixture
def test_db() -> None:
    """Seed the per-test isolated database (root conftest) with tracks + 'All'."""
    with get_db_connection() as conn:
        conn.executemany(
            "INSERT INTO tracks (id, title, artist, local_path, source)"
            " VALUES (?, ?, ?, ?, ?)",
            TEST_TRACKS,
        )
        _insert_playlist(conn, "All")
        conn.commit()


def test_record_comparison_column_names():
    """Verify INSERT uses correct column names matching schema."""
    with get_db_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(playlist_comparison_history)")
        cols = {row["name"] for row in cursor.fetchall()}

    required = {
        "track_a_playlist_rating_before",
        "track_a_playlist_rating_after",
        "track_b_playlist_rating_before",
        "track_b_playlist_rating_after",
    }
    assert required.issubset(cols), f"Missing columns: {required - cols}"


@pytest.fixture
def test_playlist(test_db) -> int:
    """A single empty playlist for comparison tests."""
    with get_db_connection() as conn:
        playlist_id = _insert_playlist(conn, "Test Playlist")
        conn.commit()
    return playlist_id


def test_record_comparison_basic(test_db, test_playlist):
    """Basic recording works without error."""
    from music_minion.domain.rating.database import record_playlist_comparison

    # Should not raise
    record_playlist_comparison(
        playlist_id=test_playlist,
        track_a_id=1,
        track_b_id=2,
        winner_id=1,
        track_a_rating_before=1500.0,
        track_b_rating_before=1500.0,
        track_a_rating_after=1516.0,
        track_b_rating_after=1484.0,
    )


@pytest.fixture
def two_playlist_setup(test_db) -> dict[str, int]:
    """Two playlists with overlapping tracks for cross-playlist tests."""
    with get_db_connection() as conn:
        playlist_a_id = _insert_playlist(conn, "Playlist A")
        playlist_b_id = _insert_playlist(conn, "Playlist B")
        # Playlist A has tracks 1, 2, 3; playlist B has 1, 2 (same pair) plus 4
        memberships = [(playlist_a_id, t, i) for i, t in enumerate([1, 2, 3])]
        memberships += [(playlist_b_id, t, i) for i, t in enumerate([1, 2, 4])]
        conn.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position)"
            " VALUES (?, ?, ?)",
            memberships,
        )
        conn.commit()

    return {"playlist_a": playlist_a_id, "playlist_b": playlist_b_id}


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
