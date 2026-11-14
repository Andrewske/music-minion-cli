"""Player actions (#78): queue insert, jump, and like/unlike on SoundCloud.

Every SoundCloud call is mocked: the SC writer thread is never started and
unlike_track / get_web_provider_state are patched where they're used.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from music_minion.core.database import get_db_connection, upsert_sc_likes
from web.backend import sc_push_worker
from web.backend.main import app
from web.backend.player_state import PlaybackState, get_state, reset_state
from web.backend.routers.player import (
    _upcoming_start,
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
def no_sc_writer() -> Iterator[dict[str, MagicMock]]:
    """Stop like/unlike from waking the real SC push worker."""
    with (
        patch("web.backend.sc_like_actions.enqueue_feed_action_drain") as drain,
        patch("web.backend.sc_like_actions.enqueue_sc_unlike") as unlike,
    ):
        yield {"drain": drain, "unlike": unlike}


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


def _like_job() -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sc_feed_action_jobs WHERE soundcloud_id = '77' AND action_type = 'like'"
        ).fetchone()
    return dict(row) if row else None


def _set_job_status(status: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE sc_feed_action_jobs SET status = ?, attempt_count = 5 WHERE soundcloud_id = '77'",
            (status,),
        )
        conn.commit()


def _keep_playlist_job() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO sc_feed_action_jobs (soundcloud_id, action_type, target_key)
            VALUES ('77', 'monthly_playlist', 'Nov 26')"""
        )
        conn.commit()


class TestLikeEndpoints:
    def test_like_queues_job_and_wakes_writer(self, no_sc_writer) -> None:
        response = client.put("/api/soundcloud/likes/77")
        assert response.status_code == 200
        assert response.json()["like_status"] == "pending"
        assert _like_job()["status"] == "pending"
        no_sc_writer["drain"].assert_called_once()

    def test_like_records_no_keep_side_effects(self, no_sc_writer) -> None:
        client.put("/api/soundcloud/likes/77")
        with get_db_connection() as conn:
            playlist_jobs = conn.execute(
                "SELECT COUNT(*) FROM sc_feed_action_jobs WHERE action_type != 'like'"
            ).fetchone()[0]
            decisions = conn.execute(
                "SELECT COUNT(*) FROM sc_track_decisions"
            ).fetchone()[0]
        assert playlist_jobs == 0 and decisions == 0

    @pytest.mark.parametrize("status", ["complete", "error"])
    def test_like_rearms_finished_job(self, no_sc_writer, status: str) -> None:
        client.put("/api/soundcloud/likes/77")
        _set_job_status(status)
        client.put("/api/soundcloud/likes/77")
        job = _like_job()
        assert job["status"] == "pending" and job["attempt_count"] == 0

    def test_like_leaves_running_job_alone(self, no_sc_writer) -> None:
        client.put("/api/soundcloud/likes/77")
        _set_job_status("running")
        client.put("/api/soundcloud/likes/77")
        assert _like_job()["status"] == "running"

    def test_rejects_non_numeric_id(self, no_sc_writer) -> None:
        assert client.put("/api/soundcloud/likes/abc").status_code == 400
        assert client.delete("/api/soundcloud/likes/abc").status_code == 400

    def test_unlike_cancels_pending_like_without_sc_call(self, no_sc_writer) -> None:
        client.put("/api/soundcloud/likes/77")
        _keep_playlist_job()
        body = client.delete("/api/soundcloud/likes/77").json()
        assert body["cancelled_pending_like"] is True
        assert body["unlike_queued"] is False
        assert _like_job() is None
        no_sc_writer["unlike"].assert_not_called()
        with get_db_connection() as conn:  # Keep's playlist job survives
            assert (
                conn.execute("SELECT COUNT(*) FROM sc_feed_action_jobs").fetchone()[0]
                == 1
            )

    def test_unlike_liked_track_queues_sc_unlike(self, no_sc_writer) -> None:
        upsert_sc_likes(["77"], "sync")
        body = client.delete("/api/soundcloud/likes/77").json()
        assert body["unlike_queued"] is True
        no_sc_writer["unlike"].assert_called_once_with("77")

    def test_like_flips_live_player_heart(self, no_sc_writer) -> None:
        with patch(
            "web.backend.routers.player.update_state", new_callable=AsyncMock
        ) as update:
            from web.backend import player_state

            track = {"id": 1, "soundcloud_id": "77", "sc_liked": False}
            player_state._state = PlaybackState(queue=(track,), current_track=track)
            client.put("/api/soundcloud/likes/77")
        update.assert_awaited_once()
        patch_fn = update.await_args.args[0]
        assert patch_fn(player_state._state).current_track["sc_liked"] is True


# ---------------------------------------------------------------------------
# SC push worker: unlike handler
# ---------------------------------------------------------------------------


def _liked() -> bool:
    with get_db_connection() as conn:
        return (
            conn.execute("SELECT 1 FROM sc_likes WHERE soundcloud_id = '77'").fetchone()
            is not None
        )


class TestUnlikeHandler:
    def _run(self, result: tuple[bool, str | None]) -> tuple[bool, str | None]:
        state = MagicMock()
        with (
            patch.object(sc_push_worker, "get_web_provider_state", return_value=state),
            patch.object(
                sc_push_worker, "unlike_track", return_value=(state, *result)
            ) as call,
        ):
            outcome = sc_push_worker._handle_unlike("77")
        call.assert_called_once_with(state, "77")
        return outcome

    def test_success_clears_sc_likes(self) -> None:
        upsert_sc_likes(["77"], "mm_keep")
        assert self._run((True, None)) == (True, None)
        assert not _liked()

    def test_404_counts_as_unliked(self) -> None:
        upsert_sc_likes(["77"], "mm_keep")
        assert self._run((False, "Track not found or not liked (404): 77"))[0] is True
        assert not _liked()

    def test_failure_keeps_sc_likes(self) -> None:
        upsert_sc_likes(["77"], "mm_keep")
        assert self._run((False, "Rate limit exceeded (429)")) == (
            False,
            "Rate limit exceeded (429)",
        )
        assert _liked()

    def test_unauthenticated_is_a_noop(self) -> None:
        upsert_sc_likes(["77"], "mm_keep")
        with (
            patch.object(sc_push_worker, "get_web_provider_state", return_value=None),
            patch.object(sc_push_worker, "unlike_track") as call,
        ):
            assert sc_push_worker._handle_unlike("77") == (True, None)
        call.assert_not_called()
        assert _liked()
