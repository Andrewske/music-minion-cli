"""Tests for feed-noise sync: get_user_reposts pagination, retry behavior,
sync_followings_reposts writes, dedup, and feed_stats CTE windowing."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud.api import (
    MAX_REPOSTS_PAGES,
    get_user_reposts,
)


def _auth_state() -> ProviderState:
    """Provider state authenticated with a fake token."""
    return ProviderState(
        config=ProviderConfig(name="soundcloud"),
        authenticated=True,
        cache={"client_id": "test", "client_secret": "test",
               "token_data": {"access_token": "tok", "expires_at": 9999999999}},
    )


def _mock_response(status: int, payload: object) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    r.json.return_value = payload
    return r


# ---------------------------------------------------------------------------
# Unit tests — no DB required
# ---------------------------------------------------------------------------


class TestGetUserReposts:
    def test_paginates_and_caps_at_3_pages(self) -> None:
        """Fetches at most MAX_REPOSTS_PAGES even if next_href always returns."""
        call_count = {"n": 0}

        def fake_request(state, method, url, **kw):
            call_count["n"] += 1
            return state, _mock_response(200, {
                "collection": [{"id": call_count["n"] * 100 + j} for j in range(200)],
                "next_href": "https://api.soundcloud.com/next",
            })

        with patch(
            "music_minion.domain.library.providers.soundcloud.api._request_with_backoff",
            side_effect=fake_request,
        ):
            state, tracks, err = get_user_reposts(_auth_state(), "123")

        assert err is None
        assert call_count["n"] == MAX_REPOSTS_PAGES == 3
        assert len(tracks) == 600

    def test_429_returns_rate_limited_error(self) -> None:
        """_request_with_backoff HTTPError(429) surfaces as 'Rate limited' string."""
        from requests import HTTPError
        err_response = MagicMock()
        err_response.status_code = 429
        err = HTTPError(response=err_response)

        with patch(
            "music_minion.domain.library.providers.soundcloud.api._request_with_backoff",
            side_effect=err,
        ):
            state, tracks, msg = get_user_reposts(_auth_state(), "123")

        assert tracks == []
        assert msg == "Rate limited"


# ---------------------------------------------------------------------------
# DB tests — construct minimal schema directly (bypasses init_database,
# which has an unrelated pre-existing bug with ALTER-added columns used in
# initial-schema indexes).
# ---------------------------------------------------------------------------


MINIMAL_SCHEMA_SQL = [
    """CREATE TABLE discovery_artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_user_id TEXT UNIQUE,
        slug TEXT,
        display_name TEXT,
        display_name_normalized TEXT,
        ranking INTEGER,
        is_following INTEGER DEFAULT 0,
        in_top_200 INTEGER DEFAULT 0,
        hit_rate REAL,
        tracks_seen INTEGER DEFAULT 0,
        tracks_liked INTEGER DEFAULT 0,
        tracks_dismissed INTEGER DEFAULT 0,
        avatar_url TEXT,
        follower_count INTEGER,
        last_checked TIMESTAMP,
        check_interval_days INTEGER DEFAULT 1
    )""",
    """CREATE TABLE discovery_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_id TEXT UNIQUE,
        slug TEXT,
        title TEXT,
        artist_name TEXT,
        duration_ms INTEGER,
        released_at TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'unseen',
        playlist_batch INTEGER
    )""",
    """CREATE TABLE discovery_track_reposters (
        discovery_track_id INTEGER NOT NULL,
        discovery_artist_id INTEGER NOT NULL,
        reposted_at TIMESTAMP,
        seen_at TIMESTAMP,
        PRIMARY KEY (discovery_track_id, discovery_artist_id)
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
        local_path TEXT,
        elo_rating REAL
    )""",
    """CREATE TABLE ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        rating_type TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE playlist_elo_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER,
        track_id INTEGER,
        rating REAL
    )""",
    """CREATE TABLE artist_match_overrides (
        id INTEGER PRIMARY KEY,
        discovery_artist_id INTEGER,
        local_artist_name TEXT,
        action TEXT,
        created_at TIMESTAMP,
        UNIQUE(local_artist_name, discovery_artist_id)
    )""",
    """CREATE VIEW artist_match_resolved AS
       SELECT NULL AS local_name, NULL AS discovery_artist_id WHERE 0""",
    """CREATE TABLE playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        track_count INTEGER DEFAULT 0,
        soundcloud_playlist_id TEXT,
        discovery_source TEXT
    )""",
    """CREATE TABLE playlist_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        position INTEGER,
        UNIQUE(playlist_id, track_id)
    )""",
    """CREATE TABLE bucket_sessions (
        id TEXT PRIMARY KEY,
        playlist_id INTEGER NOT NULL,
        status TEXT DEFAULT 'active'
    )""",
    """CREATE TABLE discovery_sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        artists_checked INTEGER DEFAULT 0,
        tracks_fetched INTEGER DEFAULT 0,
        tracks_added INTEGER DEFAULT 0,
        mixes_added INTEGER DEFAULT 0,
        tracks_skipped INTEGER DEFAULT 0,
        dry_run INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0
    )""",
]


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Minimal DB fixture covering just the tables the sync needs."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(
        "music_minion.core.database.get_database_path",
        lambda: db_path,
    )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    for stmt in MINIMAL_SCHEMA_SQL:
        conn.execute(stmt)
    conn.commit()
    conn.close()
    yield db_path


class TestSyncFollowingsReposts:
    def test_writes_rows_with_seen_at(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO discovery_artists (soundcloud_user_id, slug, display_name, ranking, is_following) "
                "VALUES ('111', 'test-artist', 'Test Artist', 1, 1)"
            )
            conn.commit()
            aid = conn.execute("SELECT id FROM discovery_artists").fetchone()["id"]

        fake_tracks = [
            {"id": 1001, "title": "A", "permalink": "a", "user": {"username": "artist"},
             "duration": 180000, "created_at": "2026/04/15 00:00:00 +0000"},
            {"id": 1002, "title": "B", "permalink": "b", "user": {"username": "artist"},
             "duration": 200000, "created_at": "2026/04/14 00:00:00 +0000"},
        ]

        from web.backend.discovery_sync import sync_followings_reposts
        with patch(
            "web.backend.discovery_sync.get_user_reposts",
            return_value=(_auth_state(), fake_tracks, None),
        ):
            added, errors = sync_followings_reposts(_auth_state())

        assert errors == []
        assert added == 2

        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT discovery_artist_id, seen_at FROM discovery_track_reposters"
            ).fetchall()
        assert len(rows) == 2
        for row in rows:
            assert row["discovery_artist_id"] == aid
            assert row["seen_at"] is not None  # CURRENT_TIMESTAMP from INSERT

    def test_dedup_via_primary_key(self, test_db) -> None:
        """Running sync twice with same response leaves row count flat."""
        from music_minion.core.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO discovery_artists (soundcloud_user_id, slug, display_name, ranking, is_following) "
                "VALUES ('222', 'x', 'X', 1, 1)"
            )
            conn.commit()

        fake = [{"id": 2001, "title": "T", "permalink": "t", "user": {"username": "x"},
                 "duration": 100, "created_at": "2026/04/15 00:00:00 +0000"}]

        from web.backend.discovery_sync import sync_followings_reposts
        with patch(
            "web.backend.discovery_sync.get_user_reposts",
            return_value=(_auth_state(), fake, None),
        ):
            sync_followings_reposts(_auth_state())
            with get_db_connection() as conn:
                conn.execute("UPDATE discovery_artists SET last_checked=NULL")
                conn.commit()
            sync_followings_reposts(_auth_state())

        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM discovery_track_reposters").fetchone()[0]
        assert count == 1


class TestBackfillNullReposted:
    """Regression: NULL reposted_at must sort last in backfill ordering.

    Bug: ORDER BY COALESCE(reposted_at, first_seen) DESC pulled tracks with
    NULL reposted_at into recency rankings via first_seen, surfacing old
    tracks that the daemon happened to ingest recently.
    """

    def test_null_reposted_at_sorts_last(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import get_unplaced_short_tracks

        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO discovery_artists "
                "(soundcloud_user_id, slug, display_name, ranking, in_top_200) "
                "VALUES ('1', 'top', 'Top', 50, 1)"
            )
            top_id = conn.execute("SELECT id FROM discovery_artists").fetchone()["id"]

            for sc_id, first_seen in [
                ("RECENT", "2026-04-25"),
                ("NULL_TS", "2018-01-01"),
                ("OLD", "2024-01-01"),
            ]:
                conn.execute(
                    "INSERT INTO discovery_tracks (soundcloud_id, title, artist_name, "
                    "duration_ms, status, first_seen) VALUES (?, ?, 'A', 200000, 'unseen', ?)",
                    (sc_id, sc_id, first_seen),
                )
            ids = {
                row["soundcloud_id"]: row["id"]
                for row in conn.execute(
                    "SELECT id, soundcloud_id FROM discovery_tracks"
                ).fetchall()
            }

            for sc_id, reposted_at in [
                ("RECENT", "2026-04-25 12:00:00"),
                ("NULL_TS", None),
                ("OLD", "2024-01-01 12:00:00"),
            ]:
                conn.execute(
                    "INSERT INTO discovery_track_reposters "
                    "(discovery_track_id, discovery_artist_id, reposted_at) "
                    "VALUES (?, ?, ?)",
                    (ids[sc_id], top_id, reposted_at),
                )
            conn.commit()

        results = get_unplaced_short_tracks(exclude_sc_ids=set(), limit=10)
        order = [r["id"] for r in results]
        assert order == ["RECENT", "OLD", "NULL_TS"], (
            f"NULL reposted_at should sort last; got {order}"
        )


class TestSeenIdsScope:
    """Regression: get_seen_track_ids must only block classified/placed tracks.

    Bug: function returned every row in discovery_tracks. After feed-noise
    daemon began ingesting all followings' reposts as status='unseen', the
    seen_ids set blocked every fresh fetch.
    """

    def test_unseen_tracks_not_blocked(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import get_seen_track_ids

        with get_db_connection() as conn:
            for sc_id, status in [
                ("L", "liked"),
                ("D", "dismissed"),
                ("P", "in_playlist"),
                ("U", "unseen"),
            ]:
                conn.execute(
                    "INSERT INTO discovery_tracks "
                    "(soundcloud_id, title, artist_name, duration_ms, status) "
                    "VALUES (?, 'T', 'A', 100, ?)",
                    (sc_id, status),
                )
            conn.commit()

        seen = get_seen_track_ids()
        assert seen == {"L", "D", "P"}, "unseen tracks must not be in seen_ids"


class TestUnplacedBackfillTopOnly:
    """Regression: backfill pool must filter to top-200 reposters.

    Bug: feed-noise daemon ingested reposts from all followings, then the
    backfill query joined discovery_artists without an in_top_200 filter,
    so the SC reposts playlist filled up with tracks whose only reposters
    were non-top-200 followings.
    """

    def test_excludes_tracks_only_reposted_by_non_top_200(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import get_unplaced_short_tracks

        with get_db_connection() as conn:
            # top-200 ranked artist
            conn.execute(
                "INSERT INTO discovery_artists "
                "(soundcloud_user_id, slug, display_name, ranking, is_following, in_top_200) "
                "VALUES ('1', 'top', 'Top', 50, 1, 1)"
            )
            # following only — not in top-200, NULL ranking
            conn.execute(
                "INSERT INTO discovery_artists "
                "(soundcloud_user_id, slug, display_name, ranking, is_following, in_top_200) "
                "VALUES ('2', 'follow', 'Follow', NULL, 1, 0)"
            )
            top_id = conn.execute(
                "SELECT id FROM discovery_artists WHERE slug='top'"
            ).fetchone()["id"]
            follow_id = conn.execute(
                "SELECT id FROM discovery_artists WHERE slug='follow'"
            ).fetchone()["id"]

            # track A: reposted only by non-top-200 following → must be excluded
            # track B: reposted only by top-200 → must be included
            # track C: reposted by both → must be included, attributed to top-200
            conn.execute(
                "INSERT INTO discovery_tracks (soundcloud_id, title, artist_name, "
                "duration_ms, status, first_seen) "
                "VALUES ('A', 'TrackA', 'X', 200000, 'unseen', '2026-04-01')"
            )
            conn.execute(
                "INSERT INTO discovery_tracks (soundcloud_id, title, artist_name, "
                "duration_ms, status, first_seen) "
                "VALUES ('B', 'TrackB', 'Y', 200000, 'unseen', '2026-04-02')"
            )
            conn.execute(
                "INSERT INTO discovery_tracks (soundcloud_id, title, artist_name, "
                "duration_ms, status, first_seen) "
                "VALUES ('C', 'TrackC', 'Z', 200000, 'unseen', '2026-04-03')"
            )
            track_a = conn.execute(
                "SELECT id FROM discovery_tracks WHERE soundcloud_id='A'"
            ).fetchone()["id"]
            track_b = conn.execute(
                "SELECT id FROM discovery_tracks WHERE soundcloud_id='B'"
            ).fetchone()["id"]
            track_c = conn.execute(
                "SELECT id FROM discovery_tracks WHERE soundcloud_id='C'"
            ).fetchone()["id"]

            conn.execute(
                "INSERT INTO discovery_track_reposters "
                "(discovery_track_id, discovery_artist_id) VALUES (?, ?)",
                (track_a, follow_id),
            )
            conn.execute(
                "INSERT INTO discovery_track_reposters "
                "(discovery_track_id, discovery_artist_id) VALUES (?, ?)",
                (track_b, top_id),
            )
            conn.execute(
                "INSERT INTO discovery_track_reposters "
                "(discovery_track_id, discovery_artist_id) VALUES (?, ?)",
                (track_c, top_id),
            )
            conn.execute(
                "INSERT INTO discovery_track_reposters "
                "(discovery_track_id, discovery_artist_id) VALUES (?, ?)",
                (track_c, follow_id),
            )
            conn.commit()

        results = get_unplaced_short_tracks(exclude_sc_ids=set(), limit=10)
        sc_ids = {r["id"] for r in results}

        assert "A" not in sc_ids, "track only reposted by non-top-200 leaked into backfill"
        assert sc_ids == {"B", "C"}

        for r in results:
            assert r["artist_id"] == top_id, "non-top-200 artist attributed to track"


class TestOwnedSCIds:
    """get_owned_sc_ids: SC IDs in any other playlist + tracks rated 'love'."""

    def test_get_owned_sc_ids(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import get_owned_sc_ids

        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO playlists (id, name) VALUES (26, 'reposts'), (99, 'other')"
            )
            for sc_id, title in [
                ("A", "in reposts only"),
                ("B", "in other playlist"),
                ("C", "love-rated"),
                ("D", "neither"),
            ]:
                conn.execute(
                    "INSERT INTO tracks (title, soundcloud_id) VALUES (?, ?)",
                    (title, sc_id),
                )
            track_ids = {
                row["soundcloud_id"]: row["id"]
                for row in conn.execute(
                    "SELECT id, soundcloud_id FROM tracks"
                ).fetchall()
            }
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, 0)",
                (26, track_ids["A"]),
            )
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, 0)",
                (99, track_ids["B"]),
            )
            conn.execute(
                "INSERT INTO ratings (track_id, rating_type) VALUES (?, 'love')",
                (track_ids["C"],),
            )
            conn.commit()

        owned = get_owned_sc_ids(exclude_playlist_id=26)
        assert owned == {"B", "C"}, (
            f"reposts-only track A and unowned D must not appear; got {owned}"
        )


class TestBackfillExcludesOwned:
    """Regression: backfill must skip tracks the user already has."""

    def test_owned_tracks_filtered(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import get_unplaced_short_tracks

        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO discovery_artists "
                "(soundcloud_user_id, slug, display_name, ranking, in_top_200) "
                "VALUES ('1', 'top', 'Top', 50, 1)"
            )
            top_id = conn.execute("SELECT id FROM discovery_artists").fetchone()["id"]

            for sc_id in ["NEW", "OWNED"]:
                conn.execute(
                    "INSERT INTO discovery_tracks (soundcloud_id, title, artist_name, "
                    "duration_ms, status) VALUES (?, ?, 'A', 200000, 'unseen')",
                    (sc_id, sc_id),
                )
            for sc_id in ["NEW", "OWNED"]:
                track_id = conn.execute(
                    "SELECT id FROM discovery_tracks WHERE soundcloud_id=?", (sc_id,)
                ).fetchone()["id"]
                conn.execute(
                    "INSERT INTO discovery_track_reposters "
                    "(discovery_track_id, discovery_artist_id, reposted_at) "
                    "VALUES (?, ?, '2026-04-25 12:00:00')",
                    (track_id, top_id),
                )
            conn.commit()

        results = get_unplaced_short_tracks(
            exclude_sc_ids=set(),
            owned_sc_ids={"OWNED"},
            limit=10,
        )
        sc_ids = {r["id"] for r in results}
        assert sc_ids == {"NEW"}, (
            f"OWNED must be filtered; got {sc_ids}"
        )


def _seed_run_discovery_sync_minimum(
    conn,
    *,
    reposts_playlist_id: int = 26,
    sc_reposts_playlist_id: str = "999",
) -> int:
    """Seed the minimum DB state run_discovery_sync needs.

    Returns the top-200 artist's id.
    """
    conn.execute(
        "INSERT INTO playlists (id, name, soundcloud_playlist_id, discovery_source) "
        "VALUES (?, 'reposts', ?, 'soundcloud_reposts')",
        (reposts_playlist_id, sc_reposts_playlist_id),
    )
    conn.execute(
        "INSERT INTO discovery_artists "
        "(soundcloud_user_id, slug, display_name, ranking, in_top_200, "
        "tracks_seen, tracks_liked, tracks_dismissed, hit_rate) "
        "VALUES ('1', 'top', 'Top', 50, 1, 0, 0, 0, 0.0)"
    )
    artist_id = conn.execute("SELECT id FROM discovery_artists").fetchone()["id"]
    conn.commit()
    return artist_id


class TestReposterWriteTimestamp:
    """Regression: run_discovery_sync writes the SC repost timestamp,
    not None, when storing reposter rows."""

    def test_reposted_at_populated_after_sync(self, test_db) -> None:
        from music_minion.core.database import get_db_connection

        with get_db_connection() as conn:
            artist_id = _seed_run_discovery_sync_minimum(conn)

        fake_track = {
            "id": 8001,
            "title": "Fresh",
            "permalink": "fresh",
            "user": {"username": "Top"},
            "duration": 200000,
            "created_at": "2026/04/25 12:00:00 +0000",
        }

        from web.backend.discovery_sync import run_discovery_sync
        with patch(
            "web.backend.discovery_sync.get_web_provider_state",
            return_value=_auth_state(),
        ), patch(
            "web.backend.discovery_sync._fetch_all_reposts",
            return_value=(_auth_state(), {artist_id: [fake_track]}, []),
        ):
            run_discovery_sync(dry_run=True)

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT reposted_at FROM discovery_track_reposters"
            ).fetchone()
        assert row is not None, "reposter row not written"
        assert row["reposted_at"] == "2026/04/25 12:00:00 +0000", (
            f"expected SC created_at as reposted_at; got {row['reposted_at']!r}"
        )


class TestFreshPathExcludesOwned:
    """Regression: tracks already owned by the user are dropped from the
    fresh-fetch result before duration split / chronological selection."""

    def test_owned_track_not_added_to_playlist(self, test_db) -> None:
        from music_minion.core.database import get_db_connection

        with get_db_connection() as conn:
            artist_id = _seed_run_discovery_sync_minimum(conn)

            conn.execute(
                "INSERT INTO tracks (title, soundcloud_id) VALUES ('Owned', 'OWNED')"
            )
            owned_local_id = conn.execute(
                "SELECT id FROM tracks WHERE soundcloud_id='OWNED'"
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO playlists (id, name) VALUES (99, 'other')"
            )
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) "
                "VALUES (99, ?, 0)",
                (owned_local_id,),
            )
            conn.commit()

        owned_track = {
            "id": "OWNED",
            "title": "Owned",
            "permalink": "owned",
            "user": {"username": "Top"},
            "duration": 200000,
            "created_at": "2026/04/25 12:00:00 +0000",
        }
        new_track = {
            "id": 9001,
            "title": "Fresh",
            "permalink": "fresh",
            "user": {"username": "Top"},
            "duration": 200000,
            "created_at": "2026/04/25 12:00:00 +0000",
        }

        from web.backend.discovery_sync import run_discovery_sync
        with patch(
            "web.backend.discovery_sync.get_web_provider_state",
            return_value=_auth_state(),
        ), patch(
            "web.backend.discovery_sync._fetch_all_reposts",
            return_value=(
                _auth_state(),
                {artist_id: [owned_track, new_track]},
                [],
            ),
        ):
            result = run_discovery_sync(dry_run=True)

        assert result.tracks_added_to_playlist == 1, (
            f"owned track should be filtered; "
            f"got tracks_added={result.tracks_added_to_playlist}"
        )


class TestFeedStatsCTE:
    def test_feed_noise_windowing(self, test_db) -> None:
        """feed_noise_7d/30d reflect correct counts divided by window."""
        from music_minion.core.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO discovery_artists (soundcloud_user_id, slug, display_name, ranking, is_following) "
                "VALUES ('333', 'y', 'Y', 1, 1)"
            )
            aid = conn.execute("SELECT id FROM discovery_artists").fetchone()["id"]

            for i in range(4):
                conn.execute(
                    "INSERT INTO discovery_tracks (soundcloud_id, slug, title, artist_name, duration_ms) "
                    "VALUES (?, ?, ?, 'Y', 100)",
                    (f"3000{i}", f"t{i}", f"Track {i}"),
                )
            track_ids = [r["id"] for r in conn.execute("SELECT id FROM discovery_tracks").fetchall()]

            # 2 rows within 7 days (1d, 3d ago)
            # 2 more within 30d but outside 7 (15d, 25d ago)
            seen_ats = ["-1 day", "-3 days", "-15 days", "-25 days"]
            for tid, offset in zip(track_ids, seen_ats):
                conn.execute(
                    f"INSERT INTO discovery_track_reposters "
                    f"(discovery_track_id, discovery_artist_id, seen_at) "
                    f"VALUES (?, ?, datetime('now', '{offset}'))",
                    (tid, aid),
                )
            conn.commit()

        from web.backend.queries.artists import get_artist_stats
        with get_db_connection() as conn:
            rows = get_artist_stats(conn, source="soundcloud", sort="noise")

        matching = [r for r in rows if r["id"] == aid]
        assert len(matching) == 1
        stats = matching[0]
        assert stats["feed_noise_7d"] == pytest.approx(2 / 7.0, abs=0.01)
        assert stats["feed_noise_30d"] == pytest.approx(4 / 30.0, abs=0.01)
