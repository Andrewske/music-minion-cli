"""Followings sync: truncation guard, followed_at, follow_order, tier C for
new follows, record_new_follow, and the nightly worker hook."""

from typing import Any

import pytest

from music_minion.core.database import get_db_connection
from web.backend import sc_feed_worker
from web.backend.queries.artists import (
    followings_abort_reason,
    record_new_follow,
    sync_followings,
)


def add_artist(
    sc_id: str,
    following: int = 1,
    tier: str = "",
    followed_at: str | None = None,
) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO discovery_artists
                (soundcloud_user_id, slug, display_name, ranking, is_following,
                 tier, followed_at)
            VALUES (?, ?, ?, 1, ?, ?, ?)""",
            (sc_id, f"slug{sc_id}", f"Name {sc_id}", following, tier, followed_at),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)


def user(sc_id: str) -> dict[str, Any]:
    return {
        "id": int(sc_id),
        "permalink": f"slug{sc_id}",
        "username": f"User {sc_id}",
        "avatar_url": f"https://img/{sc_id}.jpg",
        "followers_count": 10,
    }


def row(sc_id: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        found = conn.execute(
            "SELECT * FROM discovery_artists WHERE soundcloud_user_id = ?", (sc_id,)
        ).fetchone()
    return dict(found)


def run_sync(sc_ids: list[str]) -> dict[str, Any]:
    with get_db_connection() as conn:
        result = sync_followings(conn, [user(i) for i in sc_ids])
        conn.commit()
    return result


class TestAbortReason:
    def test_empty_fetch_aborts(self) -> None:
        assert followings_abort_reason(0, 0) is not None

    def test_under_80_percent_aborts(self) -> None:
        assert followings_abort_reason(79, 100) is not None

    def test_at_80_percent_is_fine(self) -> None:
        assert followings_abort_reason(80, 100) is None

    def test_first_sync_with_no_follows_is_fine(self) -> None:
        assert followings_abort_reason(5, 0) is None


class TestGuard:
    def test_empty_fetch_writes_nothing(self) -> None:
        add_artist("1")
        result = run_sync([])
        assert result["aborted"] == "fetch returned no followings"
        assert row("1")["is_following"] == 1

    def test_truncated_fetch_writes_nothing(self) -> None:
        for i in range(1, 11):
            add_artist(str(i))
        result = run_sync(["1", "2", "3", "4", "5", "6", "99"])
        assert result["aborted"]
        assert all(row(str(i))["is_following"] == 1 for i in range(1, 11))
        with get_db_connection() as conn:
            assert (
                conn.execute(
                    "SELECT 1 FROM discovery_artists WHERE soundcloud_user_id = '99'"
                ).fetchone()
                is None
            )


class TestFollowedAt:
    def test_existing_follow_stays_null(self) -> None:
        add_artist("1")
        run_sync(["1"])
        assert row("1")["followed_at"] is None

    def test_insert_sets_followed_at(self) -> None:
        add_artist("1")
        run_sync(["1", "2"])
        assert row("2")["followed_at"] is not None
        assert row("2")["is_following"] == 1

    def test_flip_sets_followed_at(self) -> None:
        add_artist("1")
        add_artist("2", following=0)
        run_sync(["1", "2"])
        assert row("2")["followed_at"] is not None

    def test_flip_never_overwrites_followed_at(self) -> None:
        add_artist("1")
        add_artist("2", following=0, followed_at="2026-01-01 00:00:00")
        run_sync(["1", "2"])
        assert row("2")["followed_at"] == "2026-01-01 00:00:00"


class TestFollowOrder:
    def test_order_is_response_position(self) -> None:
        add_artist("1")
        add_artist("2")
        run_sync(["2", "3", "1"])
        assert [row(i)["follow_order"] for i in ("2", "3", "1")] == [0, 1, 2]

    def test_unfollowed_rows_get_null(self) -> None:
        for i in ("1", "2", "3", "4", "5"):
            add_artist(i)
        run_sync(["1", "2", "3", "4", "5"])
        result = run_sync(["1", "2", "3", "4"])
        assert row("5")["follow_order"] is None
        assert row("5")["is_following"] == 0
        assert result["unfollowed_remotely"] == 1


class TestTierC:
    def test_new_follow_gets_tier_c(self) -> None:
        add_artist("1")
        result = run_sync(["1", "2"])
        assert row("2")["tier"] == "C"
        assert result["tiered"] == 1

    def test_existing_untiered_follow_untouched(self) -> None:
        add_artist("1")
        run_sync(["1"])
        assert row("1")["tier"] == ""

    def test_refollow_keeps_tier(self) -> None:
        add_artist("1")
        add_artist("2", following=0, tier="A")
        run_sync(["1", "2"])
        assert row("2")["tier"] == "A"

    def test_refollow_untiered_gets_c(self) -> None:
        add_artist("1")
        add_artist("2", following=0, tier=None)  # type: ignore[arg-type]
        run_sync(["1", "2"])
        assert row("2")["tier"] == "C"

    def test_rankings_recomputed_once_tiered(self) -> None:
        add_artist("1", tier="S")
        run_sync(["1", "2"])
        assert row("1")["ranking"] == 1
        assert row("2")["ranking"] == 2


class TestRecordNewFollow:
    def _record(self, sc_user: dict[str, Any]) -> int:
        with get_db_connection() as conn:
            artist_id = record_new_follow(conn, sc_user)
            conn.commit()
        return artist_id

    def test_inserts_followed_tier_c(self) -> None:
        artist_id = self._record(user("7"))
        found = row("7")
        assert found["id"] == artist_id
        assert (found["is_following"], found["tier"]) == (1, "C")
        assert found["followed_at"] is not None
        assert found["display_name"] == "User 7"

    def test_refollow_keeps_tier_and_followed_at(self) -> None:
        artist_id = add_artist("7", following=0, tier="B", followed_at="2026-02-02")
        assert self._record(user("7")) == artist_id
        found = row("7")
        assert (found["is_following"], found["tier"]) == (1, "B")
        assert found["followed_at"] == "2026-02-02"

    def test_stub_user_keeps_known_name(self) -> None:
        add_artist("7", following=0)
        self._record({"id": "7"})
        assert row("7")["display_name"] == "Name 7"

    def test_rejects_user_without_id(self) -> None:
        with pytest.raises(ValueError, match="no id"):
            self._record({"username": "x"})


class TestWorker:
    @pytest.fixture
    def fetched(self, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
        from music_minion.domain.library.providers.soundcloud import api

        response: list[dict[str, Any]] = []
        monkeypatch.setattr(sc_feed_worker, "get_web_provider_state", lambda: object())
        monkeypatch.setattr(api, "get_followings", lambda state: (state, response))
        return response

    def test_due_when_followed_row_unstamped(self) -> None:
        add_artist("1")
        assert sc_feed_worker._followings_last_synced_at() is None

    def test_single_follow_does_not_defer_sync(self) -> None:
        add_artist("1")
        run_sync(["1"])
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE discovery_artists SET last_sc_sync_at = '2026-01-01 00:00:00'"
            )
            conn.commit()
        with get_db_connection() as conn:
            record_new_follow(conn, user("2"))
            conn.commit()
        assert sc_feed_worker._followings_last_synced_at() == "2026-01-01 00:00:00"

    def test_runs_sync_when_due(self, fetched: list[dict[str, Any]]) -> None:
        add_artist("1")
        fetched.extend([user("1"), user("2")])
        sc_feed_worker._maybe_sync_followings()
        assert row("2")["tier"] == "C"
        assert sc_feed_worker._followings_last_synced_at() is not None

    def test_skips_when_recently_synced(self, fetched: list[dict[str, Any]]) -> None:
        add_artist("1")
        run_sync(["1"])
        fetched.extend([user("1"), user("2")])
        sc_feed_worker._maybe_sync_followings()
        with get_db_connection() as conn:
            assert (
                conn.execute(
                    "SELECT 1 FROM discovery_artists WHERE soundcloud_user_id = '2'"
                ).fetchone()
                is None
            )

    def test_empty_fetch_keeps_follows(self, fetched: list[dict[str, Any]]) -> None:
        add_artist("1")
        sc_feed_worker._maybe_sync_followings()
        assert row("1")["is_following"] == 1
        assert sc_feed_worker._followings_last_synced_at() is None
