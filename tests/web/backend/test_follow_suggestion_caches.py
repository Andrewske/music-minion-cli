"""Nightly follow-suggestion cache job: name search, activity, own account."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud import api as sc_api
from web.backend import follow_suggestion_caches as caches

NOW = datetime(2026, 11, 11, tzinfo=UTC)


class _Resp:
    def __init__(self, data: object) -> None:
        self._data = data

    def json(self) -> object:
        return self._data


def _exec(sql: str, params: tuple = ()) -> None:
    with get_db_connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def _rows(sql: str) -> list[tuple]:
    with get_db_connection() as conn:
        return [tuple(r) for r in conn.execute(sql).fetchall()]


def _profile(_state: object, user_id: str) -> tuple[None, dict, None]:
    """get_user stub: the profile of whichever account was asked for."""
    return None, {"id": int(user_id), "username": f"U{user_id}"}, None


def _sc_time(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y/%m/%d %H:%M:%S +0000")


def _suggestion(key: str, evidence_score: float, tracks: int) -> dict:
    return {
        "key": key,
        "soundcloud_user_id": None if key.startswith("name:") else key,
        "display_name": key,
        "evidence_score": evidence_score,
        "evidence": {"original": tracks},
    }


class TestPure:
    def test_pick_search_match_exact_key_most_followers(self) -> None:
        users = [
            {"id": 1, "username": "Eater", "followers_count": 10},
            {"id": 2, "username": "EATER ✦", "followers_count": 5000},
            {"id": 3, "username": "Eater Fan Page", "followers_count": 99999},
            {"id": 4, "username": "x", "permalink": "eater", "followers_count": 20},
        ]
        assert caches.pick_search_match(users, "eater")["id"] == 2
        assert caches.pick_search_match(users[2:3], "eater") is None

    def test_names_to_search(self) -> None:
        ranked = [
            _suggestion("name:small", 9.0, 2),
            _suggestion("name:big", 3.0, 3),
            _suggestion("name:bigger", 5.0, 4),
            _suggestion("name:missed", 6.0, 5),
            _suggestion("70", 10.0, 9),
        ]
        names = caches.names_to_search(ranked, {"missed"}, limit=10)
        assert names == [("bigger", "name:bigger"), ("big", "name:big")]
        assert caches.names_to_search(ranked, set(), limit=1) == [
            ("missed", "name:missed")
        ]

    def test_accounts_to_refresh(self) -> None:
        ranked = [_suggestion(k, s, 1) for k, s in (("1", 3), ("2", 2), ("3", 1))]
        ranked.append(_suggestion("name:x", 9, 5))
        fetched = {"1": "2026-11-10 00:00:00", "2": "2026-10-01 00:00:00"}
        assert caches.accounts_to_refresh(ranked, fetched, NOW, 10) == ["2", "3"]
        assert caches.accounts_to_refresh(ranked, fetched, NOW, 1) == ["2"]

    def test_accounts_to_refresh_stops_at_pool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(caches, "ACTIVITY_POOL", 2)
        ranked = [_suggestion(k, s, 1) for k, s in (("1", 3), ("2", 2), ("3", 1))]
        fetched = {"1": "2026-11-10 00:00:00"}  # fresh; 2 and 3 are stale
        assert caches.accounts_to_refresh(ranked, fetched, NOW, 10) == ["2"]

    def test_looks_like_label(self) -> None:
        own = [{"metadata_artist": "Wooli x Trivecta"}, {"title": "Wooli - Song"}] * 2
        assert not caches.looks_like_label("Wooli", own)
        label = [
            {"metadata_artist": "A"},
            {"title": "B - Song"},
            {"metadata_artist": "C"},
        ]
        assert caches.looks_like_label("Monstercat", label)
        assert not caches.looks_like_label("Monstercat", label[:2])  # too few

    def test_uploads_without_credits_are_not_a_label(self) -> None:
        """Eater's own tracks carry no metadata_artist and no 'X - ' credit."""
        uploads = [{"title": t} for t in ("Echoes", "Orbit", "Pulse")]
        assert not caches.looks_like_label("Eater", uploads)
        uploads.append({"title": "Pulse", "metadata_artist": ""})
        assert not caches.looks_like_label("Eater", uploads)

    def test_unknown_uploads_dilute_explicit_credits(self) -> None:
        mixed = [{"metadata_artist": "A"}, {"title": "B - Song"}] + [
            {"title": "Untitled"}
        ] * 2
        assert not caches.looks_like_label("Channel", mixed)  # 2 of 4 credit others
        assert caches.looks_like_label("Channel", mixed[:2] + [{"title": "C - X"}])

    def test_summarize_activity(self) -> None:
        user = {
            "username": "U",
            "permalink": "u",
            "avatar_url": "a",
            "followers_count": 9,
        }
        uploads = [{"created_at": _sc_time(10)}, {"created_at": _sc_time(200)}]
        reposts = [
            {"created_at": _sc_time(400), "reposted_at": _sc_time(5)},
            {"created_at": _sc_time(30)},
            {"created_at": _sc_time(300)},
        ]
        row = caches.summarize_activity(user, uploads, reposts, NOW)
        assert row["followers"] == 9 and row["username"] == "U"
        assert row["uploads_90d"] == 1 and row["reposts_90d"] == 2
        assert row["last_upload_at"].startswith("2026-11-01")
        assert row["last_repost_at"].startswith("2026-11-06")

    def test_summarize_activity_falls_back_to_upload_user(self) -> None:
        uploads = [{"created_at": _sc_time(1), "user": {"username": "From Track"}}]
        assert (
            caches.summarize_activity(None, uploads, [], NOW)["username"]
            == "From Track"
        )


