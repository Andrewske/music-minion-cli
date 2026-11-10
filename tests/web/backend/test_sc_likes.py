"""sc_likes: migration backfill, writers, the shared SQL helper, and every
API that reports sc_liked. Runs on the fully migrated per-test DB."""

from unittest.mock import patch

import pytest

from music_minion.core import database
from music_minion.core.database import (
    _migrate_v71_sc_likes,
    clear_soundcloud_like,
    get_db_connection,
    has_soundcloud_like,
    mark_soundcloud_liked,
    upsert_sc_likes,
)
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from web.backend.feed_rating import process_one_pending_action
from web.backend.queries import artists as artist_queries
from web.backend.queries import feed as feed_queries
from web.backend.queries import insights as insight_queries
from web.backend.queries.tracks import batch_fetch_tracks_with_metadata
from web.backend.routers.playlists import get_playlist_tracks_with_ratings
from web.backend.sc_likes import liked_soundcloud_ids, sc_liked_sql


def _exec(sql: str, params: tuple = ()) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def _likes() -> dict[str, dict]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM sc_likes").fetchall()
    return {row["soundcloud_id"]: dict(row) for row in rows}


def _track(
    sc_id: str | None, artist: str = "Artist", source: str = "soundcloud"
) -> int:
    return _exec(
        """INSERT INTO tracks (title, artist, artist_normalized, soundcloud_id, source)
        VALUES (?, ?, ?, ?, ?)""",
        (f"t {sc_id}", artist, artist.lower(), sc_id, source),
    )


def _rating(track_id: int, source: str, rating_type: str = "like") -> None:
    _exec(
        "INSERT INTO ratings (track_id, rating_type, source) VALUES (?, ?, ?)",
        (track_id, rating_type, source),
    )


def _job(sc_id: str, status: str, action_type: str = "like") -> None:
    target = "" if action_type == "like" else "Nov 26"
    _exec(
        """INSERT INTO sc_feed_action_jobs (soundcloud_id, action_type, target_key, status)
        VALUES (?, ?, ?, ?)""",
        (sc_id, action_type, target, status),
    )


def _auth_state() -> ProviderState:
    return ProviderState(config=ProviderConfig(name="soundcloud"), authenticated=True)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestMigration:
    def _rerun(self) -> None:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM sc_likes")
            _migrate_v71_sc_likes(conn)
            conn.commit()

    def test_backfills_sc_markers_deduped_and_skips_local_likes(self) -> None:
        liked = _track("100")
        _rating(liked, "soundcloud")
        _rating(liked, "soundcloud")  # duplicate marker
        twin = _track("100", source="local")  # second row, same SC id
        _rating(twin, "soundcloud")
        _rating(_track("200"), "user")  # MM-local like, not a SC like
        _rating(_track("300"), "spotify")
        _rating(_track(None), "soundcloud")  # no SC id to key on
        self._rerun()
        likes = _likes()
        assert set(likes) == {"100"}
        assert likes["100"]["source"] == "backfill"
        assert likes["100"]["liked_at"] is None

    def test_backfills_completed_keep_likes_only(self) -> None:
        _job("done", "complete")
        _job("waiting", "pending")
        _job("broken", "error")
        _job("playlist-only", "complete", action_type="monthly_playlist")
        self._rerun()
        likes = _likes()
        assert set(likes) == {"done"}
        assert likes["done"]["source"] == "mm_keep"

    def test_rerun_is_a_no_op(self) -> None:
        _rating(_track("100"), "soundcloud")
        self._rerun()
        with get_db_connection() as conn:
            _migrate_v71_sc_likes(conn)
            conn.commit()
        assert list(_likes()) == ["100"]

    def test_schema_version_is_at_least_71(self) -> None:
        assert database.SCHEMA_VERSION >= 71


# ---------------------------------------------------------------------------
# Writers + helper
# ---------------------------------------------------------------------------


