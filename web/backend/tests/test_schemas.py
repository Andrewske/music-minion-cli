"""Tests for backend schemas."""

import pytest
from web.backend.schemas import TrackInfo, ComparisonPair, StartSessionRequest


def test_track_info_schema():
    """Test TrackInfo Pydantic model."""
    track = TrackInfo(
        id=1,
        title="Test Track",
        artist="Test Artist",
        album="Test Album",
        year=2023,
        bpm=120,
        genre="Electronic",
        rating=1500.0,
        comparison_count=5,
        wins=3,
        losses=2,
        duration=180.5,
        has_waveform=True,
    )

    assert track.id == 1
    assert track.title == "Test Track"
    assert track.rating == 1500.0
    assert track.wins == 3
    assert track.losses == 2


def test_comparison_pair_schema():
    """Test ComparisonPair Pydantic model."""
    track_a = TrackInfo(
        id=1,
        title="Track A",
        artist="Artist A",
        rating=1500.0,
        comparison_count=0,
        wins=0,
        losses=0,
        has_waveform=False,
    )

    track_b = TrackInfo(
        id=2,
        title="Track B",
        artist="Artist B",
        rating=1500.0,
        comparison_count=0,
        wins=0,
        losses=0,
        has_waveform=False,
    )

    pair = ComparisonPair(
        track_a=track_a, track_b=track_b, session_id="test-session-123"
    )

    assert pair.track_a.title == "Track A"
    assert pair.track_b.title == "Track B"
    assert pair.session_id == "test-session-123"


def test_start_session_request_schema():
    """Test StartSessionRequest Pydantic model."""
    request = StartSessionRequest(
        target_comparisons=20, genre_filter="Electronic", year_filter="2023"
    )

    assert request.target_comparisons == 20
    assert request.genre_filter == "Electronic"
    assert request.year_filter == "2023"