def _seed_likes() -> None:
    """Eater credited on 3 liked tracks (no uploader), account 70 uploaded 2."""
    for i in range(3):
        _exec(f"INSERT INTO sc_likes (soundcloud_id, source) VALUES ('e{i}', 'sync')")
        _exec(
            f"""INSERT INTO tracks (title, artist, soundcloud_id, source)
            VALUES ('Song {i}', 'Eater', 'e{i}', 'soundcloud')"""
        )
    for i in range(2):
        _exec(
            f"""INSERT INTO sc_likes (soundcloud_id, source, uploader_soundcloud_id,
            uploader_username) VALUES ('p{i}', 'sync', '70', 'PHRVA')"""
        )


class TestJob:
    def _run(self, search_result: list[dict]) -> caches.CacheRunStats:
        with (
            patch.object(caches, "get_me", return_value=(None, {"id": 555}, None)),
            patch.object(caches, "search_users", return_value=(None, search_result, None)) as search,
            patch.object(caches, "get_user", side_effect=_profile),
            patch.object(caches, "get_user_tracks", return_value=(None, [], None)),
            patch.object(caches, "get_user_reposts", return_value=(None, [], None)),
        ):  # fmt: skip
            stats = caches.refresh_follow_suggestion_caches(None)
        self.search_calls = search.call_count
        return stats

    def test_resolves_names_and_refreshes_activity(self) -> None:
        _seed_likes()
        stats = self._run([{"id": 42, "username": "EATER", "permalink": "eater"}])
        assert stats == caches.CacheRunStats(1, 1, 2)
        assert ("eater", "42", "medium", "search") in _rows(
            "SELECT name_key, soundcloud_user_id, confidence, source FROM sc_name_resolutions"
        )
        refreshed = {
            r[0] for r in _rows("SELECT soundcloud_user_id FROM sc_account_activity")
        }
        assert refreshed == {"70", "42"}  # the newly resolved account too
        assert ("555",) in _rows(
            "SELECT soundcloud_user_id FROM follow_suggestion_dismissals"
        )

    def test_miss_is_cached_and_not_searched_again(self) -> None:
        _seed_likes()
        self._run([{"id": 9, "username": "Eater Fan Page"}])
        assert ("eater", None, "none") in _rows(
            "SELECT name_key, soundcloud_user_id, confidence FROM sc_name_resolutions"
        )
        stats = self._run([])
        assert stats.names_searched == 0 and self.search_calls == 0
        assert stats.activity_refreshed == 0  # fetched under a week ago

    def test_stops_on_auth_error(self) -> None:
        _seed_likes()
        with (
            patch.object(caches, "get_me", return_value=(None, None, "HTTP 401")),
            patch.object(caches, "search_users", return_value=(None, [], "HTTP 401")),
            patch.object(caches, "get_user", return_value=(None, None, "HTTP 401")),
            patch.object(caches, "get_user_tracks") as tracks,
        ):
            stats = caches.refresh_follow_suggestion_caches(None)
        assert stats == caches.CacheRunStats(0, 0, 0, "HTTP 401")
        tracks.assert_not_called()


