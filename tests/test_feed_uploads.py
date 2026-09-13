"""Tests for the SoundCloud uploads feed: get_user_tracks pagination,
uploads sync, feed page queries (cursor/filters), and the -1/0/+1 rating flow."""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud.api import (
    MAX_UPLOAD_PAGES,
    get_tracks_by_ids,
    get_user_tracks,
)


def _auth_state() -> ProviderState:
    return ProviderState(
        config=ProviderConfig(name="soundcloud"),
        authenticated=True,
        cache={
            "client_id": "test",
            "client_secret": "test",
            "token_data": {"access_token": "tok", "expires_at": 9999999999},
        },
    )


def _mock_response(status: int, payload: object) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    r.json.return_value = payload
    return r


def _recent(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y/%m/%d %H:%M:%S +0000"
    )


MINIMAL_SCHEMA_SQL = [
    """CREATE TABLE discovery_artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_user_id TEXT,
        slug TEXT UNIQUE,
        display_name TEXT,
        display_name_normalized TEXT,
        ranking INTEGER DEFAULT 0,
        tier TEXT,
        hit_rate REAL DEFAULT 0,
        upload_keep_rate REAL,
        upload_rated_count REAL NOT NULL DEFAULT 0,
        repost_keep_rate REAL,
        repost_rated_count REAL NOT NULL DEFAULT 0,
        tracks_seen INTEGER DEFAULT 0,
        tracks_liked INTEGER DEFAULT 0,
        tracks_dismissed INTEGER DEFAULT 0,
        in_top_200 INTEGER DEFAULT 0,
        is_following INTEGER DEFAULT 1,
        avatar_url TEXT,
        follower_count INTEGER,
        last_checked TIMESTAMP,
        check_interval_days INTEGER DEFAULT 1,
        uploads_last_checked TIMESTAMP,
        upload_check_interval_hours INTEGER DEFAULT 24
    )""",
    """CREATE TABLE discovery_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_id TEXT UNIQUE,
        title TEXT,
        artist_name TEXT,
        duration_ms INTEGER,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        playlist_batch INTEGER,
        uploader_soundcloud_id TEXT,
        genre TEXT,
        artwork_url TEXT,
        permalink_url TEXT,
        access TEXT,
        uploaded_at TIMESTAMP,
        released_at TIMESTAMP,
        metadata_updated_at TIMESTAMP,
        status TEXT DEFAULT 'unseen'
    )""",
    """CREATE TABLE discovery_track_reposters (
        discovery_track_id INTEGER NOT NULL,
        discovery_artist_id INTEGER NOT NULL,
        reposted_at TIMESTAMP,
        seen_at TIMESTAMP,
        event_type TEXT DEFAULT 'repost',
        raw_reposted_at TEXT,
        repost_time_precision TEXT DEFAULT 'approximate',
        PRIMARY KEY (discovery_track_id, discovery_artist_id)
    )""",
    """CREATE TABLE tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        artist TEXT,
        artist_normalized TEXT,
        soundcloud_id TEXT UNIQUE,
        duration REAL,
        local_path TEXT,
        artwork_url TEXT,
        source_url TEXT,
        genre TEXT,
        updated_at TIMESTAMP,
        source TEXT
    )""",
    """CREATE TABLE sc_artist_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discovery_artist_id INTEGER NOT NULL,
        soundcloud_id TEXT UNIQUE NOT NULL,
        title TEXT,
        permalink_url TEXT,
        artwork_url TEXT,
        duration_ms INTEGER DEFAULT 0,
        uploaded_at TIMESTAMP NOT NULL,
        local_track_id INTEGER,
        status TEXT NOT NULL DEFAULT 'visible'
            CHECK (status IN ('visible', 'hidden', 'dismissed', 'liked')),
        rated_at TIMESTAMP,
        sc_like_done BOOLEAN DEFAULT 0,
        sc_playlist_done BOOLEAN DEFAULT 0,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        access TEXT,
        event_type TEXT DEFAULT 'upload',
        uploader_soundcloud_id TEXT,
        genre TEXT,
        released_at TIMESTAMP,
        metadata_updated_at TIMESTAMP
    )""",
    """CREATE TABLE sc_monthly_playlists (
        name TEXT PRIMARY KEY,
        sc_playlist_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE sc_feed_sync_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_run_at TIMESTAMP,
        last_run_status TEXT,
        last_error TEXT,
        events_added_last_run INTEGER DEFAULT 0,
        total_events INTEGER DEFAULT 0,
        last_run_duration_ms INTEGER,
        uploads_last_run_at TIMESTAMP,
        uploads_last_status TEXT,
        uploads_last_error TEXT,
        uploads_added_last_run INTEGER DEFAULT 0,
        metadata_backfill_cursor INTEGER DEFAULT 0,
        metadata_backfill_status TEXT,
        metadata_backfill_last_error TEXT,
        metadata_backfill_completed_at TIMESTAMP
    )""",
    """CREATE TABLE playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        soundcloud_playlist_id TEXT
    )""",
    """CREATE TABLE ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        rating_type TEXT NOT NULL,
        source TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE playlist_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        position INTEGER,
        UNIQUE(playlist_id, track_id)
    )""",
]


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("music_minion.core.database.get_database_path", lambda: db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    for stmt in MINIMAL_SCHEMA_SQL:
        conn.execute(stmt)
    conn.execute("INSERT INTO sc_feed_sync_state (id) VALUES (1)")
    conn.commit()
    conn.close()
    yield db_path


def _insert_artist(conn, slug="artist-a", top200=0, name="Artist A") -> int:
    cursor = conn.execute(
        """INSERT INTO discovery_artists
        (soundcloud_user_id, slug, display_name, display_name_normalized,
         ranking, in_top_200, is_following)
        VALUES (?, ?, ?, ?, 1, ?, 1)""",
        (str(abs(hash(slug)) % 10**6), slug, name, name.lower(), top200),
    )
    return cursor.lastrowid


def _insert_upload(
    conn, artist_id, sc_id, uploaded_at, status="visible", title="T"
) -> int:
    cursor = conn.execute(
        """INSERT INTO sc_artist_uploads
        (discovery_artist_id, soundcloud_id, title, uploaded_at, status)
        VALUES (?, ?, ?, ?, ?)""",
        (artist_id, sc_id, title, uploaded_at, status),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# get_user_tracks — no DB
# ---------------------------------------------------------------------------


class TestGetUserTracks:
    def test_paginates_and_caps(self) -> None:
        calls = {"n": 0}

        def fake_request(state, method, url, **kw):
            calls["n"] += 1
            return state, _mock_response(
                200,
                {
                    "collection": [{"id": calls["n"] * 100 + j} for j in range(200)],
                    "next_href": "https://api.soundcloud.com/next",
                },
            )

        with patch(
            "music_minion.domain.library.providers.soundcloud.api._request_with_backoff",
            side_effect=fake_request,
        ):
            state, tracks, err = get_user_tracks(_auth_state(), "123")

        assert err is None
        assert calls["n"] == MAX_UPLOAD_PAGES == 2
        assert len(tracks) == 400

    def test_stops_when_no_next_href(self) -> None:
        def fake_request(state, method, url, **kw):
            return state, _mock_response(200, {"collection": [{"id": 1}]})

        with patch(
            "music_minion.domain.library.providers.soundcloud.api._request_with_backoff",
            side_effect=fake_request,
        ):
            state, tracks, err = get_user_tracks(_auth_state(), "123")

        assert err is None
        assert len(tracks) == 1

    def test_bulk_metadata_fetch_uses_ids_filter(self) -> None:
        response = _mock_response(200, [{"id": 1}, {"id": 2}])
        with patch(
            "music_minion.domain.library.providers.soundcloud.api._request_with_backoff",
            return_value=(_auth_state(), response),
        ) as request:
            _state, tracks, error = get_tracks_by_ids(_auth_state(), ["1", "2"])

        assert error is None
        assert [track["id"] for track in tracks] == [1, 2]
        assert request.call_args.kwargs["params"]["ids"] == "1,2"


# ---------------------------------------------------------------------------
# Uploads sync
# ---------------------------------------------------------------------------


class TestSyncFollowingsUploads:
    def _artist_dict(self, artist_id: int) -> dict:
        return {"id": artist_id, "soundcloud_user_id": "111", "slug": "artist-a"}

    def test_inserts_and_imports_to_library(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_uploads_sync import sync_followings_uploads

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            conn.commit()

        fake = [
            {
                "id": 9001,
                "title": "New Song",
                "permalink_url": "https://sc/x",
                "artwork_url": "https://img/x-large.jpg",
                "duration": 180000,
                "genre": "House",
                "access": "playable",
                "release_date": "2026-09-01",
                "user": {"id": 111, "username": "Artist A"},
                "created_at": _recent(3),
            },
        ]
        with patch(
            "web.backend.feed_uploads_sync.get_user_tracks",
            return_value=(_auth_state(), fake, None),
        ):
            added, errors = sync_followings_uploads(
                _auth_state(), [self._artist_dict(aid)]
            )

        assert added == 1
        assert errors == []
        with get_db_connection() as conn:
            upload = conn.execute("SELECT * FROM sc_artist_uploads").fetchone()
            track = conn.execute("SELECT * FROM tracks").fetchone()
        assert upload["local_track_id"] == track["id"]
        assert track["source"] == "soundcloud"
        assert track["artwork_url"] == "https://img/x-t500x500.jpg"
        assert "T" in upload["uploaded_at"]  # ISO normalized
        assert upload["event_type"] == "upload"
        assert upload["uploader_soundcloud_id"] == "111"
        assert upload["genre"] == "House"
        assert upload["access"] == "playable"
        assert upload["released_at"] == "2026-09-01"
        with get_db_connection() as conn:
            artist = conn.execute(
                "SELECT uploads_last_checked, last_checked FROM discovery_artists"
            ).fetchone()
        assert artist["uploads_last_checked"] is not None
        assert artist["last_checked"] is None

    def test_known_upload_metadata_is_upserted(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_uploads_sync import sync_followings_uploads

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            _insert_upload(
                conn,
                aid,
                "9001",
                "2026-07-01T00:00:00+00:00",
                title="Old title",
            )
            conn.commit()

        current = [
            {
                "id": 9001,
                "title": "Current title",
                "permalink_url": "https://soundcloud.com/artist/current",
                "artwork_url": "https://img/current-large.jpg",
                "genre": "Techno",
                "access": "preview",
                "duration": 181000,
                "created_at": _recent(2),
                "release_date": "2026-09-05",
                "user": {"id": 111, "username": "Artist A"},
            }
        ]
        with patch(
            "web.backend.feed_uploads_sync.get_user_tracks",
            return_value=(_auth_state(), current, None),
        ):
            added, errors = sync_followings_uploads(
                _auth_state(), [self._artist_dict(aid)]
            )

        assert added == 0
        assert errors == []
        with get_db_connection() as conn:
            upload = conn.execute(
                "SELECT * FROM sc_artist_uploads WHERE soundcloud_id = '9001'"
            ).fetchone()
        assert upload["title"] == "Current title"
        assert upload["genre"] == "Techno"
        assert upload["access"] == "preview"
        assert upload["permalink_url"].endswith("/current")
        assert upload["artwork_url"] == "https://img/current-t500x500.jpg"

    def test_skips_known_and_old_uploads(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_uploads_sync import sync_followings_uploads

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            _insert_upload(conn, aid, "9001", "2026-07-01T00:00:00+00:00")
            conn.commit()

        fake = [
            {
                "id": 9001,
                "title": "Known",
                "user": {"username": "A"},
                "created_at": _recent(3),
            },
            {
                "id": 9002,
                "title": "Pre-cutoff",
                "user": {"username": "A"},
                "created_at": "2025/12/15 00:00:00 +0000",
            },  # before UPLOAD_CUTOFF
            {
                "id": 9003,
                "title": "Fresh",
                "user": {"username": "A"},
                "created_at": _recent(1),
            },
        ]
        with patch(
            "web.backend.feed_uploads_sync.get_user_tracks",
            return_value=(_auth_state(), fake, None),
        ):
            added, _ = sync_followings_uploads(_auth_state(), [self._artist_dict(aid)])

        assert added == 1
        with get_db_connection() as conn:
            ids = {
                r["soundcloud_id"]
                for r in conn.execute("SELECT soundcloud_id FROM sc_artist_uploads")
            }
        assert ids == {"9001", "9003"}

    def test_backfill_sweeps_all_followed_artists(self, test_db) -> None:
        """Backfill ignores due-cadence (last_checked recent) and single-pages."""
        from music_minion.core.database import get_db_connection
        from web.backend.feed_uploads_sync import run_uploads_backfill

        with get_db_connection() as conn:
            a1 = _insert_artist(conn, "one", name="One")
            a2 = _insert_artist(conn, "two", name="Two")
            conn.execute("UPDATE discovery_artists SET last_checked = datetime('now')")
            conn.commit()

        calls: list[int] = []

        def fake_get(state, user_id, limit=200, max_pages=2):
            calls.append(max_pages)
            return (
                state,
                [
                    {
                        "id": 5000 + len(calls),
                        "title": "T",
                        "user": {"username": "A"},
                        "created_at": _recent(2),
                    }
                ],
                None,
            )

        with patch(
            "web.backend.feed_uploads_sync.get_user_tracks", side_effect=fake_get
        ):
            added, errors = run_uploads_backfill(_auth_state())

        assert added == 2
        assert errors == []
        assert calls == [
            1,
            1,
        ]  # both artists swept despite fresh last_checked; 1 page each
        with get_db_connection() as conn:
            artists = {
                r["discovery_artist_id"]
                for r in conn.execute(
                    "SELECT discovery_artist_id FROM sc_artist_uploads"
                )
            }
        assert artists == {a1, a2}

    def test_never_touches_last_checked(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_uploads_sync import sync_followings_uploads

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            conn.commit()

        fake = [
            {
                "id": 9001,
                "title": "X",
                "user": {"username": "A"},
                "created_at": _recent(2),
            }
        ]
        with patch(
            "web.backend.feed_uploads_sync.get_user_tracks",
            return_value=(_auth_state(), fake, None),
        ):
            sync_followings_uploads(_auth_state(), [self._artist_dict(aid)])

        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT last_checked FROM discovery_artists WHERE id = ?", (aid,)
            ).fetchone()
        assert row["last_checked"] is None

    def test_upload_due_check_is_independent_from_repost_cadence(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import (
            get_followed_artists_due_for_upload_check,
        )

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            conn.execute(
                """UPDATE discovery_artists
                SET last_checked = datetime('now'),
                    check_interval_days = 30,
                    uploads_last_checked = datetime('now', '-25 hours')
                WHERE id = ?""",
                (aid,),
            )
            conn.commit()

        due = get_followed_artists_due_for_upload_check()
        assert [artist["id"] for artist in due] == [aid]

    def test_writes_sync_state(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_uploads_sync import sync_followings_uploads

        sync_followings_uploads(_auth_state(), [])
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM sc_feed_sync_state").fetchone()
        assert row["uploads_last_status"] == "ok"
        assert row["uploads_added_last_run"] == 0


# ---------------------------------------------------------------------------
# Feed page queries
# ---------------------------------------------------------------------------


class TestGetFeedPage:
    def test_ordering_and_status_filter(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            _insert_upload(conn, aid, "1", "2026-07-01T00:00:00+00:00", "visible")
            _insert_upload(conn, aid, "2", "2026-07-03T00:00:00+00:00", "liked")
            _insert_upload(conn, aid, "3", "2026-07-02T00:00:00+00:00", "hidden")
            _insert_upload(conn, aid, "4", "2026-07-04T00:00:00+00:00", "dismissed")
            conn.commit()

        items = get_feed_page(limit=10)
        assert [i["soundcloud_id"] for i in items] == ["2", "1"]

    def test_cursor_stable_under_new_inserts(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            for day in range(1, 7):
                _insert_upload(conn, aid, str(day), f"2026-07-0{day}T00:00:00+00:00")
            conn.commit()

        page1 = get_feed_page(limit=3)
        assert [i["soundcloud_id"] for i in page1] == ["6", "5", "4"]

        # A sync inserts a newer row mid-scroll — page 2 must not shift.
        with get_db_connection() as conn:
            _insert_upload(conn, aid, "99", "2026-07-09T00:00:00+00:00")
            conn.commit()

        last = page1[-1]
        page2 = get_feed_page(
            limit=3, cursor_uploaded_at=last["uploaded_at"], cursor_id=last["id"]
        )
        assert [i["soundcloud_id"] for i in page2] == ["3", "2", "1"]

    def test_cursor_tiebreak_same_timestamp(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        ts = "2026-07-01T00:00:00+00:00"
        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            ids = [_insert_upload(conn, aid, str(n), ts) for n in range(3)]
            conn.commit()

        page1 = get_feed_page(limit=2)
        assert [i["id"] for i in page1] == [ids[2], ids[1]]
        page2 = get_feed_page(limit=2, cursor_uploaded_at=ts, cursor_id=ids[1])
        assert [i["id"] for i in page2] == [ids[0]]

    def test_top200_filter(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            top = _insert_artist(conn, "top", top200=1, name="Top")
            other = _insert_artist(conn, "other", top200=0, name="Other")
            _insert_upload(conn, top, "1", "2026-07-01T00:00:00+00:00")
            _insert_upload(conn, other, "2", "2026-07-02T00:00:00+00:00")
            conn.commit()

        assert len(get_feed_page(limit=10)) == 2
        items = get_feed_page(limit=10, top200=True)
        assert [i["soundcloud_id"] for i in items] == ["1"]

    def test_in_library_requires_local_path(self, test_db) -> None:
        """Streaming-only imports (local_path NULL) must NOT count as in-library."""
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            saved = _insert_artist(conn, "saved", name="Saved Artist")
            streaming = _insert_artist(conn, "streaming", name="Streaming Artist")
            _insert_upload(conn, saved, "1", "2026-07-01T00:00:00+00:00")
            _insert_upload(conn, streaming, "2", "2026-07-02T00:00:00+00:00")
            conn.execute(
                "INSERT INTO tracks (artist, artist_normalized, local_path) "
                "VALUES ('Saved Artist', 'saved artist', '/music/x.mp3')"
            )
            conn.execute(
                "INSERT INTO tracks (artist, artist_normalized, soundcloud_id, source) "
                "VALUES ('Streaming Artist', 'streaming artist', '77', 'soundcloud')"
            )
            conn.commit()

        items = get_feed_page(limit=10, in_library=True)
        assert [i["soundcloud_id"] for i in items] == ["1"]
        all_items = get_feed_page(limit=10)
        by_sc = {i["soundcloud_id"]: i for i in all_items}
        assert by_sc["1"]["artist"]["in_library"] is True
        assert by_sc["2"]["artist"]["in_library"] is False


# ---------------------------------------------------------------------------
# Rating flow
# ---------------------------------------------------------------------------


@pytest.fixture
def client(test_db):
    from web.backend.routers.feed import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRateUpload:
    def _seed(self) -> tuple[int, int]:
        from music_minion.core.database import get_db_connection

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            uid = _insert_upload(conn, aid, "9001", "2026-07-01T00:00:00+00:00")
            conn.commit()
        return aid, uid

    def test_minus_one_dismisses_and_penalizes(self, client) -> None:
        from music_minion.core.database import get_db_connection

        aid, uid = self._seed()
        resp = client.post(f"/api/feed/{uid}/rate", json={"value": -1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"

        with get_db_connection() as conn:
            artist = conn.execute(
                "SELECT * FROM discovery_artists WHERE id = ?", (aid,)
            ).fetchone()
        assert artist["tracks_dismissed"] == 1
        assert artist["hit_rate"] == 0

    def test_zero_hides_without_penalty(self, client) -> None:
        from music_minion.core.database import get_db_connection

        aid, uid = self._seed()
        resp = client.post(f"/api/feed/{uid}/rate", json={"value": 0})
        assert resp.status_code == 200
        assert resp.json()["status"] == "hidden"

        with get_db_connection() as conn:
            artist = conn.execute(
                "SELECT * FROM discovery_artists WHERE id = ?", (aid,)
            ).fetchone()
        assert artist["tracks_dismissed"] == 0
        assert artist["tracks_liked"] == 0

    def test_plus_one_likes_and_runs_sc_flow(self, client) -> None:
        from music_minion.core.database import get_db_connection

        aid, uid = self._seed()
        with (
            patch(
                "web.backend.routers.feed.get_web_provider_state",
                return_value=_auth_state(),
            ),
            patch(
                "web.backend.feed_rating.like_track",
                return_value=(_auth_state(), True, None),
            ) as mock_like,
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(_auth_state(), "PL1", None),
            ),
            patch(
                "web.backend.feed_rating.add_track_to_playlist",
                return_value=(_auth_state(), True, None),
            ) as mock_add,
        ):
            resp = client.post(f"/api/feed/{uid}/rate", json={"value": 1})

        assert resp.status_code == 200
        mock_like.assert_called_once()
        mock_add.assert_called_once()
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sc_artist_uploads WHERE id = ?", (uid,)
            ).fetchone()
            artist = conn.execute(
                "SELECT * FROM discovery_artists WHERE id = ?", (aid,)
            ).fetchone()
        assert row["status"] == "liked"
        assert row["sc_like_done"] == 1
        assert row["sc_playlist_done"] == 1
        assert artist["tracks_liked"] == 1
        assert artist["hit_rate"] == 100

    def test_sc_failure_leaves_flags_for_sweep(self, client) -> None:
        from web.backend.queries.feed import get_unsynced_liked_uploads

        _, uid = self._seed()
        with (
            patch(
                "web.backend.routers.feed.get_web_provider_state",
                return_value=_auth_state(),
            ),
            patch(
                "web.backend.feed_rating.like_track",
                return_value=(_auth_state(), False, "Rate limited"),
            ),
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(_auth_state(), None, "Rate limited"),
            ),
        ):
            resp = client.post(f"/api/feed/{uid}/rate", json={"value": 1})

        assert resp.status_code == 200
        pending = get_unsynced_liked_uploads()
        assert [p["id"] for p in pending] == [uid]

    def test_invalid_value_rejected(self, client) -> None:
        _, uid = self._seed()
        resp = client.post(f"/api/feed/{uid}/rate", json={"value": 2})
        assert resp.status_code == 422

    def test_unknown_upload_404(self, client) -> None:
        resp = client.post("/api/feed/12345/rate", json={"value": 0})
        assert resp.status_code == 404


class TestMonthlyPlaylist:
    def test_name_format(self) -> None:
        from web.backend.feed_rating import monthly_playlist_name

        assert (
            monthly_playlist_name(datetime(2026, 7, 15, tzinfo=timezone.utc))
            == "Jul 26"
        )
        assert (
            monthly_playlist_name(datetime(2027, 1, 2, tzinfo=timezone.utc)) == "Jan 27"
        )

    def test_ladder_cache_then_local_then_scan_then_create(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_rating import (
            get_or_create_monthly_sc_playlist,
            monthly_playlist_name,
        )

        name = monthly_playlist_name()

        # (4) nothing anywhere -> create
        with (
            patch(
                "web.backend.feed_rating.get_playlists",
                return_value=(_auth_state(), []),
            ),
            patch(
                "web.backend.feed_rating.create_playlist",
                return_value=(_auth_state(), "NEW1", None),
            ) as mock_create,
        ):
            _, pid, err = get_or_create_monthly_sc_playlist(_auth_state())
        assert pid == "NEW1" and err is None
        mock_create.assert_called_once()

        # (1) now cached -> no API calls at all
        with patch("web.backend.feed_rating.get_playlists") as mock_get:
            _, pid, _ = get_or_create_monthly_sc_playlist(_auth_state())
        assert pid == "NEW1"
        mock_get.assert_not_called()

        # (2) clear cache, local playlists row wins
        with get_db_connection() as conn:
            conn.execute("DELETE FROM sc_monthly_playlists")
            conn.execute(
                "INSERT INTO playlists (name, soundcloud_playlist_id) VALUES (?, 'LOCAL1')",
                (name,),
            )
            conn.commit()
        with patch("web.backend.feed_rating.get_playlists") as mock_get:
            _, pid, _ = get_or_create_monthly_sc_playlist(_auth_state())
        assert pid == "LOCAL1"
        mock_get.assert_not_called()

        # (3) no cache/local -> SC scan by name
        with get_db_connection() as conn:
            conn.execute("DELETE FROM sc_monthly_playlists")
            conn.execute("DELETE FROM playlists")
            conn.commit()
        with patch(
            "web.backend.feed_rating.get_playlists",
            return_value=(_auth_state(), [{"id": "SCAN1", "name": name}]),
        ):
            _, pid, _ = get_or_create_monthly_sc_playlist(_auth_state())
        assert pid == "SCAN1"


class TestRetrySweep:
    def test_sweep_finishes_pending_rows(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_rating import sync_pending_feed_likes

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            uid = _insert_upload(
                conn, aid, "9001", "2026-07-01T00:00:00+00:00", status="liked"
            )
            conn.commit()

        with (
            patch(
                "web.backend.feed_rating.like_track",
                return_value=(_auth_state(), True, None),
            ),
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(_auth_state(), "PL1", None),
            ),
            patch(
                "web.backend.feed_rating.add_track_to_playlist",
                return_value=(_auth_state(), True, None),
            ),
        ):
            processed = sync_pending_feed_likes(_auth_state())

        assert processed == 1
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT sc_like_done, sc_playlist_done FROM sc_artist_uploads WHERE id = ?",
                (uid,),
            ).fetchone()
        assert row["sc_like_done"] == 1 and row["sc_playlist_done"] == 1
