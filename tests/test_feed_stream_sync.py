"""Tests for the SC-stream feed sync and the adaptive per-artist sweep cadence."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest

from music_minion.core.database import get_db_connection
from tests.test_feed_sync import MINIMAL_SCHEMA_SQL, _auth_state, _mock_response
from web.backend import feed_stream_sync
from web.backend.feed_stream_sync import split_stream_items, sync_from_stream

SINCE = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path, monkeypatch):
    import sqlite3

    db_path = tmp_path / "test.db"
    monkeypatch.setattr("music_minion.core.database.get_database_path", lambda: db_path)
    conn = sqlite3.connect(str(db_path))
    for stmt in MINIMAL_SCHEMA_SQL:
        conn.execute(stmt)
    for column in ("stream_checkpoint_at TEXT", "sweep_last_run_at TEXT"):
        conn.execute(f"ALTER TABLE sc_feed_sync_state ADD COLUMN {column}")
    conn.execute("ALTER TABLE tracks ADD COLUMN updated_at TIMESTAMP")
    conn.execute("INSERT INTO sc_feed_sync_state (id) VALUES (1)")
    conn.executemany(
        """INSERT INTO discovery_artists
            (id, soundcloud_user_id, slug, display_name, is_following)
        VALUES (?, ?, ?, ?, ?)""",
        [(1, "111", "followed", "Followed", 1), (2, "222", "gone", "Gone", 0)],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(
        "web.backend.queries.discovery.recalculate_artist_stats", lambda: None
    )
    return db_path


def _track(sc_id: int, uploader: str, created: str) -> dict[str, Any]:
    return {
        "id": sc_id,
        "title": f"T{sc_id}",
        "permalink": f"t{sc_id}",
        "user": {"id": int(uploader), "username": f"u{uploader}"},
        "duration": 200_000,
        "created_at": created,
        "access": "playable",
    }


def _repost(sc_id: int, reposter: str, at: str) -> dict[str, Any]:
    return {
        "type": "track:repost",
        "created_at": at,
        "reposter": f"soundcloud:users:{reposter}",
        "origin": _track(sc_id, "999", "2026/08/01 00:00:00 +0000"),
    }


def _upload(sc_id: int, uploader: str, at: str) -> dict[str, Any]:
    return {"type": "track", "created_at": at, "origin": _track(sc_id, uploader, at)}


NEW = "2026/09/10 12:00:00 +0000"
OLD = "2026/08/20 12:00:00 +0000"


class TestSplitStreamItems:
    def test_keeps_only_followed_actors_inside_window(self) -> None:
        items = [
            _repost(1, "111", NEW),
            _repost(2, "222", NEW),  # unfollowed reposter
            _repost(3, "111", OLD),  # before window
            _upload(4, "111", NEW),
            _upload(5, "333", NEW),  # unknown uploader
        ]
        events = split_stream_items(items, {"111": 1}, SINCE)

        assert [(t["id"], a, at) for t, a, at in events.reposts] == [(1, 1, NEW)]
        assert {
            a: [t["id"] for t in ts] for a, ts in events.uploads_by_artist.items()
        } == {1: [4]}


class TestSyncFromStream:
    def test_ingests_exact_reposts_uploads_and_advances_checkpoint(self, db) -> None:
        items = [_repost(10, "111", NEW), _upload(11, "111", NEW)]
        with patch.object(
            feed_stream_sync,
            "get_feed_tracks",
            return_value=(_auth_state(), items, None),
        ):
            reposts, uploads = sync_from_stream(_auth_state())

        assert (reposts, uploads) == (1, 1)
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT reposted_at, repost_time_precision FROM discovery_track_reposters"
            ).fetchone()
            upload = conn.execute(
                "SELECT soundcloud_id FROM sc_artist_uploads"
            ).fetchone()
            checkpoint = conn.execute(
                "SELECT stream_checkpoint_at FROM sc_feed_sync_state"
            ).fetchone()[0]
        assert tuple(row) == (NEW, "exact")
        assert upload[0] == "11"
        assert checkpoint is not None

    def test_next_run_reads_from_checkpoint_minus_overlap(self, db) -> None:
        checkpoint = datetime(2026, 9, 20, 6, tzinfo=timezone.utc)
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE sc_feed_sync_state SET stream_checkpoint_at = ?",
                (checkpoint.isoformat(),),
            )
            conn.commit()
        with patch.object(
            feed_stream_sync, "get_feed_tracks", return_value=(_auth_state(), [], None)
        ) as fetch:
            sync_from_stream(_auth_state())

        assert (
            fetch.call_args.args[1] == checkpoint - feed_stream_sync.CHECKPOINT_OVERLAP
        )

    def test_api_error_raises_and_keeps_checkpoint(self, db) -> None:
        with patch.object(
            feed_stream_sync,
            "get_feed_tracks",
            return_value=(_auth_state(), [_repost(10, "111", NEW)], "HTTP 500"),
        ):
            with pytest.raises(RuntimeError, match="HTTP 500"):
                sync_from_stream(_auth_state())

        with get_db_connection() as conn:
            state = conn.execute(
                "SELECT stream_checkpoint_at FROM sc_feed_sync_state"
            ).fetchone()[0]
            reposts = conn.execute(
                "SELECT COUNT(*) FROM discovery_track_reposters"
            ).fetchone()[0]
        assert state is None
        assert reposts == 0


class TestGetFeedTracks:
    def test_stops_paging_once_a_page_reaches_since(self) -> None:
        from music_minion.domain.library.providers.soundcloud.api import get_feed_tracks

        pages = [
            {"collection": [_repost(1, "111", NEW)], "next_href": "https://x/p2"},
            {"collection": [_repost(2, "111", OLD)], "next_href": "https://x/p3"},
            {"collection": [_repost(3, "111", OLD)], "next_href": None},
        ]
        responses = [(_auth_state(), _mock_response(200, p)) for p in pages]
        with patch(
            "music_minion.domain.library.providers.soundcloud.api._request_with_backoff",
            side_effect=responses,
        ) as request:
            _state, items, error = get_feed_tracks(_auth_state(), SINCE)

        assert error is None
        assert request.call_count == 2
        assert [i["origin"]["id"] for i in items] == [1, 2]


class TestSweepCadence:
    def _interval(self, column: str) -> int:
        with get_db_connection() as conn:
            return conn.execute(
                f"SELECT {column} FROM discovery_artists WHERE id = 1"
            ).fetchone()[0]

    def test_repeat_reposts_back_off_instead_of_resetting(self, db) -> None:
        from web.backend.discovery_sync import sync_followings_reposts

        tracks = [_track(50, "999", OLD)]
        with patch(
            "web.backend.discovery_sync.get_user_reposts",
            return_value=(_auth_state(), tracks, None),
        ):
            sync_followings_reposts(_auth_state())
            assert self._interval("check_interval_days") == 1  # new pair found
            with get_db_connection() as conn:
                conn.execute("UPDATE discovery_artists SET last_checked = NULL")
                conn.commit()
            sync_followings_reposts(_auth_state())

        assert self._interval("check_interval_days") == 2

    def test_upload_interval_doubles_when_quiet_and_resets_on_upload(self, db) -> None:
        from web.backend.queries.discovery import update_artist_uploads_last_checked

        update_artist_uploads_last_checked(1, 0)
        update_artist_uploads_last_checked(1, 0)
        assert self._interval("upload_check_interval_hours") == 96
        for _ in range(10):
            update_artist_uploads_last_checked(1, 0)
        assert self._interval("upload_check_interval_hours") == 720
        update_artist_uploads_last_checked(1, 3)
        assert self._interval("upload_check_interval_hours") == 24


class TestWorkerSweepGate:
    def test_sweep_due_after_24h(self, db) -> None:
        from web.backend import sc_feed_worker

        assert sc_feed_worker._sweep_due()  # never swept
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        stale = datetime.now(timezone.utc) - timedelta(hours=25)
        for at, expected in ((recent, False), (stale, True)):
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE sc_feed_sync_state SET sweep_last_run_at = ?",
                    (at.isoformat(),),
                )
                conn.commit()
            assert sc_feed_worker._sweep_due() is expected

    def test_stream_only_run_skips_sweep(self, monkeypatch) -> None:
        from web.backend import sc_feed_worker

        calls: list[str] = []
        monkeypatch.setattr(sc_feed_worker, "_mark_running", lambda: None)
        monkeypatch.setattr(sc_feed_worker, "get_web_provider_state", lambda: object())
        monkeypatch.setattr(
            sc_feed_worker,
            "sync_from_stream",
            lambda s: calls.append("stream") or (2, 1),
        )
        monkeypatch.setattr(
            sc_feed_worker, "_run_sweep", lambda s: calls.append("sweep") or (5, 5)
        )
        monkeypatch.setattr(sc_feed_worker, "_after_ingest", lambda s: None)
        monkeypatch.setattr(sc_feed_worker, "_write_success", lambda e, d, sweep: 0)

        quick = sc_feed_worker._fetch_feed_locked(sweep=False)
        full = sc_feed_worker._fetch_feed_locked(sweep=True)

        assert calls == ["stream", "stream", "sweep"]
        assert (quick["events_added"], quick["uploads_added"]) == (2, 1)
        assert (full["events_added"], full["uploads_added"]) == (7, 6)
