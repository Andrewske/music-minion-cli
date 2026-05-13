"""Tests for player_state module."""

import asyncio
import pytest
from pydantic import ValidationError
from backend.player_state import (
    PlaybackState,
    get_state,
    get_state_dict,
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
