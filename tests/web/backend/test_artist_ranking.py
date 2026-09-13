"""Tests for artist tier/ranking management: recompute_tier_rankings ordering,
set_artist_ranking insert semantics, and tier column plumbing in get_artist_stats."""

import sqlite3

import pytest

from web.backend.queries.artists import (
    get_artist_stats,
    recompute_tier_rankings,
    set_artist_ranking,
    set_artist_tier,
)

# Minimal schema covering everything get_artist_stats and the ranking
# helpers touch. artist_match_resolved is a view in prod; a plain table
# with the same columns is enough for these queries.
SCHEMA_SQL = [
    """CREATE TABLE discovery_artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_user_id TEXT,
        slug TEXT,
        display_name TEXT,
        ranking INTEGER,
        tier TEXT,
        hit_rate REAL,
        upload_keep_rate REAL DEFAULT 0.22,
        upload_rated_count REAL DEFAULT 0,
        repost_keep_rate REAL DEFAULT 0.22,
        repost_rated_count REAL DEFAULT 0,
        tracks_seen INTEGER DEFAULT 0,
        is_following INTEGER DEFAULT 1,
        in_top_200 INTEGER DEFAULT 0,
        avatar_url TEXT,
        follower_count INTEGER
    )""",
    """CREATE TABLE artist_match_resolved (
        local_name TEXT,
        discovery_artist_id INTEGER
    )""",
    """CREATE TABLE tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        artist TEXT,
        artist_normalized TEXT,
        soundcloud_id TEXT,
        album TEXT,
        genre TEXT,
        year INTEGER,
        duration REAL,
        local_path TEXT
    )""",
    """CREATE TABLE ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        rating_type TEXT NOT NULL,
        source TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE playlist_elo_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER,
        track_id INTEGER,
        rating REAL
    )""",
    """CREATE TABLE playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        library TEXT
    )""",
    """CREATE TABLE playlist_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL
    )""",
    """CREATE TABLE discovery_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_id TEXT
    )""",
    """CREATE TABLE discovery_track_reposters (
        discovery_track_id INTEGER NOT NULL,
        discovery_artist_id INTEGER NOT NULL,
        reposted_at TIMESTAMP,
        seen_at TIMESTAMP
    )""",
]


@pytest.fixture
def conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for stmt in SCHEMA_SQL:
        conn.execute(stmt)
    yield conn
    conn.close()


def _add_artist(
    conn: sqlite3.Connection,
    name: str,
    ranking: int | None = None,
    tier: str | None = None,
    followers: int = 0,
) -> int:
    cursor = conn.execute(
        """INSERT INTO discovery_artists (slug, display_name, ranking, tier, follower_count)
           VALUES (?, ?, ?, ?, ?)""",
        (name.lower(), name, ranking, tier, followers),
    )
    return cursor.lastrowid


def _add_liked_tracks(conn: sqlite3.Connection, artist_id: int, name: str, n: int) -> None:
    """Give an artist n SC-liked library tracks."""
    norm = name.lower()
    conn.execute(
        "INSERT INTO artist_match_resolved (local_name, discovery_artist_id) VALUES (?, ?)",
        (norm, artist_id),
    )
    for i in range(n):
        cursor = conn.execute(
            "INSERT INTO tracks (title, artist, artist_normalized) VALUES (?, ?, ?)",
            (f"{name} track {i}", name, norm),
        )
        conn.execute(
            "INSERT INTO ratings (track_id, rating_type, source) VALUES (?, 'like', 'soundcloud')",
            (cursor.lastrowid,),
        )


def _rankings(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT display_name, ranking FROM discovery_artists"
    ).fetchall()
    return {r["display_name"]: r["ranking"] for r in rows}


class TestRecomputeTierRankings:
    def test_tier_order_beats_stats(self, conn) -> None:
        """S-tier ranks above A-tier even with fewer liked tracks."""
        s_id = _add_artist(conn, "SArtist", ranking=5, tier="S")
        a_id = _add_artist(conn, "AArtist", ranking=1, tier="A")
        _add_liked_tracks(conn, s_id, "SArtist", 1)
        _add_liked_tracks(conn, a_id, "AArtist", 10)

        recompute_tier_rankings(conn)

        ranks = _rankings(conn)
        assert ranks["SArtist"] == 1
        assert ranks["AArtist"] == 2

    def test_liked_count_orders_within_tier(self, conn) -> None:
        low_id = _add_artist(conn, "FewLikes", ranking=1, tier="A")
        high_id = _add_artist(conn, "ManyLikes", ranking=2, tier="A")
        _add_liked_tracks(conn, low_id, "FewLikes", 2)
        _add_liked_tracks(conn, high_id, "ManyLikes", 7)

        recompute_tier_rankings(conn)

        ranks = _rankings(conn)
        assert ranks["ManyLikes"] == 1
        assert ranks["FewLikes"] == 2

    def test_untiered_follow_tiered_in_existing_order(self, conn) -> None:
        _add_artist(conn, "OldFirst", ranking=3)
        _add_artist(conn, "OldSecond", ranking=8)
        _add_artist(conn, "Tiered", ranking=99, tier="B")

        recompute_tier_rankings(conn)

        ranks = _rankings(conn)
        assert ranks["Tiered"] == 1
        assert ranks["OldFirst"] == 2
        assert ranks["OldSecond"] == 3

    def test_set_tier_missing_artist_returns_false(self, conn) -> None:
        assert set_artist_tier(conn, 12345, "S") is False

    def test_clear_tier_moves_artist_after_tiered(self, conn) -> None:
        a = _add_artist(conn, "Alpha", ranking=1, tier="S")
        _add_artist(conn, "Beta", ranking=2, tier="A")

        assert set_artist_tier(conn, a, None) is True

        ranks = _rankings(conn)
        assert ranks["Beta"] == 1
        assert ranks["Alpha"] == 2


class TestSetArtistRanking:
    def test_insert_at_position_shifts_others(self, conn) -> None:
        _add_artist(conn, "First", ranking=1)
        _add_artist(conn, "Second", ranking=2)
        third = _add_artist(conn, "Third", ranking=3)

        assert set_artist_ranking(conn, third, 1) is True

        ranks = _rankings(conn)
        assert ranks["Third"] == 1
        assert ranks["First"] == 2
        assert ranks["Second"] == 3

    def test_missing_artist_returns_false(self, conn) -> None:
        assert set_artist_ranking(conn, 999, 1) is False


class TestArtistStatsTierColumn:
    def test_stats_include_tier_and_union_aligns(self, conn) -> None:
        """Smoke test: tier flows through the CTE query, and the local-artist
        UNION branch still has matching column counts."""
        artist_id = _add_artist(conn, "Tiered", ranking=1, tier="S", followers=10)
        _add_liked_tracks(conn, artist_id, "Tiered", 1)
        # Local-only artist (no artist_match_resolved row)
        conn.execute(
            "INSERT INTO tracks (title, artist, artist_normalized) VALUES ('t', 'LocalOnly', 'localonly')"
        )

        stats = get_artist_stats(conn, source="all", sort="rank")

        by_name = {s["display_name"]: s for s in stats}
        assert by_name["Tiered"]["tier"] == "S"
        assert by_name["LocalOnly"]["tier"] is None
