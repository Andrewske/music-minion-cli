"""Tests for player_state module."""

import asyncio
import pytest
from pydantic import ValidationError
from backend.player_state import (
    PlaybackState,
    get_state,
    get_state_dict,
    get_slim_state_dict,
    get_queue_page,
    update_state,
    reset_state,
)


@pytest.fixture(autouse=True)
def clean_state():
    """Reset state before each test."""
    reset_state()
    yield
    reset_state()


class TestPlaybackStateImmutability:
    """Verify frozen Pydantic model prevents mutation."""

    def test_cannot_mutate_field(self):
        state = PlaybackState()
        with pytest.raises(ValidationError):
            state.is_playing = True

    def test_queue_is_tuple(self):
        state = PlaybackState(queue=[{"id": 1}, {"id": 2}])
        assert isinstance(state.queue, tuple)


class TestGetState:
    """Tests for get_state() function."""

    def test_returns_current_state(self):
        state = get_state()
        assert isinstance(state, PlaybackState)

    def test_returns_same_instance(self):
        """get_state() returns the same object until updated."""
        s1 = get_state()
        s2 = get_state()
        assert s1 is s2


class TestGetStateDict:
    """Tests for get_state_dict() function."""

    def test_server_time_in_milliseconds(self):
        state_dict = get_state_dict()
        assert "serverTime" in state_dict
        assert isinstance(state_dict["serverTime"], float)
        assert state_dict["serverTime"] > 1_000_000_000_000

    @pytest.mark.asyncio
    async def test_track_started_at_converted_to_milliseconds(self, monkeypatch):
        import time
        monkeypatch.setattr(
            "backend.sync_manager.sync_manager.broadcast",
            lambda *args: asyncio.sleep(0)
        )
        await update_state({"track_started_at": time.time()}, broadcast=False)
        state_dict = get_state_dict()
        assert state_dict["trackStartedAt"] > 1_000_000_000_000

    def test_track_started_at_null_safe(self):
        state_dict = get_state_dict()
        assert state_dict["trackStartedAt"] is None

    def test_uses_camel_case_aliases(self):
        state_dict = get_state_dict()
        assert "currentTrack" in state_dict
        assert "queueIndex" in state_dict
        assert "isPlaying" in state_dict


class TestUpdateState:
    """Tests for update_state() function."""

    @pytest.mark.asyncio
    async def test_update_with_dict(self, monkeypatch):
        # Mock broadcast to avoid import issues
        monkeypatch.setattr(
            "backend.sync_manager.sync_manager.broadcast",
            lambda *args: asyncio.sleep(0)
        )

        await update_state({"is_playing": True}, broadcast=False)
        assert get_state().is_playing is True

        await update_state({"is_playing": False}, broadcast=False)
        assert get_state().is_playing is False

    @pytest.mark.asyncio
    async def test_update_with_callable(self, monkeypatch):
        monkeypatch.setattr(
            "backend.sync_manager.sync_manager.broadcast",
            lambda *args: asyncio.sleep(0)
        )

        def increment_index(state: PlaybackState) -> PlaybackState:
            return state.model_copy(update={"queue_index": state.queue_index + 1})

        await update_state({"queue_index": 5}, broadcast=False)
        await update_state(increment_index, broadcast=False)
        assert get_state().queue_index == 6

    @pytest.mark.asyncio
    async def test_list_to_tuple_conversion(self, monkeypatch):
        monkeypatch.setattr(
            "backend.sync_manager.sync_manager.broadcast",
            lambda *args: asyncio.sleep(0)
        )

        tracks = [{"id": 1}, {"id": 2}]
        await update_state({"queue": tracks}, broadcast=False)
        assert isinstance(get_state().queue, tuple)
        assert len(get_state().queue) == 2

    @pytest.mark.asyncio
    async def test_concurrent_updates_are_serialized(self, monkeypatch):
        """Multiple concurrent updates should not race."""
        monkeypatch.setattr(
            "backend.sync_manager.sync_manager.broadcast",
            lambda *args: asyncio.sleep(0)
        )

        await update_state({"queue_index": 0}, broadcast=False)

        async def increment():
            for _ in range(100):
                def inc(s):
                    return s.model_copy(update={"queue_index": s.queue_index + 1})
                await update_state(inc, broadcast=False)

        # Run 3 concurrent incrementers
        await asyncio.gather(increment(), increment(), increment())

        # Should be exactly 300 (no lost updates)
        assert get_state().queue_index == 300


