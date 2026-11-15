"""Player actions (#78): queue insert, jump, and like/unlike on SoundCloud.

Every SoundCloud call is mocked: the SC writer thread is never started and
like_track / unlike_track are patched where the job runner uses them.
"""

from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection, upsert_sc_likes
from web.backend.main import app
from web.backend.player_state import PlaybackState, get_state, reset_state
from web.backend.routers.player import (
    _upcoming_start,
    anchor_current,
    insert_track,
    with_sc_liked,
)
from web.backend.schemas import PlayContext

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_player_state() -> Iterator[None]:
    reset_state()
    yield
    reset_state()


@pytest.fixture
def no_sc_writer() -> Iterator[MagicMock]:
    """Stop like/unlike requests from waking the real SC push worker."""
    with patch("web.backend.sc_like_actions.enqueue_feed_action_drain") as drain:
        yield drain


def _track(title: str, sc_id: str | None = None, unavailable: bool = False) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO tracks (title, artist, soundcloud_id, source, unavailable_at)
            VALUES (?, 'A', ?, 'soundcloud', ?)""",
            (title, sc_id, "2026-01-01" if unavailable else None),
        )
        conn.commit()
        return cursor.lastrowid


def _q(*ids: int) -> tuple[dict, ...]:
    return tuple({"id": i} for i in ids)


async def _seed_playback(ids: list[int], index: int, playing: bool = True) -> None:
    from web.backend.player_state import update_state

    queue = tuple({"id": i, "source": "local"} for i in ids)
    await update_state(
        {
            "queue": queue,
            "queue_index": index,
            "current_track": queue[index],
            "is_playing": playing,
            "current_context": PlayContext(type="feed", track_ids=ids),
        },
        broadcast=False,
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestInsertTrack:
    def test_next_goes_right_after_cursor(self) -> None:
        queue, at = insert_track(_q(1, 2, 3, 4), 2, {"id": 9}, "next")
        assert [t["id"] for t in queue] == [1, 2, 9, 3, 4]
        assert at == 2

    def test_last_goes_to_window_end(self) -> None:
        queue, at = insert_track(_q(1, 2, 3), 2, {"id": 9}, "last")
        assert [t["id"] for t in queue] == [1, 2, 3, 9]
        assert at == 3

    def test_upcoming_duplicate_moves_instead_of_doubling(self) -> None:
        queue, at = insert_track(_q(1, 2, 3, 4), 2, {"id": 4}, "next")
        assert [t["id"] for t in queue] == [1, 2, 4, 3]
        assert at == 2

    def test_already_played_copy_is_kept(self) -> None:
        queue, _ = insert_track(_q(1, 2, 3), 2, {"id": 1}, "next")
        assert [t["id"] for t in queue] == [1, 2, 1, 3]


class TestUpcomingStart:
    def test_current_in_queue(self) -> None:
        s = PlaybackState(queue=_q(1, 2, 3), queue_index=1, current_track={"id": 2})
        assert _upcoming_start(s) == 2

    def test_current_displaced_points_at_next(self) -> None:
        # Organizer: current track assigned away; queue_index is the next track.
        s = PlaybackState(queue=_q(1, 3), queue_index=1, current_track={"id": 2})
        assert _upcoming_start(s) == 1


class TestAnchorCurrent:
    def test_leaves_a_queue_holding_the_current_track(self) -> None:
        s = PlaybackState(queue=_q(1, 2, 3), queue_index=1, current_track={"id": 2})
        assert anchor_current(s) == (s.queue, 1)

    def test_puts_a_displaced_current_track_back_at_the_cursor(self) -> None:
        s = PlaybackState(queue=_q(1, 3), queue_index=1, current_track={"id": 2})
        queue, cursor = anchor_current(s)
        assert [t["id"] for t in queue] == [1, 2, 3] and cursor == 1

    def test_emptied_queue(self) -> None:
        s = PlaybackState(queue=(), queue_index=0, current_track={"id": 2})
        assert anchor_current(s) == (({"id": 2},), 0)


class TestWithScLiked:
    def test_patches_queue_and_current(self) -> None:
        track = {"id": 1, "soundcloud_id": "55", "sc_liked": False}
        s = PlaybackState(queue=(track, {"id": 2}), current_track=track)
        patched = with_sc_liked(s, "55", True)
        assert patched is not None
        assert patched.queue[0]["sc_liked"] is True
        assert patched.current_track == patched.queue[0]
        assert patched.queue[1] == {"id": 2}

    def test_none_when_nothing_matches(self) -> None:
        s = PlaybackState(queue=({"id": 1, "soundcloud_id": "1"},))
        assert with_sc_liked(s, "55", True) is None

    def test_none_when_already_in_that_state(self) -> None:
        track = {"id": 1, "soundcloud_id": "55", "sc_liked": True}
        assert with_sc_liked(PlaybackState(queue=(track,)), "55", True) is None


# ---------------------------------------------------------------------------
# POST /api/player/queue
# ---------------------------------------------------------------------------


class TestQueueInsertEndpoint:
    @pytest.mark.asyncio
    async def test_play_next_inserts_and_bumps_version(self) -> None:
        a, b, c, new = (_track(t) for t in ("a", "b", "c", "new"))
        await _seed_playback([a, b, c], 0)
        version = get_state().queue_version

        response = client.post("/api/player/queue", json={"trackId": new})

        assert response.status_code == 200
        assert response.json() == {"index": 1, "queue_size": 4}
        state = get_state()
        assert [t["id"] for t in state.queue] == [a, new, b, c]
        assert state.queue_version == version + 1
        assert state.current_track["id"] == a and state.queue_index == 0

    @pytest.mark.asyncio
    async def test_add_to_queue_appends(self) -> None:
        a, b, new = (_track(t) for t in ("a", "b", "new"))
        await _seed_playback([a, b], 0)
        response = client.post(
            "/api/player/queue", json={"trackId": new, "position": "last"}
        )
        assert response.status_code == 200
        assert [t["id"] for t in get_state().queue] == [a, b, new]

    def test_rejects_when_nothing_playing(self) -> None:
        response = client.post("/api/player/queue", json={"trackId": _track("x")})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_and_dead_tracks(self) -> None:
        a = _track("a")
        await _seed_playback([a], 0)
        assert (
            client.post("/api/player/queue", json={"trackId": 999_999}).status_code
            == 404
        )
        dead = _track("dead", unavailable=True)
        assert (
            client.post("/api/player/queue", json={"trackId": dead}).status_code == 400
        )

    @pytest.mark.asyncio
    async def test_inserts_into_emptied_organizer_queue(self) -> None:
        """Organizer: the last track got assigned away but keeps playing."""
        from web.backend.player_state import update_state

        playing, new = _track("playing"), _track("new")
        await update_state(
            {"queue": (), "queue_index": 0, "current_track": {"id": playing}},
            broadcast=False,
        )
        response = client.post("/api/player/queue", json={"trackId": new})
        assert response.status_code == 200
        # The playing track is re-anchored at the cursor; the insert follows it.
        assert response.json()["index"] == 1
        state = get_state()
        assert [t["id"] for t in state.queue] == [playing, new]
        assert state.queue_index == 0

    @pytest.mark.asyncio
    async def test_requeuing_the_displaced_current_track_plays_it_again(self) -> None:
        """Queue A while displaced A plays: the new copy must not read as current."""
        from web.backend.player_state import update_state

        playing, b = _track("playing"), _track("b")
        await update_state(
            {"queue": ({"id": b},), "queue_index": 0, "current_track": {"id": playing}},
            broadcast=False,
        )
        response = client.post(
            "/api/player/queue", json={"trackId": playing, "position": "next"}
        )
        assert response.status_code == 200
        state = get_state()
        assert [t["id"] for t in state.queue] == [playing, playing, b]
        assert _upcoming_start(state) == 1

    @pytest.mark.asyncio
    async def test_persists_queue(self) -> None:
        a, new = _track("a"), _track("new")
        await _seed_playback([a], 0)
        with patch("web.backend.routers.player.save_queue_state") as save:
            client.post("/api/player/queue", json={"trackId": new})
        assert save.call_args.kwargs["queue_ids"] == [a, new]


# ---------------------------------------------------------------------------
# POST /api/player/jump
# ---------------------------------------------------------------------------


class TestJumpEndpoint:
    @pytest.mark.asyncio
    async def test_jump_moves_cursor_and_keeps_queue(self) -> None:
        a, b, c = (_track(t) for t in ("a", "b", "c"))
        await _seed_playback([a, b, c], 0)
        version = get_state().queue_version

        response = client.post("/api/player/jump", json={"index": 2, "trackId": c})

        assert response.status_code == 200
        state = get_state()
        assert state.queue_index == 2 and state.current_track["id"] == c
        assert state.position_ms == 0 and state.is_playing
        assert state.queue_version == version  # position-only change
        assert state.current_history_id is not None

    @pytest.mark.asyncio
    async def test_jump_while_paused_stays_paused(self) -> None:
        a, b = _track("a"), _track("b")
        await _seed_playback([a, b], 0, playing=False)
        client.post("/api/player/jump", json={"index": 1, "trackId": b})
        state = get_state()
        assert state.is_playing is False and state.track_started_at is None

    @pytest.mark.asyncio
    async def test_stale_index_conflicts(self) -> None:
        a, b = _track("a"), _track("b")
        await _seed_playback([a, b], 0)
        response = client.post("/api/player/jump", json={"index": 1, "trackId": a})
        assert response.status_code == 409
        assert get_state().queue_index == 0

    @pytest.mark.asyncio
    async def test_out_of_range(self) -> None:
        await _seed_playback([_track("a")], 0)
        response = client.post("/api/player/jump", json={"index": 5, "trackId": 1})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# PUT/DELETE /api/soundcloud/likes/{soundcloud_id}
# ---------------------------------------------------------------------------

SC_ID = "77"


def _like_job() -> dict:
    with get_db_connection() as conn:
        row = conn.execute(
            """SELECT * FROM sc_feed_action_jobs
            WHERE soundcloud_id = ? AND action_type = 'like'""",
            (SC_ID,),
        ).fetchone()
    assert row is not None, "no like job row"
    return dict(row)


def _liked() -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM sc_likes WHERE soundcloud_id = ?", (SC_ID,)
        ).fetchone()
    return row is not None


def _job_count() -> int:
    with get_db_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM sc_feed_action_jobs").fetchone()[0]


class TestLikeEndpoints:
    def test_like_records_desired_state_and_wakes_writer(self, no_sc_writer) -> None:
        body = client.put(f"/api/soundcloud/likes/{SC_ID}").json()
        assert body["sc_liked"] is True and body["like_status"] == "pending"
        job = _like_job()
        assert (job["status"], job["want_liked"], job["generation"]) == (
            "pending",
            1,
            1,
        )
        no_sc_writer.assert_called_once()

    def test_unlike_flips_desired_state_on_the_same_row(self, no_sc_writer) -> None:
        client.put(f"/api/soundcloud/likes/{SC_ID}")
        client.delete(f"/api/soundcloud/likes/{SC_ID}")
        job = _like_job()
        assert (job["want_liked"], job["generation"]) == (0, 2)
        assert _job_count() == 1

    def test_like_records_no_keep_side_effects(self, no_sc_writer) -> None:
        client.put(f"/api/soundcloud/likes/{SC_ID}")
        with get_db_connection() as conn:
            decisions = conn.execute(
                "SELECT COUNT(*) FROM sc_track_decisions"
            ).fetchone()[0]
        assert _job_count() == 1 and decisions == 0

    def test_request_while_running_keeps_it_running(self, no_sc_writer) -> None:
        from web.backend.queries.feed import claim_due_action

        client.put(f"/api/soundcloud/likes/{SC_ID}")
        claim_due_action()
        client.delete(f"/api/soundcloud/likes/{SC_ID}")
        job = _like_job()
        assert (job["status"], job["want_liked"], job["generation"]) == (
            "running",
            0,
            2,
        )

    def test_rejects_non_numeric_id(self, no_sc_writer) -> None:
        assert client.put("/api/soundcloud/likes/abc").status_code == 400
        assert client.delete("/api/soundcloud/likes/abc").status_code == 400

    def test_like_flips_live_player_heart(self, no_sc_writer) -> None:
        from web.backend import player_state

        track = {"id": 1, "soundcloud_id": SC_ID, "sc_liked": False}
        player_state._state = PlaybackState(queue=(track,), current_track=track)
        with patch(
            "web.backend.routers.player.update_state", new_callable=AsyncMock
        ) as update:
            client.put(f"/api/soundcloud/likes/{SC_ID}")
        patch_fn = update.await_args.args[0]
        assert patch_fn(player_state._state).current_track["sc_liked"] is True


# ---------------------------------------------------------------------------
# Real ordering: the durable job and the worker's drain loop run for real;
# only the SoundCloud HTTP calls are mocked. Requests are injected from
# inside the mocked SC call, which is where a concurrent API request lands.
# ---------------------------------------------------------------------------

ScResult = tuple[object, bool, str | None]


class FakeSoundCloud:
    """Records like/unlike calls; each `during` hook runs inside one call."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.during: list[Callable[[], None]] = []
        self.results: list[tuple[bool, str | None]] = []

    def _call(self, kind: str, state: object) -> ScResult:
        self.calls.append(kind)
        if self.during:
            self.during.pop(0)()
        success, err = self.results.pop(0) if self.results else (True, None)
        return state, success, err

    def like(self, state: object, _sc_id: str) -> ScResult:
        return self._call("like", state)

    def unlike(self, state: object, _sc_id: str) -> ScResult:
        return self._call("unlike", state)


