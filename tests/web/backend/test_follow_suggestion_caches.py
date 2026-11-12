"""Nightly follow-suggestion cache job: name search, activity, own account."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from music_minion.core.database import get_db_connection
from web.backend import follow_suggestion_caches as caches

NOW = datetime(2026, 11, 11, tzinfo=UTC)


def _exec(sql: str, params: tuple = ()) -> None:
    with get_db_connection() as conn:
        conn.execute(sql, params)
        conn.commit()


def _rows(sql: str) -> list[tuple]:
    with get_db_connection() as conn:
        return [tuple(r) for r in conn.execute(sql).fetchall()]


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
        user = {"id": 70, "username": "PHRVA", "followers_count": 1000}
        with (
            patch.object(caches, "get_me", return_value=(None, {"id": 555}, None)),
            patch.object(caches, "search_users", return_value=(None, search_result, None)) as search,
            patch.object(caches, "get_user", return_value=(None, user, None)),
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
        assert stats == caches.CacheRunStats(0, 0, 0)
        tracks.assert_not_called()


class TestWorkerHook:
    def test_failure_never_escapes(self) -> None:
        from web.backend import sc_feed_worker

        with patch.object(
            caches, "refresh_follow_suggestion_caches", side_effect=RuntimeError("boom")
        ):
            sc_feed_worker._refresh_follow_suggestion_caches(None)  # no raise