def _refresh(user_ids: list[str]) -> tuple[int, str | None]:
    with get_db_connection() as conn:
        _s, done, stopped = caches.refresh_activity(None, conn, user_ids, NOW)
    return done, stopped


class TestServiceErrors:
    def test_is_service_error(self) -> None:
        service = ["HTTP 0", "HTTP 401", "HTTP 429", "HTTP 500", "HTTP 503",
                   "Rate limited", "Authentication failed", "Request timed out",
                   "Connection error", "ConnectionError", "ReadTimeout"]  # fmt: skip
        account = ["HTTP 404", "HTTP 403", "HTTP 400", "User 70 not found",
                   "Invalid JSON response", "Malformed response: {'errors': []}",
                   "followings of 7 incomplete: pagination repeated x"]  # fmt: skip
        assert all(caches.is_service_error(e) for e in service)
        assert not any(caches.is_service_error(e) for e in account)

    @staticmethod
    def _old_activity(user_id: str) -> None:
        _exec(
            """INSERT INTO sc_account_activity
                (soundcloud_user_id, username, uploads_90d, reposts_90d,
                 last_upload_at, fetched_at)
            VALUES (?, 'Old', 7, 3, '2026-10-01T00:00:00+00:00', '2026-01-01 00:00:00')""",
            (user_id,),
        )

    @staticmethod
    def _activity(user_id: str) -> tuple:
        return _rows(
            f"""SELECT username, uploads_90d, reposts_90d, last_upload_at, fetched_at
            FROM sc_account_activity WHERE soundcloud_user_id = '{user_id}'"""
        )[0]

    def test_failed_uploads_fetch_keeps_old_row(self) -> None:
        self._old_activity("70")
        before = self._activity("70")
        with (
            patch.object(caches, "get_user", return_value=(None, {"id": 70}, None)),
            patch.object(caches, "get_user_tracks", return_value=(None, [], "User 70 not found")),
            patch.object(caches, "get_user_reposts", return_value=(None, [], None)),
        ):  # fmt: skip
            done, stopped = _refresh(["70"])
        assert (done, stopped) == (0, None)
        assert self._activity("70") == before

    def test_failed_reposts_fetch_skips_account_and_continues(self) -> None:
        self._old_activity("70")
        before = self._activity("70")
        reposts = [(None, [], "HTTP 404"), (None, [], None)]
        with (
            patch.object(caches, "get_user", side_effect=_profile),
            patch.object(caches, "get_user_tracks", return_value=(None, [], None)),
            patch.object(caches, "get_user_reposts", side_effect=reposts),
        ):
            done, stopped = _refresh(["70", "71"])
        assert (done, stopped) == (1, None)
        assert self._activity("70") == before
        assert self._activity("71")[1] == 0

    def test_errors_body_keeps_old_row_and_continues(self) -> None:
        """An HTTP 200 {"errors": [...]} feed is malformed, not an empty feed:
        the account keeps its 7/3 counts and old fetched_at; the next one runs."""
        self._old_activity("70")
        before = self._activity("70")
        errors_body = _Resp({"errors": [{"error_message": "nope"}]})
        good = _Resp({"collection": [{"id": 1, "created_at": _sc_time(3)}]})
        with (
            patch.object(caches, "get_user", side_effect=_profile),
            patch.object(sc_api, "_request_with_backoff",
                         side_effect=[(None, errors_body), (None, good), (None, good)]),
        ):  # fmt: skip
            done, stopped = _refresh(["70", "71"])
        assert (done, stopped) == (1, None)
        assert self._activity("70") == before
        assert self._activity("71")[1:3] == (1, 1)

    def test_profile_for_another_account_keeps_old_row(self) -> None:
        self._old_activity("70")
        before = self._activity("70")
        with (
            patch.object(caches, "get_user", return_value=(None, {"id": 99}, None)),
            patch.object(caches, "get_user_tracks") as tracks,
        ):
            done, stopped = _refresh(["70"])
        assert (done, stopped) == (0, None)
        assert self._activity("70") == before
        tracks.assert_not_called()

    def test_profile_5xx_stops_the_run(self) -> None:
        self._old_activity("70")
        before = self._activity("70")
        with (
            patch.object(caches, "get_user", return_value=(None, None, "HTTP 503")) as user,
            patch.object(caches, "get_user_tracks") as tracks,
        ):  # fmt: skip
            done, stopped = _refresh(["70", "71", "72"])
        assert (done, stopped) == (0, "HTTP 503")
        assert user.call_count == 1
        tracks.assert_not_called()
        assert self._activity("70") == before

    def test_uploads_connection_error_stops_the_run(self) -> None:
        with (
            patch.object(caches, "get_user", side_effect=_profile) as user,
            patch.object(caches, "get_user_tracks", return_value=(None, [], "Connection error")),
        ):  # fmt: skip
            done, stopped = _refresh(["70", "71"])
        assert (done, stopped) == (0, "Connection error")
        assert user.call_count == 1

    def test_search_5xx_stops_without_recording_a_miss(self) -> None:
        with patch.object(
            caches, "search_users", return_value=(None, [], "HTTP 503")
        ) as search:
            _s, found, stopped = caches.search_names(None, [("a", "A"), ("b", "B")])
        assert (found, stopped) == ({}, "HTTP 503")
        assert search.call_count == 1

    def test_search_account_error_records_nothing_and_continues(self) -> None:
        results = [(None, [], "HTTP 400"), (None, [{"id": 5, "username": "B"}], None)]
        with patch.object(caches, "search_users", side_effect=results):
            _s, found, stopped = caches.search_names(None, [("a", "A"), ("b", "B")])
        assert stopped is None
        assert set(found) == {"b"} and found["b"].soundcloud_user_id == "5"

    def test_search_outage_skips_activity_and_caches_no_miss(self) -> None:
        _seed_likes()
        with (
            patch.object(caches, "get_me", return_value=(None, {"id": 555}, None)),
            patch.object(caches, "search_users", return_value=(None, [], "HTTP 502")),
            patch.object(caches, "get_user") as user,
        ):
            stats = caches.refresh_follow_suggestion_caches(None)
        assert stats == caches.CacheRunStats(0, 0, 0, "HTTP 502")
        user.assert_not_called()
        assert _rows("SELECT 1 FROM sc_name_resolutions WHERE source = 'search'") == []

    def test_me_outage_stops_before_any_lookup(self) -> None:
        with (
            patch.object(caches, "get_me", return_value=(None, None, "HTTP 500")),
            patch.object(caches, "search_users") as search,
        ):
            stats = caches.refresh_follow_suggestion_caches(None)
        assert stats.stopped == "HTTP 500"
        search.assert_not_called()