class TestBroadcastConcurrency:
    """Broadcast runs outside the state lock and supports one-shot extras."""

    @pytest.mark.asyncio
    async def test_slow_broadcast_does_not_block_updates(self, monkeypatch):
        """A hung broadcast (slow WS client) must not hold the state lock."""
        release = asyncio.Event()

        async def slow_broadcast(event_type, data):
            await release.wait()

        monkeypatch.setattr(
            "backend.sync_manager.sync_manager.broadcast", slow_broadcast
        )

        t1 = asyncio.create_task(update_state({"queue_index": 1}))
        await asyncio.sleep(0)  # let t1 mutate and enter the blocked broadcast

        # Would deadlock (and time out) if broadcast ran under the state lock
        await asyncio.wait_for(
            update_state({"queue_index": 2}, broadcast=False), timeout=1
        )
        assert get_state().queue_index == 2

        release.set()
        await t1

    @pytest.mark.asyncio
    async def test_broadcast_extra_merged_into_payload_only(self, monkeypatch):
        """broadcast_extra fields ride along in the payload, not the state."""
        sent: list[dict] = []

        async def capture(event_type, data):
            sent.append(data)

        monkeypatch.setattr("backend.sync_manager.sync_manager.broadcast", capture)

        await update_state(
            {"queue_index": 3}, broadcast_extra={"pruned_track_id": 99}
        )

        assert sent[0]["pruned_track_id"] == 99
        assert sent[0]["queueIndex"] == 3
        assert not hasattr(get_state(), "pruned_track_id")


class TestQueueVersion:
    """queue_version bumps on content changes only, never on position changes."""

    @pytest.mark.asyncio
    async def test_bumps_on_queue_replace_via_dict(self):
        assert get_state().queue_version == 0
        await update_state({"queue": [{"id": 1}, {"id": 2}]}, broadcast=False)
        assert get_state().queue_version == 1

    @pytest.mark.asyncio
    async def test_bumps_on_refill_append(self):
        await update_state({"queue": ({"id": 1},)}, broadcast=False)
        state = get_state()
        await update_state(
            {"queue": state.queue + ({"id": 2},)}, broadcast=False
        )
        assert get_state().queue_version == 2

    @pytest.mark.asyncio
    async def test_bumps_on_prune_via_callable(self):
        await update_state({"queue": ({"id": 1}, {"id": 2})}, broadcast=False)

        def prune(s: PlaybackState) -> PlaybackState:
            return s.model_copy(
                update={"queue": tuple(t for t in s.queue if t["id"] != 2)}
            )

        await update_state(prune, broadcast=False)
        assert get_state().queue_version == 2
        assert len(get_state().queue) == 1

    @pytest.mark.asyncio
    async def test_no_bump_on_pause_like_update(self):
        await update_state({"queue": ({"id": 1},)}, broadcast=False)
        await update_state(
            {"is_playing": False, "position_ms": 1234, "track_started_at": None},
            broadcast=False,
        )
        assert get_state().queue_version == 1

    @pytest.mark.asyncio
    async def test_no_bump_on_seek_like_update(self):
        await update_state({"queue": ({"id": 1},)}, broadcast=False)
        await update_state({"position_ms": 60_000}, broadcast=False)
        assert get_state().queue_version == 1

    @pytest.mark.asyncio
    async def test_no_bump_on_index_advance_via_callable(self):
        """Queue-index advance (skip within window) keeps queue identity."""
        await update_state({"queue": ({"id": 1}, {"id": 2})}, broadcast=False)

        def advance(s: PlaybackState) -> PlaybackState:
            return s.model_copy(
                update={
                    "queue_index": s.queue_index + 1,
                    "current_track": s.queue[s.queue_index + 1],
                }
            )

        await update_state(advance, broadcast=False)
        assert get_state().queue_version == 1
        assert get_state().queue_index == 1