@pytest.fixture
def sc() -> Iterator[FakeSoundCloud]:
    fake = FakeSoundCloud()
    with (
        patch("web.backend.feed_rating.like_track", side_effect=fake.like),
        patch("web.backend.feed_rating.unlike_track", side_effect=fake.unlike),
    ):
        yield fake


def _request(liked: bool) -> None:
    """What the endpoint records (the worker wake-up is _drain below)."""
    from web.backend.queries.feed import set_like_intent

    set_like_intent(SC_ID, liked)


def _drain() -> None:
    from web.backend.feed_rating import drain_pending_feed_actions

    drain_pending_feed_actions(MagicMock())


class TestLikeOrdering:
    def test_like_sent_while_unlike_in_flight_wins(self, sc) -> None:
        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        sc.during = [lambda: _request(True)]
        _drain()
        assert sc.calls == ["unlike", "like"]
        assert _liked() and _like_job()["status"] == "complete"

    def test_unlike_sent_while_like_in_flight_wins(self, sc) -> None:
        _request(True)
        sc.during = [lambda: _request(False)]
        _drain()
        assert sc.calls == ["like", "unlike"]
        job = _like_job()
        assert (job["status"], job["want_liked"]) == ("complete", 0)
        assert not _liked()

    def test_like_then_unlike_before_drain_sends_only_the_last(self, sc) -> None:
        upsert_sc_likes([SC_ID], "sync")
        _request(True)
        _request(False)
        _drain()
        assert sc.calls == ["unlike"]
        assert not _liked()

    def test_superseded_failure_schedules_no_retry(self, sc) -> None:
        """A failing like overtaken by an unlike must not retry the like."""
        upsert_sc_likes([SC_ID], "sync")
        _request(True)
        sc.during = [lambda: _request(False)]
        sc.results = [(False, "Network error: boom"), (True, None)]
        _drain()
        assert sc.calls == ["like", "unlike"]
        job = _like_job()
        assert (job["status"], job["want_liked"], job["last_error"]) == (
            "complete",
            0,
            None,
        )
        assert not _liked()

    def test_current_failure_backs_off(self, sc) -> None:
        _request(True)
        sc.results = [(False, "Network error: boom")]
        _drain()
        job = _like_job()
        assert job["status"] == "error" and job["last_error"] == "Network error: boom"
        assert not _liked()

    def test_unlike_404_counts_as_done(self, sc) -> None:
        upsert_sc_likes([SC_ID], "mm_keep")
        _request(False)
        sc.results = [(False, "Track not found or not liked (404): 77")]
        _drain()
        assert _like_job()["status"] == "complete" and not _liked()

    def test_like_404_is_a_failure(self, sc) -> None:
        _request(True)
        sc.results = [(False, "Track not found (404): 77")]
        _drain()
        assert _like_job()["status"] == "error"

    def test_unlike_survives_restart(self, sc) -> None:
        from web.backend.queries.feed import (
            claim_due_action,
            recover_interrupted_actions,
        )

        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        claim_due_action()  # the process dies mid-call
        recover_interrupted_actions()
        _drain()
        assert sc.calls == ["unlike"] and not _liked()


