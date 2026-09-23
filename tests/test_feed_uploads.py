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
        slug TEXT,
        title TEXT,
        artist_name TEXT,
        duration_ms INTEGER,
        released_at TIMESTAMP,
        uploaded_at TIMESTAMP,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        playlist_batch INTEGER,
        local_track_id INTEGER,
        uploader_soundcloud_id TEXT,
        genre TEXT,
        artwork_url TEXT,
        permalink_url TEXT,
        access TEXT,
        metadata_updated_at TIMESTAMP,
        workflow_state TEXT DEFAULT 'unseen',
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
        genre TEXT,
        local_path TEXT,
        artwork_url TEXT,
        source TEXT,
        source_url TEXT,
        updated_at TIMESTAMP,
        soundcloud_synced_at TIMESTAMP
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
        playlist_id INTEGER,
        track_id INTEGER,
        position INTEGER
    )""",
    """CREATE TABLE sc_track_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        decided_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        surface TEXT NOT NULL,
        model_version TEXT,
        feature_snapshot TEXT,
        is_current INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE UNIQUE INDEX idx_sc_track_decisions_current
        ON sc_track_decisions(soundcloud_id) WHERE is_current = 1""",
    """CREATE VIEW sc_current_training_decisions AS
        SELECT soundcloud_id, decision, decided_at, surface,
               model_version, feature_snapshot
        FROM sc_track_decisions
        WHERE is_current = 1 AND decision IN ('keep', 'nope')""",
    """CREATE TABLE sc_feed_action_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        soundcloud_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        target_key TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        attempt_count INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 5,
        next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_error TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        UNIQUE(soundcloud_id, action_type, target_key)
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
    from music_minion.core.database import _migrate_v64_track_predictions

    _migrate_v64_track_predictions(conn)
    conn.execute("INSERT INTO sc_feed_sync_state (id) VALUES (1)")
    conn.commit()
    conn.close()
    yield db_path