class TestWorkerHook:
    def test_failure_never_escapes(self) -> None:
        from web.backend import sc_feed_worker

        with patch.object(
            caches, "refresh_follow_suggestion_caches", side_effect=RuntimeError("boom")
        ):
            sc_feed_worker._refresh_follow_suggestion_caches(None)  # no raise


class TestTrackPageShape:
    def test_errors_body_is_malformed_not_empty(self) -> None:
        body = (None, _Resp({"errors": [{"error_message": "x"}]}))
        for fetch in (sc_api.get_user_tracks, sc_api.get_user_reposts):
            with patch.object(sc_api, "_request_with_backoff", return_value=body):
                _s, items, error = fetch(None, "70", max_pages=1)
            assert items == [] and error.startswith("Malformed response")
            assert not caches.is_service_error(error)

    def test_non_object_items_are_malformed(self) -> None:
        body = (None, _Resp({"collection": [{"id": 1}, "junk"]}))
        with patch.object(sc_api, "_request_with_backoff", return_value=body):
            _s, items, error = sc_api.get_user_tracks(None, "70", max_pages=1)
        assert items == [] and error.startswith("Malformed response")

    def test_list_and_paged_bodies_still_parse(self) -> None:
        pages = [
            (None, _Resp({"collection": [{"id": 1}, None], "next_href": "https://n"})),
            (None, _Resp([{"id": 2}])),
        ]
        with patch.object(sc_api, "_request_with_backoff", side_effect=pages):
            _s, items, error = sc_api.get_user_reposts(None, "70", max_pages=3)
        assert error is None and [t["id"] for t in items] == [1, 2]
