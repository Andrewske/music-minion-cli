"""Full SC likes fetch + reconcile: completeness, safety rails, and the
nightly schedule. HTTP is always mocked; the DB is the per-test migrated copy."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import requests

from music_minion.core.database import (
    apply_sc_likes_reconcile,
    get_db_connection,
    upsert_sc_likes,
)
from music_minion.domain.library.providers.soundcloud import (
    likes_fetch,
    likes_reconcile,
)
from music_minion.domain.library.providers.soundcloud.likes_fetch import (
    LikesSnapshot,
    fetch_all_liked_ids,
)
from music_minion.domain.library.providers.soundcloud.likes_reconcile import (
    mass_delete_threshold,
    plan_reconcile,
    reconcile_sc_likes,
)
from web.backend import sc_feed_worker

PAGE2 = "https://api.soundcloud.com/me/likes/tracks?cursor=2"
PAGE3 = "https://api.soundcloud.com/me/likes/tracks?cursor=3"
OLD = "2026-01-01 00:00:00"


class FakeResponse:
    def __init__(self, status: int, payload: Any = None) -> None:
        self.status_code = status
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _page(ids: list[str], next_href: str | None = None) -> dict:
    return {
        "collection": [{"kind": "track", "id": int(i), "title": f"T{i}"} for i in ids],
        "next_href": next_href,
    }


def fake_get(pages: dict[str, FakeResponse], calls: list | None = None) -> Any:
    """requests.get stand-in keyed by URL; records (url, params)."""

    def _get(url: str, params: dict, headers: dict, timeout: int) -> FakeResponse:
        if calls is not None:
            calls.append((url, dict(params)))
        return pages[url]

    return _get


def _three_pages() -> dict[str, FakeResponse]:
    return {
        likes_fetch.LIKES_URL: FakeResponse(200, _page(["1", "2"], PAGE2)),
        PAGE2: FakeResponse(200, _page(["3", "4"], PAGE3)),
        PAGE3: FakeResponse(200, _page(["5"])),
    }


def _snapshot(ids: set[str], complete: bool = True) -> LikesSnapshot:
    return LikesSnapshot(frozenset(ids), complete, "test", 1)


def _likes() -> set[str]:
    with get_db_connection() as conn:
        return {r[0] for r in conn.execute("SELECT soundcloud_id FROM sc_likes")}


def _exec(sql: str, params: tuple = ()) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def _seed_likes(ids: list[str], synced_at: str = OLD) -> None:
    upsert_sc_likes(ids, "sync")
    _exec("UPDATE sc_likes SET synced_at = ?", (synced_at,))


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, pages: dict) -> None:
    real = likes_fetch.fetch_all_liked_ids
    monkeypatch.setattr(
        likes_reconcile,
        "fetch_all_liked_ids",
        lambda token: real(token, http_get=fake_get(pages)),
    )


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


class TestFetch:
    def test_complete_multi_page_fetch(self) -> None:
        calls: list = []
        snap = fetch_all_liked_ids("tok", http_get=fake_get(_three_pages(), calls))
        assert snap.complete and snap.reason == "complete"
        assert snap.ids == {"1", "2", "3", "4", "5"}
        assert snap.pages == 3
        assert calls[0][1]["access"] == "playable,preview,blocked"
        assert calls[1] == (PAGE2, {})  # next_href carries its own params

    def test_error_on_page_two_is_incomplete(self) -> None:
        pages = _three_pages()
        pages[PAGE2] = FakeResponse(500)
        snap = fetch_all_liked_ids("tok", http_get=fake_get(pages))
        assert not snap.complete
        assert "HTTP 500" in snap.reason and "page 2" in snap.reason
        assert snap.ids == {"1", "2"}

    def test_auth_error_is_incomplete(self) -> None:
        pages = {likes_fetch.LIKES_URL: FakeResponse(401)}
        snap = fetch_all_liked_ids("tok", http_get=fake_get(pages))
        assert not snap.complete and "auth error" in snap.reason

    def test_network_error_and_bad_json_are_incomplete(self) -> None:
        def boom(*_a: Any, **_k: Any) -> None:
            raise requests.ConnectionError("down")

        assert not fetch_all_liked_ids("tok", http_get=boom).complete
        bad = {likes_fetch.LIKES_URL: FakeResponse(200, ValueError("not json"))}
        assert not fetch_all_liked_ids("tok", http_get=fake_get(bad)).complete

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {"next_href": None},
            {"collection": [None]},
            {"collection": [{"kind": "playlist", "id": 9}]},
            {"collection": [{"kind": "track"}]},
        ],
    )
    def test_unexpected_payload_is_incomplete(self, payload: Any) -> None:
        pages = {likes_fetch.LIKES_URL: FakeResponse(200, payload)}
        assert not fetch_all_liked_ids("tok", http_get=fake_get(pages)).complete

    def test_pagination_loop_is_incomplete(self) -> None:
        pages = {likes_fetch.LIKES_URL: FakeResponse(200, _page(["1"], PAGE2))}
        pages[PAGE2] = FakeResponse(200, _page(["2"], PAGE2))
        snap = fetch_all_liked_ids("tok", http_get=fake_get(pages))
        assert not snap.complete and "loop" in snap.reason


# ---------------------------------------------------------------------------
# Planner (pure)
# ---------------------------------------------------------------------------


class TestPlan:
    def test_adds_and_removes(self) -> None:
        current = {"a": OLD, "b": OLD}
        plan = plan_reconcile(current, _snapshot({"b", "c"}), "2026-06-01 00:00:00")
        assert plan.to_add == {"c"} and plan.to_remove == {"a"}
        assert plan.guard is None

    def test_incomplete_never_removes_even_forced(self) -> None:
        plan = plan_reconcile(
            {"a": OLD}, _snapshot({"b"}, complete=False), "2026-06-01", force=True
        )
        assert plan.guard and plan.guard.startswith("incomplete")
        assert plan.to_add == {"b"}

    def test_empty_fetch_needs_force(self) -> None:
        current = {"a": OLD}
        assert plan_reconcile(current, _snapshot(set()), "2026-06-01").guard == (
            "empty fetch"
        )
        assert (
            plan_reconcile(current, _snapshot(set()), "2026-06-01", True).guard is None
        )

    def test_mass_delete_guard(self) -> None:
        current = {str(i): OLD for i in range(1000)}
        kept = {str(i) for i in range(1000 - 50)}  # 50 > max(25, 5% of 1000)
        plan = plan_reconcile(current, _snapshot(kept), "2026-06-01")
        assert mass_delete_threshold(1000) == 50
        assert plan.guard is None
        kept.discard("0")
        plan = plan_reconcile(current, _snapshot(kept), "2026-06-01")
        assert plan.guard == "mass delete: 51 > 50"
        assert (
            plan_reconcile(current, _snapshot(kept), "2026-06-01", True).guard is None
        )

    def test_small_library_floor(self) -> None:
        assert mass_delete_threshold(100) == 25

    def test_row_written_after_fetch_start_is_protected(self) -> None:
        current = {"old": OLD, "new": "2026-06-01 00:00:05"}
        plan = plan_reconcile(current, _snapshot({"x"}), "2026-06-01 00:00:05")
        assert plan.to_remove == {"old"} and plan.protected == {"new"}


# ---------------------------------------------------------------------------
# Apply + end to end
# ---------------------------------------------------------------------------


def _track_with_marker(sc_id: str) -> int:
    track_id = _exec(
        "INSERT INTO tracks (title, artist, soundcloud_id, source) VALUES (?, ?, ?, ?)",
        (f"Title {sc_id}", "Artist", sc_id, "soundcloud"),
    )
    _exec(
        "INSERT INTO ratings (track_id, rating_type, source) VALUES (?, 'like', 'soundcloud')",
        (track_id,),
    )
    _exec(
        "INSERT INTO ratings (track_id, rating_type, source) VALUES (?, 'love', 'user')",
        (track_id,),
    )
    return track_id


def _ratings(track_id: int) -> set[tuple[str, str]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT rating_type, source FROM ratings WHERE track_id = ?", (track_id,)
        ).fetchall()
    return {(r[0], r[1]) for r in rows}


class TestApply:
    def test_removes_like_and_soundcloud_marker_only(self) -> None:
        track_id = _track_with_marker("1")
        _seed_likes(["1", "2"])
        assert apply_sc_likes_reconcile([], ["1"], "2026-06-01 00:00:00") == (0, 1)
        assert _likes() == {"2"}
        assert _ratings(track_id) == {("love", "user")}

    def test_concurrent_like_survives_apply(self) -> None:
        _seed_likes(["1"])
        upsert_sc_likes(["1"], "mm_keep", liked_now=True)  # re-liked in-app now
        assert apply_sc_likes_reconcile([], ["1"], "2026-01-02 00:00:00") == (0, 0)
        assert _likes() == {"1"}

    def test_adds_like_and_missing_marker(self) -> None:
        track_id = _exec(
            "INSERT INTO tracks (title, artist, soundcloud_id, source) VALUES ('t', 'a', '7', 'soundcloud')"
        )
        assert apply_sc_likes_reconcile(["7"], [], OLD) == (1, 0)
        assert apply_sc_likes_reconcile(["7"], [], OLD) == (0, 0)
        assert _ratings(track_id) == {("like", "soundcloud")}


class TestReconcileRun:
    def test_dry_run_writes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _track_with_marker("9")
        _seed_likes(["9", "1"])
        _patch_fetch(monkeypatch, _three_pages())
        report = reconcile_sc_likes("tok")
        assert (report.to_add, report.to_remove, report.applied) == (4, 1, False)
        assert report.remove_sample == ["Artist - Title 9 (9)"]
        assert _likes() == {"9", "1"}

    def test_apply_end_to_end(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_likes(["9", "1"])
        _patch_fetch(monkeypatch, _three_pages())
        report = reconcile_sc_likes("tok", apply=True)
        assert (report.added, report.removed) == (4, 1)
        assert _likes() == {"1", "2", "3", "4", "5"}

    def test_page_two_error_deletes_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_likes(["9"])
        pages = _three_pages()
        pages[PAGE2] = FakeResponse(503)
        _patch_fetch(monkeypatch, pages)
        report = reconcile_sc_likes("tok", apply=True, force=True)
        assert not report.complete and report.removed == 0
        assert report.skipped_by_guard == 1
        assert _likes() == {"9", "1", "2"}  # page 1 adds still land

    def test_auth_error_deletes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_likes(["9"])
        _patch_fetch(monkeypatch, {likes_fetch.LIKES_URL: FakeResponse(403)})
        report = reconcile_sc_likes("tok", apply=True)
        assert not report.complete and _likes() == {"9"}

    def test_empty_list_needs_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_likes(["9", "8"])
        _patch_fetch(monkeypatch, {likes_fetch.LIKES_URL: FakeResponse(200, _page([]))})
        report = reconcile_sc_likes("tok", apply=True)
        assert report.guard == "empty fetch" and _likes() == {"9", "8"}
        assert reconcile_sc_likes("tok", apply=True, force=True).removed == 2
        assert _likes() == set()

    def test_mass_delete_guard_skips_and_warns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_likes([str(i) for i in range(100, 130)] + ["1"])
        _patch_fetch(
            monkeypatch, {likes_fetch.LIKES_URL: FakeResponse(200, _page(["1"]))}
        )
        report = reconcile_sc_likes("tok", apply=True)
        assert report.guard == "mass delete: 30 > 25"
        assert (report.removed, report.skipped_by_guard) == (0, 30)
        assert len(_likes()) == 31

    def test_like_written_mid_fetch_survives(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _seed_likes(["9", "8"])

        def fetch_with_inapp_like(token: str) -> LikesSnapshot:
            upsert_sc_likes(["8"], "mm_keep", liked_now=True)  # lands mid-fetch
            return _snapshot({"1"})

        monkeypatch.setattr(
            likes_reconcile, "fetch_all_liked_ids", fetch_with_inapp_like
        )
        report = reconcile_sc_likes("tok", apply=True)
        assert report.protected == 1 and report.removed == 1
        assert _likes() == {"8", "1"}

    def test_fetch_crash_is_incomplete(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_likes(["9"])

        def crash(token: str) -> LikesSnapshot:
            raise KeyError("boom")

        monkeypatch.setattr(likes_reconcile, "fetch_all_liked_ids", crash)
        report = reconcile_sc_likes("tok", apply=True)
        assert not report.complete and _likes() == {"9"}


# ---------------------------------------------------------------------------
# Nightly schedule
# ---------------------------------------------------------------------------


class TestSchedule:
    NOW = datetime(2026, 11, 9, 3, 0, tzinfo=UTC)

    def test_due_decision(self) -> None:
        due = sc_feed_worker.likes_reconcile_due
        assert due(None, self.NOW)
        assert due("garbage", self.NOW)
        assert not due((self.NOW - timedelta(hours=1)).isoformat(), self.NOW)
        assert not due((self.NOW - timedelta(hours=22)).isoformat(), self.NOW)
        assert due((self.NOW - timedelta(hours=23)).isoformat(), self.NOW)

    def _run(self, monkeypatch: pytest.MonkeyPatch, complete: bool) -> list:
        calls: list = []
        report = likes_reconcile.ReconcileReport(
            fetched=1, complete=complete, reason="r", current=1, to_add=0,
            to_remove=0, protected=0, guard=None, applied=True,
        )  # fmt: skip
        monkeypatch.setattr(sc_feed_worker, "get_web_provider_state", lambda: object())
        monkeypatch.setattr(
            likes_reconcile,
            "reconcile_for_provider",
            lambda state, apply: calls.append(apply) or report,
        )
        sc_feed_worker._maybe_reconcile_sc_likes()
        return calls

    def test_first_run_is_dry_then_waits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(monkeypatch, complete=True) == [False]
        assert sc_feed_worker._likes_reconcile_last_run_at() is not None
        assert self._run(monkeypatch, complete=True) == []

    def test_applies_once_a_previous_run_is_old(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        yesterday = (sc_feed_worker._now_utc() - timedelta(hours=24)).isoformat()
        _exec(
            "UPDATE sc_feed_sync_state SET likes_reconcile_last_run_at = ?",
            (yesterday,),
        )
        assert self._run(monkeypatch, complete=True) == [True]
        assert self._run(monkeypatch, complete=True) == []

    def test_incomplete_run_retries_next_tick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._run(monkeypatch, complete=False) == [False]
        assert sc_feed_worker._likes_reconcile_last_run_at() is None
        assert self._run(monkeypatch, complete=False) == [False]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


class TestCli:
    def _patch_auth(self, monkeypatch: pytest.MonkeyPatch, token: str | None) -> None:
        from music_minion.domain.library.providers import soundcloud
        from music_minion.domain.library.providers.soundcloud import api

        monkeypatch.setattr(soundcloud, "init_provider", lambda config: object())
        token_data = {"access_token": token} if token else None
        monkeypatch.setattr(
            api, "_ensure_valid_token", lambda state: (state, token_data)
        )

    def test_default_is_dry_run(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        from music_minion.cli import run_sc_likes_reconcile

        _track_with_marker("9")
        _seed_likes(["9", "1"])
        self._patch_auth(monkeypatch, "tok")
        _patch_fetch(monkeypatch, _three_pages())
        assert run_sc_likes_reconcile() == 0
        out = capsys.readouterr().out
        assert "DRY RUN" in out and "to remove: 1" in out
        assert "Artist - Title 9 (9)" in out
        assert _likes() == {"9", "1"}

    def test_unauthenticated_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from music_minion.cli import run_sc_likes_reconcile

        self._patch_auth(monkeypatch, None)
        assert run_sc_likes_reconcile(apply=True) == 1