class TestWriters:
    def test_upsert_counts_new_rows_and_keeps_first_source(self) -> None:
        assert upsert_sc_likes(["1", "2", "2", None], "sync") == 2
        assert upsert_sc_likes(["2", "3"], "mm_keep", liked_now=True) == 1
        likes = _likes()
        assert likes["2"]["source"] == "sync"
        assert likes["2"]["liked_at"] is None
        assert likes["3"]["liked_at"] is not None

    def test_upsert_rejects_unknown_source(self) -> None:
        with pytest.raises(ValueError, match="Invalid sc_likes source"):
            upsert_sc_likes(["1"], "user")

    def test_cli_like_and_unlike_keep_sc_likes_in_sync(self) -> None:
        track_id = _track("77")
        assert has_soundcloud_like(track_id) is False
        mark_soundcloud_liked(track_id, "77")
        assert has_soundcloud_like(track_id) is True
        assert _likes()["77"]["source"] == "cli"
        clear_soundcloud_like(track_id, "77")
        assert has_soundcloud_like(track_id) is False
        with get_db_connection() as conn:
            markers = conn.execute(
                "SELECT COUNT(*) FROM ratings WHERE track_id = ? AND source = 'soundcloud'",
                (track_id,),
            ).fetchone()[0]
        assert markers == 0

    def test_has_soundcloud_like_reads_sc_likes_not_markers(self) -> None:
        track_id = _track("88")
        _rating(track_id, "soundcloud")
        assert has_soundcloud_like(track_id) is False
        upsert_sc_likes(["88"], "sync")
        assert has_soundcloud_like(track_id) is True

    def test_sql_helper_and_python_lookup_agree(self) -> None:
        upsert_sc_likes(["a"], "sync")
        with get_db_connection() as conn:
            assert (
                conn.execute(f"SELECT {sc_liked_sql(':id')}", {"id": "a"}).fetchone()[0]
                == 1
            )
            assert (
                conn.execute(f"SELECT {sc_liked_sql(':id')}", {"id": "b"}).fetchone()[0]
                == 0
            )
            assert liked_soundcloud_ids(conn, ["a", "b", None]) == {"a"}
            assert liked_soundcloud_ids(conn, []) == set()

    def test_provider_sync_records_every_fetched_like(self) -> None:
        from music_minion.domain.library.providers.soundcloud import api

        api._record_sc_likes({"5", "6"})
        api._record_sc_likes(set())
        assert set(_likes()) == {"5", "6"}
        assert _likes()["5"]["source"] == "sync"


# ---------------------------------------------------------------------------
# Feed action worker
# ---------------------------------------------------------------------------


class TestWorker:
    def _run(self, like_result: tuple) -> None:
        with patch("web.backend.feed_rating.like_track", return_value=like_result):
            process_one_pending_action(_auth_state())

    def test_successful_like_writes_sc_likes(self) -> None:
        feed_queries.enqueue_keep_actions("900", "Nov 26")
        self._run((_auth_state(), True, None))
        assert _likes()["900"]["source"] == "mm_keep"
        assert _likes()["900"]["liked_at"] is not None

    def test_already_liked_counts_as_liked(self) -> None:
        feed_queries.enqueue_keep_actions("901", "Nov 26")
        self._run((_auth_state(), False, "Track already liked"))
        assert "901" in _likes()

    def test_failed_like_writes_nothing(self) -> None:
        feed_queries.enqueue_keep_actions("902", "Nov 26")
        self._run((_auth_state(), False, "HTTP 500: boom"))
        assert _likes() == {}

    def test_playlist_job_never_writes_a_like(self) -> None:
        _job("903", "pending", action_type="monthly_playlist")
        with (
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(_auth_state(), "PL", None),
            ),
            patch(
                "web.backend.feed_rating.add_track_to_playlist",
                return_value=(_auth_state(), True, None),
            ),
        ):
            process_one_pending_action(_auth_state())
        assert _likes() == {}


# ---------------------------------------------------------------------------
# APIs
# ---------------------------------------------------------------------------


def _artist(slug: str = "uploader") -> int:
    return _exec(
        """INSERT INTO discovery_artists
            (soundcloud_user_id, slug, display_name, ranking, is_following)
        VALUES (?, ?, ?, 1, 1)""",
        (f"u-{slug}", slug, slug.title()),
    )


def _upload(artist_id: int, sc_id: str) -> None:
    _exec(
        """INSERT INTO sc_artist_uploads
            (discovery_artist_id, soundcloud_id, title, uploaded_at, duration_ms)
        VALUES (?, ?, ?, '2026-07-01T00:00:00+00:00', 180000)""",
        (artist_id, sc_id, f"Upload {sc_id}"),
    )