class TestSlimBroadcastPayload:
    """playback:state broadcasts carry no queue array — slim payload shape."""

    @pytest.mark.asyncio
    async def test_broadcast_omits_queue_but_carries_version_and_meta(
        self, monkeypatch
    ):
        sent: list[dict] = []

        async def capture(event_type, data):
            sent.append(data)

        monkeypatch.setattr("backend.sync_manager.sync_manager.broadcast", capture)

        track = {"id": 7, "title": "T", "artist": "A"}
        await update_state(
            {
                "queue": (track, {"id": 8}),
                "queue_index": 0,
                "current_track": track,
                "is_playing": True,
            }
        )

        payload = sent[0]
        assert "queue" not in payload
        assert payload["queueVersion"] == 1
        assert payload["queueLength"] == 2
        assert payload["stateSeq"] == 1
        assert payload["currentTrack"] == track
        assert payload["queueIndex"] == 0
        assert payload["isPlaying"] is True
        assert "serverTime" in payload
        assert "devices" in payload

    @pytest.mark.asyncio
    async def test_state_seq_monotonic_across_broadcasts(self, monkeypatch):
        sent: list[dict] = []

        async def capture(event_type, data):
            sent.append(data)

        monkeypatch.setattr("backend.sync_manager.sync_manager.broadcast", capture)

        await update_state({"is_playing": True})
        await update_state({"is_playing": False})
        assert [p["stateSeq"] for p in sent] == [1, 2]

    def test_full_state_dict_keeps_queue_for_sync_full(self):
        """sync:full / GET /state stay fat — queue included plus version meta."""
        state_dict = get_state_dict()
        assert "queue" in state_dict
        assert "queueVersion" in state_dict
        assert "queueLength" in state_dict
        assert "stateSeq" in state_dict

    def test_slim_dict_is_full_dict_minus_queue(self):
        full = get_state_dict()
        slim = get_slim_state_dict()
        assert set(full.keys()) - set(slim.keys()) == {"queue"}


class TestGetQueuePage:
    """GET /player/queue pagination semantics."""

    @pytest.mark.asyncio
    async def test_returns_full_window_by_default(self):
        queue = tuple({"id": i} for i in range(30))
        await update_state({"queue": queue}, broadcast=False)

        page = get_queue_page()
        assert page["version"] == 1
        assert page["total"] == 30
        assert page["offset"] == 0
        assert [t["id"] for t in page["tracks"]] == list(range(30))

    @pytest.mark.asyncio
    async def test_offset_and_limit_slice(self):
        queue = tuple({"id": i} for i in range(30))
        await update_state({"queue": queue}, broadcast=False)

        page = get_queue_page(offset=10, limit=5)
        assert page["offset"] == 10
        assert page["total"] == 30
        assert [t["id"] for t in page["tracks"]] == [10, 11, 12, 13, 14]

    @pytest.mark.asyncio
    async def test_offset_past_end_returns_empty(self):
        await update_state({"queue": ({"id": 1},)}, broadcast=False)
        page = get_queue_page(offset=100, limit=10)
        assert page["tracks"] == []
        assert page["total"] == 1

    @pytest.mark.asyncio
    async def test_negative_offset_and_zero_limit_clamped(self):
        queue = tuple({"id": i} for i in range(5))
        await update_state({"queue": queue}, broadcast=False)
        page = get_queue_page(offset=-3, limit=0)
        assert page["offset"] == 0
        assert len(page["tracks"]) == 1  # limit clamped to 1

    def test_empty_queue(self):
        page = get_queue_page()
        assert page == {"version": 0, "total": 0, "offset": 0, "tracks": []}
