"""Tests for radio scheduler service."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from music_minion.domain.library.models import Track
from music_minion.domain.radio.models import NowPlaying, Station
from music_minion.domain.radio.scheduler import (
    SchedulerState,
    _record_history,
    get_current_state,
    get_next_track_path,
    get_scheduler_info,
    handle_track_unavailable,
    reset_scheduler_state,
)


@pytest.fixture
def mock_track() -> Track:
    """Create a mock track for testing."""
    return Track(
        local_path="/music/artist/track.flac",
        title="Test Track",
        artist="Test Artist",
        duration=180.0,
        id=42,
    )


@pytest.fixture
def mock_station() -> Station:
    """Create a mock station for testing."""
    return Station(
        id=1,
        name="Test Station",
        playlist_id=10,
        mode="shuffle",
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_now_playing(mock_track: Track) -> NowPlaying:
    """Create a mock NowPlaying for testing."""
    return NowPlaying(
        track=mock_track,
        position_ms=5000,
        next_track=None,
        upcoming=[],
        station_id=1,
        source_type="local",
    )


class TestSchedulerState:
    """Tests for SchedulerState dataclass."""

    def test_default_state(self) -> None:
        """Test default scheduler state has None values."""
        state = SchedulerState()
        assert state.current_track_id is None
        assert state.current_started_at is None
        assert state.last_request_time is None

    def test_state_with_values(self) -> None:
        """Test scheduler state with values."""
        now = datetime.now()
        state = SchedulerState(
            current_track_id=42,
            current_started_at=now,
            last_request_time=now,
        )
        assert state.current_track_id == 42
        assert state.current_started_at == now


class TestGetNextTrackPath:
    """Tests for get_next_track_path function."""

    def test_no_active_station_returns_none(self) -> None:
        """Test returns None when no station is active."""
        reset_scheduler_state()
        with patch(
            "music_minion.domain.radio.scheduler.get_active_station", return_value=None
        ):
            result = get_next_track_path()
            assert result is None

    def test_no_tracks_available_returns_none(
        self, mock_station: Station
    ) -> None:
        """Test returns None when station has no tracks."""
        reset_scheduler_state()
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=None,
            ),
        ):
            result = get_next_track_path()
            assert result is None

    def test_returns_local_path(
        self,
        mock_station: Station,
        mock_now_playing: NowPlaying,
    ) -> None:
        """Test returns local path for local tracks."""
        reset_scheduler_state()
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=mock_now_playing,
            ),
            patch(
                "music_minion.domain.radio.scheduler._record_history"
            ) as mock_record,
        ):
            result = get_next_track_path()
            assert result == "/music/artist/track.flac"
            mock_record.assert_called_once()

    def test_records_history_on_new_track(
        self,
        mock_station: Station,
        mock_now_playing: NowPlaying,
    ) -> None:
        """Test history is recorded when track changes."""
        reset_scheduler_state()
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=mock_now_playing,
            ),
            patch(
                "music_minion.domain.radio.scheduler._record_history"
            ) as mock_record,
        ):
            # First call - should record
            get_next_track_path()
            assert mock_record.call_count == 1

            # Second call with same track - should not record again
            get_next_track_path()
            assert mock_record.call_count == 1


class TestHandleTrackUnavailable:
    """Tests for handle_track_unavailable function."""

    def test_no_active_station_returns_none(self) -> None:
        """Test returns None when no station is active."""
        with patch(
            "music_minion.domain.radio.scheduler.get_active_station", return_value=None
        ):
            result = handle_track_unavailable(42)
            assert result is None

    def test_marks_track_skipped_and_returns_next(
        self,
        mock_station: Station,
        mock_now_playing: NowPlaying,
    ) -> None:
        """Test marks track as skipped and returns next track."""
        reset_scheduler_state()
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.mark_track_skipped"
            ) as mock_skip,
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=mock_now_playing,
            ),
            patch("music_minion.domain.radio.scheduler._record_history"),
        ):
            result = handle_track_unavailable(100, "file_missing")
            mock_skip.assert_called_once_with(1, 100, "file_missing")
            assert result == "/music/artist/track.flac"


class TestGetCurrentState:
    """Tests for get_current_state function."""

    def test_no_active_station_returns_none(self) -> None:
        """Test returns None when no station is active."""
        with patch(
            "music_minion.domain.radio.scheduler.get_active_station", return_value=None
        ):
            result = get_current_state()
            assert result is None

    def test_returns_now_playing(
        self,
        mock_station: Station,
        mock_now_playing: NowPlaying,
    ) -> None:
        """Test returns NowPlaying state."""
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=mock_now_playing,
            ),
        ):
            result = get_current_state()
            assert result == mock_now_playing


class TestGetSchedulerInfo:
    """Tests for get_scheduler_info function."""

    def test_returns_state_dict(self) -> None:
        """Test returns scheduler state as dict."""
        reset_scheduler_state()
        info = get_scheduler_info()
        assert isinstance(info, dict)
        assert "current_track_id" in info
        assert "current_started_at" in info
        assert "last_request_time" in info

    def test_state_after_request(
        self,
        mock_station: Station,
        mock_now_playing: NowPlaying,
    ) -> None:
        """Test scheduler info reflects state after request."""
        reset_scheduler_state()
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=mock_now_playing,
            ),
            patch("music_minion.domain.radio.scheduler._record_history"),
        ):
            get_next_track_path()
            info = get_scheduler_info()
            assert info["current_track_id"] == 42
            assert info["current_started_at"] is not None


class TestResetSchedulerState:
    """Tests for reset_scheduler_state function."""

    def test_resets_state(
        self,
        mock_station: Station,
        mock_now_playing: NowPlaying,
    ) -> None:
        """Test resets scheduler state to defaults."""
        # First, set some state
        with (
            patch(
                "music_minion.domain.radio.scheduler.get_active_station",
                return_value=mock_station,
            ),
            patch(
                "music_minion.domain.radio.scheduler.calculate_now_playing",
                return_value=mock_now_playing,
            ),
            patch("music_minion.domain.radio.scheduler._record_history"),
        ):
            get_next_track_path()
            info = get_scheduler_info()
            assert info["current_track_id"] == 42

        # Now reset
        reset_scheduler_state()
        info = get_scheduler_info()
        assert info["current_track_id"] is None
        assert info["current_started_at"] is None