class TestApis:
    def test_feed_items_report_sc_liked_without_a_tracks_row(self, monkeypatch) -> None:
        monkeypatch.setattr("web.backend.queries.feed.FEED_WINDOW_DAYS", None)
        artist = _artist()
        _upload(artist, "liked")
        _upload(artist, "plain")
        upsert_sc_likes(["liked"], "sync")
        items = {i["soundcloud_id"]: i for i in feed_queries.get_feed_page(limit=10)}
        assert items["liked"]["sc_liked"] is True
        assert items["plain"]["sc_liked"] is False
        assert "in_likes" not in items["liked"]

    def test_keep_without_a_landed_like_is_not_sc_liked(self) -> None:
        _upload(_artist(), "kept")
        feed_queries.record_decision("kept", "keep", "test")
        assert feed_queries.is_sc_liked("kept") is False
        upsert_sc_likes(["kept"], "mm_keep")
        assert feed_queries.is_sc_liked("kept") is True

    def test_reviewed_rows_report_sc_liked(self) -> None:
        _upload(_artist(), "r1")
        feed_queries.record_decision("r1", "not_quite", "test")
        upsert_sc_likes(["r1"], "sync")
        [row] = feed_queries.get_reviewed_page()
        assert row["sc_liked"] is True

    def test_insight_tracks_report_sc_liked(self) -> None:
        _upload(_artist(), "i1")
        feed_queries.record_decision("i1", "keep", "test")
        [row] = insight_queries.load_reviewed_tracks()
        assert row["sc_liked"] is False
        upsert_sc_likes(["i1"], "sync")
        [row] = insight_queries.load_reviewed_tracks()
        assert row["sc_liked"] is True

    def test_playlist_tracks_sc_liked_means_sc_likes_not_keep(self) -> None:
        # Live DBs have tracks.released_at; the migrations never add it.
        _exec("ALTER TABLE tracks ADD COLUMN released_at TIMESTAMP")
        liked, kept = _track("pl-liked"), _track("pl-kept")
        playlist = _exec("INSERT INTO playlists (name, type) VALUES ('p', 'manual')")
        for position, track_id in enumerate((liked, kept)):
            _exec(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                (playlist, track_id, position),
            )
        upsert_sc_likes(["pl-liked"], "sync")
        feed_queries.record_decision("pl-kept", "keep", "test")
        tracks, _total = get_playlist_tracks_with_ratings(playlist, sort_field="title")
        by_id = {t["id"]: t["sc_liked"] for t in tracks}
        assert by_id == {liked: True, kept: False}

    def test_player_tracks_carry_sc_liked(self) -> None:
        liked, plain, local = _track("q1"), _track("q2"), _track(None, source="local")
        upsert_sc_likes(["q1"], "sync")
        with get_db_connection() as conn:
            tracks = batch_fetch_tracks_with_metadata([liked, plain, local], conn)
        assert [t["sc_liked"] for t in tracks] == [True, False, False]

    def test_artist_counts_distinct_ids_across_library_and_uploads(self) -> None:
        artist = _artist("djx")
        _exec(
            "INSERT INTO artist_match_overrides (local_artist_name, discovery_artist_id, action)"
            " VALUES ('djx', ?, 'merge')",
            (artist,),
        )
        _track("lib-1", artist="DJX")
        _track("lib-1", artist="DJX", source="local")  # same SC id twice
        _upload(artist, "lib-1")  # and as an upload
        _upload(artist, "up-only")  # liked, no tracks row
        _upload(artist, "not-liked")
        upsert_sc_likes(["lib-1", "up-only"], "sync")
        with get_db_connection() as conn:
            rows = artist_queries.get_artist_stats(
                conn, source="soundcloud", sort="name"
            )
            library = artist_queries.get_artist_library_tracks(conn, artist)
        [stats] = [r for r in rows if r["id"] == artist]
        assert stats["sc_liked_count"] == 2
        assert library is not None
        assert {t["sc_liked"] for t in library} == {True}
        assert "is_liked" not in library[0]