class TestKeepInteraction:
    def test_unkeep_keeps_player_requests(self) -> None:
        from web.backend.queries.feed import cancel_pending_actions

        _request(False)
        assert cancel_pending_actions(SC_ID) == 0
        assert _like_job()["want_liked"] == 0

    def test_unkeep_still_cancels_keep_jobs(self) -> None:
        from web.backend.queries.feed import (
            cancel_pending_actions,
            enqueue_keep_actions,
        )

        enqueue_keep_actions(SC_ID, "Nov 26")
        assert cancel_pending_actions(SC_ID) == 2

    def test_player_unlike_overrides_pending_keep_like(self) -> None:
        from web.backend.queries.feed import enqueue_keep_actions

        enqueue_keep_actions(SC_ID, "Nov 26")
        _request(False)
        assert _job_count() == 2
        assert _like_job()["want_liked"] == 0

    def test_unlike_rows_show_no_like_action_state(self) -> None:
        from web.backend.queries.feed import get_action_state

        _request(True)
        assert get_action_state(SC_ID)["like"] == "pending"
        _request(False)
        assert get_action_state(SC_ID)["like"] is None


# ---------------------------------------------------------------------------
# Second review: atomic mirror, Keep after unlike, reconcile tombstone,
# final-attempt recovery.
# ---------------------------------------------------------------------------