def _insert_artist(conn, slug="artist-a", top200=0, name="Artist A", rank=1) -> int:
    cursor = conn.execute(
        """INSERT INTO discovery_artists
        (soundcloud_user_id, slug, display_name, display_name_normalized,
         ranking, in_top_200, is_following)
        VALUES (?, ?, ?, ?, ?, ?, 1)""",
        (str(abs(hash(slug)) % 10**6), slug, name, name.lower(), rank, top200),
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
    decision = {"liked": "keep", "dismissed": "nope", "hidden": "hide"}.get(status)
    if decision:
        conn.execute(
            """INSERT INTO sc_track_decisions
            (soundcloud_id, decision, decided_at, surface)
            VALUES (?, ?, ?, 'test')""",
            (sc_id, decision, uploaded_at),
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
            limit=3,
            cursor_event_at=last["event_at"],
            cursor_soundcloud_id=last["soundcloud_id"],
        )
        assert [i["soundcloud_id"] for i in page2] == ["3", "2", "1"]

    def test_cursor_tiebreak_same_timestamp(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        ts = "2026-07-01T00:00:00+00:00"
        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            for n in range(3):
                _insert_upload(conn, aid, str(n), ts)
            conn.commit()

        page1 = get_feed_page(limit=2)
        assert [i["id"] for i in page1] == ["2", "1"]
        page2 = get_feed_page(
            limit=2,
            cursor_event_at=page1[-1]["event_at"],
            cursor_soundcloud_id=page1[-1]["soundcloud_id"],
        )
        assert [i["id"] for i in page2] == ["0"]

    def test_top200_filter(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            top = _insert_artist(conn, "top", top200=1, name="Top")
            other = _insert_artist(conn, "other", top200=0, name="Other", rank=201)
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

    def test_plus_one_commits_and_enqueues_sc_flow(self, client) -> None:
        from music_minion.core.database import get_db_connection

        aid, uid = self._seed()
        with patch("web.backend.routers.feed.enqueue_feed_action_drain") as wake:
            resp = client.post(f"/api/feed/{uid}/rate", json={"value": 1})

        assert resp.status_code == 200
        wake.assert_called_once()
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sc_artist_uploads WHERE id = ?", (uid,)
            ).fetchone()
            artist = conn.execute(
                "SELECT * FROM discovery_artists WHERE id = ?", (aid,)
            ).fetchone()
            jobs = conn.execute(
                "SELECT action_type, status FROM sc_feed_action_jobs ORDER BY action_type"
            ).fetchall()
        assert row["status"] == "liked"
        assert [(job["action_type"], job["status"]) for job in jobs] == [
            ("like", "pending"),
            ("monthly_playlist", "pending"),
        ]
        assert artist["tracks_liked"] == 1
        assert artist["hit_rate"] == 100

    def test_duplicate_keep_does_not_duplicate_jobs(self, client) -> None:
        from music_minion.core.database import get_db_connection

        _, uid = self._seed()
        with patch("web.backend.routers.feed.enqueue_feed_action_drain"):
            assert (
                client.post(f"/api/feed/{uid}/rate", json={"value": 1}).status_code
                == 200
            )
            assert (
                client.post(f"/api/feed/{uid}/rate", json={"value": 1}).status_code
                == 200
            )
        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM sc_feed_action_jobs").fetchone()[
                0
            ]
        assert count == 2

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
        from web.backend.feed_rating import drain_pending_feed_actions

        with get_db_connection() as conn:
            aid = _insert_artist(conn)
            _insert_upload(
                conn, aid, "9001", "2026-07-01T00:00:00+00:00", status="liked"
            )
            conn.commit()

        from web.backend.queries.feed import enqueue_keep_actions

        enqueue_keep_actions("9001", "Jul 26")

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
            processed = drain_pending_feed_actions(_auth_state())

        assert processed == 2
        with get_db_connection() as conn:
            statuses = [
                row["status"]
                for row in conn.execute(
                    "SELECT status FROM sc_feed_action_jobs ORDER BY action_type"
                ).fetchall()
            ]
        assert statuses == ["complete", "complete"]


class TestUnifiedFeed:
    @staticmethod
    def _insert_repost(conn, artist_id: int, sc_id: str, event_at: str) -> int:
        cursor = conn.execute(
            """INSERT INTO discovery_tracks
            (soundcloud_id, title, artist_name, duration_ms, released_at,
             permalink_url, genre, access, uploader_soundcloud_id)
            VALUES (?, ?, 'Uploader', 120000, '2026-06-01', ?, 'house',
                    'playable', 'uploader-1')""",
            (sc_id, f"Track {sc_id}", f"https://soundcloud.com/u/{sc_id}"),
        )
        conn.execute(
            """INSERT INTO discovery_track_reposters
            (discovery_track_id, discovery_artist_id, reposted_at,
             repost_time_precision) VALUES (?, ?, ?, 'exact')""",
            (cursor.lastrowid, artist_id, event_at),
        )
        return cursor.lastrowid

    def test_deduplicates_release_and_repost_and_filters_source(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            uploader = _insert_artist(conn, "uploader", rank=80, name="Uploader")
            reposter = _insert_artist(conn, "reposter", rank=20, name="Reposter")
            _insert_upload(conn, uploader, "same", "2026-07-01T00:00:00+00:00")
            self._insert_repost(conn, reposter, "same", "2026-07-03T00:00:00+00:00")
            conn.commit()

        all_items = get_feed_page(source="all")
        assert len(all_items) == 1
        assert all_items[0]["sources"] == ["release", "repost"]
        assert all_items[0]["event_at"] == "2026-07-03T00:00:00Z"
        assert all_items[0]["best_reposter_rank"] == 20
        assert all_items[0]["reposter_count"] == 1
        assert all_items[0]["reposters"][0]["repost_time_precision"] == "exact"
        assert get_feed_page(source="releases")[0]["sources"] == ["release"]
        assert get_feed_page(source="reposts")[0]["sources"] == ["repost"]

    def test_rank_uses_current_ranking_and_unfollowed_events_are_excluded(
        self, test_db
    ) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            rank_200 = _insert_artist(conn, "rank200", top200=0, rank=200)
            rank_201 = _insert_artist(conn, "rank201", top200=1, rank=201)
            unfollowed = _insert_artist(conn, "gone", rank=1)
            conn.execute(
                "UPDATE discovery_artists SET is_following = 0 WHERE id = ?",
                (unfollowed,),
            )
            _insert_upload(conn, rank_200, "yes", "2026-07-03")
            _insert_upload(conn, rank_201, "no", "2026-07-02")
            _insert_upload(conn, unfollowed, "gone", "2026-07-01")
            conn.commit()

        assert [item["soundcloud_id"] for item in get_feed_page(max_rank=200)] == [
            "yes"
        ]

    def test_lazy_materialization_creates_only_requested_repost(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import materialize_feed_track

        with get_db_connection() as conn:
            reposter = _insert_artist(conn, "reposter", rank=1)
            self._insert_repost(conn, reposter, "one", "2026-07-03")
            self._insert_repost(conn, reposter, "two", "2026-07-02")
            conn.commit()

        first = materialize_feed_track("one")
        again = materialize_feed_track("one")
        assert first == again
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, soundcloud_id, local_path FROM tracks"
            ).fetchall()
        assert [
            (row["id"], row["soundcloud_id"], row["local_path"]) for row in rows
        ] == [(first, "one", None)]


class TestCanonicalDecisionLedger:
    def test_rerating_preserves_history_and_one_training_label(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_decision_history, record_decision

        with get_db_connection() as conn:
            artist = _insert_artist(conn)
            _insert_upload(conn, artist, "track", "2026-07-01")
            conn.commit()

        record_decision("track", "keep", "web_feed", "model-1", {"uploader_rank": 1})
        record_decision("track", "hide", "mobile_feed")
        record_decision("track", "nope", "repost_builder")
        history = get_decision_history("track")
        assert [row["decision"] for row in history] == ["keep", "hide", "nope"]
        assert sum(row["is_current"] for row in history) == 1
        assert history[-1]["feature_snapshot"] is None
        with get_db_connection() as conn:
            training = conn.execute(
                """SELECT soundcloud_id, decision FROM sc_track_decisions
                WHERE is_current = 1 AND decision IN ('keep', 'nope')"""
            ).fetchall()
        assert [tuple(row) for row in training] == [("track", "nope")]


class TestDurableFeedActions:
    def test_partial_failure_retry_and_already_done_are_idempotent(
        self, test_db
    ) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.feed_rating import drain_pending_feed_actions
        from web.backend.queries.feed import enqueue_keep_actions, reconcile_actions

        enqueue_keep_actions("track", "Jul 26")
        with (
            patch(
                "web.backend.feed_rating.like_track",
                return_value=(_auth_state(), False, "Already liked"),
            ),
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(_auth_state(), "PL1", None),
            ),
            patch(
                "web.backend.feed_rating.add_track_to_playlist",
                return_value=(_auth_state(), False, "Rate limited"),
            ),
        ):
            assert drain_pending_feed_actions(_auth_state()) == 2

        with get_db_connection() as conn:
            states = {
                row["action_type"]: row["status"]
                for row in conn.execute("SELECT * FROM sc_feed_action_jobs")
            }
        assert states == {"like": "complete", "monthly_playlist": "error"}

        assert reconcile_actions("track") == 1
        with (
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(_auth_state(), "PL1", None),
            ),
            patch(
                "web.backend.feed_rating.add_track_to_playlist",
                return_value=(_auth_state(), False, "Already in playlist"),
            ),
        ):
            assert drain_pending_feed_actions(_auth_state()) == 1
        with get_db_connection() as conn:
            assert {
                row["status"]
                for row in conn.execute("SELECT status FROM sc_feed_action_jobs")
            } == {"complete"}

    def test_restart_recovers_running_job(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import (
            enqueue_keep_actions,
            recover_interrupted_actions,
        )

        enqueue_keep_actions("track", "Jul 26")
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE sc_feed_action_jobs SET status = 'running' "
                "WHERE action_type = 'like'"
            )
            conn.commit()
        assert recover_interrupted_actions() == 1
        with get_db_connection() as conn:
            status = conn.execute(
                "SELECT status FROM sc_feed_action_jobs WHERE action_type = 'like'"
            ).fetchone()["status"]
        assert status == "pending"


# ---------------------------------------------------------------------------
# Unified releases + reposts API (#57) and heart flow by SoundCloud id (#58)
# ---------------------------------------------------------------------------


def _insert_repost_track(
    conn,
    artist_id: int,
    sc_id: str,
    reposted_at: str | None = None,
    seen_at: str = "2026-01-01 00:00:00",
    uploader_sc_id: str = "uploader-1",
) -> int:
    """Repost-only track. reposted_at NULL means only the observation time is known."""
    cursor = conn.execute(
        """INSERT INTO discovery_tracks
        (soundcloud_id, title, artist_name, duration_ms, permalink_url, genre,
         access, uploader_soundcloud_id, first_seen)
        VALUES (?, ?, 'Uploader', 120000, ?, 'house', 'playable', ?, ?)""",
        (
            sc_id,
            f"Track {sc_id}",
            f"https://soundcloud.com/u/{sc_id}",
            uploader_sc_id,
            seen_at,
        ),
    )
    conn.execute(
        """INSERT INTO discovery_track_reposters
        (discovery_track_id, discovery_artist_id, reposted_at, seen_at,
         repost_time_precision)
        VALUES (?, ?, ?, ?, ?)""",
        (
            cursor.lastrowid,
            artist_id,
            reposted_at,
            seen_at,
            "exact" if reposted_at else "approximate",
        ),
    )
    return cursor.lastrowid


def _link_reposter(conn, track_row_id: int, artist_id: int, reposted_at: str) -> None:
    conn.execute(
        """INSERT INTO discovery_track_reposters
        (discovery_track_id, discovery_artist_id, reposted_at, seen_at,
         repost_time_precision) VALUES (?, ?, ?, ?, 'exact')""",
        (track_row_id, artist_id, reposted_at, reposted_at),
    )


def _fetch_all_pages(client, limit: int, **params) -> list[dict]:
    items: list[dict] = []
    cursor = None
    for _ in range(50):
        query = {"limit": limit, **params}
        if cursor:
            query["cursor"] = cursor
        resp = client.get("/api/feed", params=query)
        assert resp.status_code == 200, resp.text
        page = resp.json()
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            return items
    raise AssertionError("pagination never terminated")


class TestUnifiedFeedApi:
    def test_mixed_timestamp_formats_order_by_instant(self, test_db) -> None:
        """Uploads store ISO, SQLite stores 'YYYY-MM-DD HH:MM:SS', exact reposts
        keep SoundCloud's raw 'YYYY/MM/DD ... +0000'. Ordering must follow the
        instant, not the separator character."""
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            uploader = _insert_artist(conn, "up", name="Up")
            reposter = _insert_artist(conn, "re", name="Re")
            _insert_upload(conn, uploader, "iso", "2026-07-02T00:00:00+00:00")
            _insert_repost_track(conn, reposter, "raw", "2026/07/03 00:00:00 +0000")
            _insert_repost_track(conn, reposter, "seen", None, "2026-07-01 00:00:00")
            conn.commit()

        items = get_feed_page(limit=10)
        assert [i["soundcloud_id"] for i in items] == ["raw", "iso", "seen"]
        assert [i["event_at"] for i in items] == [
            "2026-07-03T00:00:00Z",
            "2026-07-02T00:00:00Z",
            "2026-07-01T00:00:00Z",
        ]
        assert items[0]["reposters"][0]["reposted_at"] == "2026-07-03T00:00:00Z"

    def test_cursor_round_trip_has_no_gaps_or_duplicates(self, client) -> None:
        from music_minion.core.database import get_db_connection

        with get_db_connection() as conn:
            uploader = _insert_artist(conn, "up", name="Up")
            reposter = _insert_artist(conn, "re", name="Re")
            for day in range(1, 5):
                _insert_upload(
                    conn, uploader, f"u{day}", f"2026-07-0{day}T12:00:00+00:00"
                )
                _insert_repost_track(
                    conn, reposter, f"r{day}", f"2026/07/0{day} 12:00:00 +0000"
                )
            conn.commit()

        items = _fetch_all_pages(client, limit=3)
        ids = [i["soundcloud_id"] for i in items]
        assert len(ids) == 8 and len(set(ids)) == 8
        # Same-instant pairs tie-break on soundcloud_id DESC, so the sequence
        # must be non-increasing on (event_at, soundcloud_id).
        keys = [(i["event_at"], i["soundcloud_id"]) for i in items]
        assert keys == sorted(keys, reverse=True)

    def test_max_rank_repost_qualifies_via_any_followed_reposter(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page

        with get_db_connection() as conn:
            close = _insert_artist(conn, "close", rank=50, name="Close")
            far = _insert_artist(conn, "far", rank=300, name="Far")
            gone = _insert_artist(conn, "gone", rank=1, name="Gone")
            conn.execute(
                "UPDATE discovery_artists SET is_following = 0 WHERE id = ?", (gone,)
            )
            both = _insert_repost_track(conn, far, "both", "2026/07/03 00:00:00 +0000")
            _link_reposter(conn, both, close, "2026/07/02 00:00:00 +0000")
            _insert_repost_track(conn, far, "far-only", "2026/07/04 00:00:00 +0000")
            only_gone = _insert_repost_track(
                conn, gone, "gone-only", "2026/07/05 00:00:00 +0000"
            )
            assert only_gone
            conn.commit()

        items = get_feed_page(max_rank=200)
        assert [i["soundcloud_id"] for i in items] == ["both"]
        assert items[0]["best_reposter_rank"] == 50
        assert items[0]["reposter_count"] == 1
        assert [r["display_name"] for r in items[0]["reposters"]] == ["Close"]

        unfiltered = {i["soundcloud_id"]: i for i in get_feed_page()}
        assert set(unfiltered) == {"both", "far-only"}
        assert unfiltered["both"]["reposter_count"] == 2

    def test_nope_and_hide_hidden_unless_show_hidden(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import get_feed_page, record_decision

        with get_db_connection() as conn:
            reposter = _insert_artist(conn, "re", name="Re")
            for sc_id in ("kept", "noped", "hidden", "fresh"):
                _insert_repost_track(
                    conn, reposter, sc_id, f"2026/07/0{len(sc_id)} 00:00:00 +0000"
                )
            conn.commit()
        record_decision("kept", "keep", "test")
        record_decision("noped", "nope", "test")
        record_decision("hidden", "hide", "test")

        visible = {i["soundcloud_id"]: i for i in get_feed_page()}
        assert set(visible) == {"kept", "fresh"}
        assert visible["kept"]["current_decision"] == "keep"
        assert visible["kept"]["status"] == "liked"
        assert visible["fresh"]["current_decision"] is None

        everything = {
            i["soundcloud_id"]: i["status"] for i in get_feed_page(show_hidden=True)
        }
        assert everything == {
            "kept": "liked",
            "noped": "dismissed",
            "hidden": "hidden",
            "fresh": "visible",
        }

    def test_limit_and_cursor_validation(self, client) -> None:
        assert client.get("/api/feed", params={"limit": 101}).status_code == 422
        assert client.get("/api/feed", params={"source": "bogus"}).status_code == 422
        assert (
            client.get("/api/feed", params={"cursor": "not-a-cursor"}).status_code
            == 400
        )
        resp = client.get(
            "/api/feed", params={"limit": 100, "source": "reposts", "max_rank": 200}
        )
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "next_cursor": None}


class TestHeartBySoundcloudId:
    def _seed_repost(self) -> int:
        from music_minion.core.database import get_db_connection

        with get_db_connection() as conn:
            reposter = _insert_artist(conn, "re", rank=10, name="Re")
            _insert_repost_track(conn, reposter, "555", "2026/07/03 00:00:00 +0000")
            conn.commit()
        return reposter

    def test_keep_repost_materializes_enqueues_and_trains_reposter(
        self, client
    ) -> None:
        from music_minion.core.database import get_db_connection

        reposter = self._seed_repost()
        with patch("web.backend.routers.feed.enqueue_feed_action_drain") as wake:
            resp = client.post(
                "/api/feed/555/rate", json={"decision": "keep", "surface": "mobile"}
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["current_decision"] == "keep"
        assert body["status"] == "liked"
        assert body["local_track_id"] is not None
        assert body["action_state"] == {
            "like": "pending",
            "monthly_playlist": "pending",
            "error": None,
        }
        wake.assert_called_once()

        with get_db_connection() as conn:
            track = conn.execute(
                "SELECT * FROM tracks WHERE id = ?", (body["local_track_id"],)
            ).fetchone()
            artist = conn.execute(
                "SELECT * FROM discovery_artists WHERE id = ?", (reposter,)
            ).fetchone()
            workflow = conn.execute(
                "SELECT workflow_state, local_track_id FROM discovery_tracks WHERE soundcloud_id = '555'"
            ).fetchone()
        assert track["soundcloud_id"] == "555" and track["local_path"] is None
        assert artist["tracks_liked"] == 1 and artist["tracks_seen"] == 1
        assert tuple(workflow) == ("processed", body["local_track_id"])

    def test_unknown_track_is_404(self, client) -> None:
        resp = client.post("/api/feed/does-not-exist/rate", json={"decision": "keep"})
        assert resp.status_code == 404

    def test_missing_decision_is_422(self, client) -> None:
        self._seed_repost()
        assert (
            client.post("/api/feed/555/rate", json={"surface": "x"}).status_code == 422
        )

    def test_nope_after_keep_cancels_pending_jobs_and_keeps_history(
        self, client
    ) -> None:
        from music_minion.core.database import get_db_connection

        self._seed_repost()
        with patch("web.backend.routers.feed.enqueue_feed_action_drain"):
            client.post("/api/feed/555/rate", json={"decision": "keep"})
            resp = client.post("/api/feed/555/rate", json={"value": -1})
        assert resp.json()["action_state"] == {
            "like": None,
            "monthly_playlist": None,
            "error": None,
        }
        with get_db_connection() as conn:
            assert (
                conn.execute("SELECT COUNT(*) FROM sc_feed_action_jobs").fetchone()[0]
                == 0
            )

        history = client.get("/api/feed/555/decisions").json()["history"]
        assert [h["decision"] for h in history] == ["keep", "nope"]
        assert [h["is_current"] for h in history] == [0, 1]

    def test_materialize_endpoint_is_idempotent(self, client) -> None:
        self._seed_repost()
        first = client.post("/api/feed/555/materialize").json()["local_track_id"]
        second = client.post("/api/feed/555/materialize").json()["local_track_id"]
        assert first == second
        assert client.post("/api/feed/nope/materialize").status_code == 404

    def test_reconcile_endpoint_resets_errored_jobs(self, client) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import (
            claim_due_action,
            enqueue_keep_actions,
            fail_action,
        )

        self._seed_repost()
        enqueue_keep_actions("555", "Jul 26")
        job = claim_due_action()
        fail_action(job["id"], "Rate limit exceeded (429)", 5, 5)
        with get_db_connection() as conn:
            assert (
                conn.execute(
                    "SELECT status FROM sc_feed_action_jobs WHERE id = ?", (job["id"],)
                ).fetchone()[0]
                == "error"
            )

        with patch("web.backend.routers.feed.enqueue_feed_action_drain") as wake:
            resp = client.post(
                "/api/feed/actions/reconcile", params={"soundcloud_id": "555"}
            )
        # The errored job and its still-pending sibling are both made due.
        assert resp.json() == {"reset": 2}
        wake.assert_called_once()
        claimed = {claim_due_action()["id"], claim_due_action()["id"]}
        assert job["id"] in claimed

    def test_rapid_concurrent_hearts_keep_one_current_row_and_two_jobs(
        self, test_db
    ) -> None:
        from concurrent.futures import ThreadPoolExecutor

        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import enqueue_keep_actions, record_decision

        self._seed_repost()

        def heart(n: int) -> None:
            record_decision("555", "keep", f"thread-{n}")
            enqueue_keep_actions("555", "Jul 26")

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(heart, range(8)))

        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT COUNT(*), SUM(is_current) FROM sc_track_decisions WHERE soundcloud_id = '555'"
            ).fetchone()
            jobs = conn.execute("SELECT COUNT(*) FROM sc_feed_action_jobs").fetchone()[
                0
            ]
        assert tuple(rows) == (8, 1)
        assert jobs == 2


class TestTrainingDedup:
    def test_release_plus_multiple_reposts_is_one_training_example(
        self, test_db
    ) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.discovery import recalculate_artist_stats
        from web.backend.queries.feed import record_decision

        with get_db_connection() as conn:
            uploader = _insert_artist(conn, "up", name="Up")
            r1 = _insert_artist(conn, "r1", name="R1")
            r2 = _insert_artist(conn, "r2", name="R2")
            _insert_upload(conn, uploader, "same", "2026-07-01T00:00:00+00:00")
            row = _insert_repost_track(conn, r1, "same", "2026/07/02 00:00:00 +0000")
            _link_reposter(conn, row, r2, "2026/07/03 00:00:00 +0000")
            _link_reposter(conn, row, uploader, "2026/07/04 00:00:00 +0000")
            conn.commit()

        record_decision("same", "keep", "web_feed")
        recalculate_artist_stats()

        with get_db_connection() as conn:
            training = conn.execute(
                "SELECT COUNT(*) FROM sc_current_training_decisions"
            ).fetchone()[0]
            stats = conn.execute(
                "SELECT slug, tracks_seen, tracks_liked FROM discovery_artists ORDER BY slug"
            ).fetchall()
        assert training == 1
        # The uploader both released and reposted it: still one contribution.
        assert [tuple(r) for r in stats] == [("r1", 1, 1), ("r2", 1, 1), ("up", 1, 1)]


class TestActionBackoff:
    def test_backoff_is_bounded_and_terminal_after_max_attempts(self, test_db) -> None:
        from music_minion.core.database import get_db_connection
        from web.backend.queries.feed import (
            claim_due_action,
            enqueue_keep_actions,
            fail_action,
            get_next_action_delay,
        )

        enqueue_keep_actions("t", "Jul 26")
        with get_db_connection() as conn:
            conn.execute("UPDATE sc_feed_action_jobs SET max_attempts = 2")
            conn.commit()

        first = claim_due_action()
        second = claim_due_action()
        assert {first["action_type"], second["action_type"]} == {
            "like",
            "monthly_playlist",
        }
        assert claim_due_action() is None  # both running

        fail_action(first["id"], "Network error", first["attempt_count"], 2)
        fail_action(second["id"], "Network error", second["attempt_count"], 2)
        assert claim_due_action() is None  # not due yet
        assert 0 < get_next_action_delay() <= 30

        with get_db_connection() as conn:
            conn.execute(
                "UPDATE sc_feed_action_jobs SET next_attempt_at = datetime('now', '-1 second')"
            )
            conn.commit()
        retry = claim_due_action()
        assert retry["attempt_count"] == 2
        fail_action(retry["id"], "Network error", 2, 2)
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sc_feed_action_jobs WHERE id = ?", (retry["id"],)
            ).fetchone()
        assert row["status"] == "error" and row["last_error"] == "Network error"
        # Terminal: never claimed again, but stays visible for reconciliation.
        assert claim_due_action()["id"] != retry["id"]
        assert claim_due_action() is None


class TestMonthlyTimezone:
    def test_month_follows_configured_timezone_not_utc(self, monkeypatch) -> None:
        from zoneinfo import ZoneInfo

        from web.backend.feed_rating import monthly_playlist_name

        late_night_utc = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(
            "web.backend.feed_rating.configured_feed_timezone",
            lambda: ZoneInfo("America/Los_Angeles"),
        )
        assert monthly_playlist_name(late_night_utc) == "Jul 26"
        monkeypatch.setattr(
            "web.backend.feed_rating.configured_feed_timezone", lambda: timezone.utc
        )
        assert monthly_playlist_name(late_night_utc) == "Aug 26"