class TestAtomicMirror:
    def test_crash_while_mirroring_leaves_job_retryable(self, sc) -> None:
        """settle + sc_likes write are one transaction: a crash in between
        rolls both back, recovery re-runs the unlike, and sc_likes clears."""
        import sqlite3

        from web.backend.queries.feed import (
            claim_due_action,
            recover_interrupted_actions,
            settle_action,
        )

        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        job = claim_due_action()
        with (
            patch(
                "web.backend.queries.feed.remove_sc_like",
                side_effect=sqlite3.OperationalError("disk I/O error"),
            ),
            pytest.raises(sqlite3.OperationalError),
        ):
            settle_action(job, True)  # the process dies here
        assert _like_job()["status"] == "running"
        assert _liked()

        recover_interrupted_actions()
        _drain()
        assert sc.calls == ["unlike"]
        assert _like_job()["status"] == "complete" and not _liked()

    def test_confirmed_unlike_stamps_tombstone(self, sc) -> None:
        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        _drain()
        assert _like_job()["unliked_at"] is not None


class TestKeepAfterUnlike:
    def test_keep_flips_pending_unlike_back_to_like(self, sc) -> None:
        from web.backend.queries.feed import enqueue_keep_actions

        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        enqueue_keep_actions(SC_ID, "Nov 26")
        job = _like_job()
        assert (job["want_liked"], job["generation"], job["requested_by"]) == (
            1,
            2,
            "keep",
        )
        with (
            patch(
                "web.backend.feed_rating.add_track_to_playlist",
                return_value=(MagicMock(), True, None),
            ),
            patch(
                "web.backend.feed_rating.get_or_create_monthly_sc_playlist",
                return_value=(MagicMock(), "pl-1", None),
            ),
        ):
            _drain()
        assert sc.calls == ["like"]
        assert _liked()

    def test_keep_after_completed_unlike_requests_a_like(self, sc) -> None:
        from web.backend.queries.feed import enqueue_keep_actions

        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        _drain()
        enqueue_keep_actions(SC_ID, "Nov 26")
        job = _like_job()
        assert (job["status"], job["want_liked"]) == ("pending", 1)

    def test_keep_on_a_wanted_like_adds_no_sc_call(self) -> None:
        from web.backend.queries.feed import enqueue_keep_actions

        _request(True)
        before = _like_job()
        enqueue_keep_actions(SC_ID, "Nov 26")
        after = _like_job()
        assert after["generation"] == before["generation"]
        assert after["requested_by"] == "player"

    def test_unkeep_cancels_keeps_like_but_not_player_like(self) -> None:
        from web.backend.queries.feed import (
            cancel_pending_actions,
            enqueue_keep_actions,
        )

        _request(False)
        enqueue_keep_actions(SC_ID, "Nov 26")  # Keep now owns the like row
        assert cancel_pending_actions(SC_ID) == 2
        _request(True)
        assert cancel_pending_actions(SC_ID) == 0


class TestReconcileTombstone:
    def _reconcile(self, fetch_started_at: str) -> tuple[int, int]:
        from music_minion.core.database import apply_sc_likes_reconcile

        return apply_sc_likes_reconcile([SC_ID], [], fetch_started_at)

    def _set_unliked_at(self, value: str) -> None:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE sc_feed_action_jobs SET unliked_at = ? WHERE soundcloud_id = ?",
                (value, SC_ID),
            )
            conn.commit()

    def test_stale_snapshot_does_not_revive_confirmed_unlike(self, sc) -> None:
        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        _drain()
        self._set_unliked_at("2026-11-14 12:00:05")
        # The fetch started before the unlike landed: its snapshot is stale.
        assert self._reconcile("2026-11-14 12:00:00") == (0, 0)
        assert not _liked()

    def test_later_relike_on_soundcloud_is_accepted(self, sc) -> None:
        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        _drain()
        self._set_unliked_at("2026-11-14 12:00:05")
        assert self._reconcile("2026-11-14 13:00:00") == (1, 0)
        assert _liked()

    def test_tombstone_ignored_once_player_likes_again(self, sc) -> None:
        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        _drain()
        self._set_unliked_at("2026-11-14 12:00:05")
        _request(True)  # want_liked = 1 again
        assert self._reconcile("2026-11-14 12:00:00") == (1, 0)


class TestFinalAttemptRecovery:
    def test_job_interrupted_on_final_attempt_runs_after_restart(self, sc) -> None:
        from web.backend.queries.feed import (
            claim_due_action,
            recover_interrupted_actions,
        )

        upsert_sc_likes([SC_ID], "sync")
        _request(False)
        with get_db_connection() as conn:
            conn.execute("UPDATE sc_feed_action_jobs SET attempt_count = 4")
            conn.commit()
        job = claim_due_action()  # final attempt: attempt_count -> 5 of 5
        assert job["attempt_count"] == job["max_attempts"]
        recover_interrupted_actions()  # the process died mid-call
        assert _like_job()["attempt_count"] == 4
        _drain()
        assert sc.calls == ["unlike"] and not _liked()
