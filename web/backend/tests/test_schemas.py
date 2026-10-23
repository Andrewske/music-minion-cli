"""Tests for backend schemas."""

import pytest
from pydantic import ValidationError

from web.backend.schemas import BuilderStartSessionRequest, ComparisonPair, TrackInfo


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
    assert track.artist == "Test Artist"
    assert track.rating == 1500.0
    assert track.wins == 3
    assert track.losses == 2


def test_track_info_schema_with_null_artist():
    """Test TrackInfo Pydantic model with null artist."""
    track = TrackInfo(
        id=2,
        title="Test Track Without Artist",
        artist=None,
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

    assert track.id == 2
    assert track.title == "Test Track Without Artist"
    assert track.artist is None
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

    pair = ComparisonPair(track_a=track_a, track_b=track_b)

    assert pair.track_a.title == "Track A"
    assert pair.track_b.title == "Track B"


def test_builder_start_session_request_schema():
    """BuilderStartSessionRequest carries only the target playlist id."""
    request = BuilderStartSessionRequest(playlist_id=42)

    assert request.playlist_id == 42


def test_builder_start_session_request_requires_playlist_id():
    with pytest.raises(ValidationError):
        BuilderStartSessionRequest()


def _track_info_with_bpm(bpm: float | None) -> TrackInfo:
    return TrackInfo(
        id=3,
        title="Fractional BPM",
        bpm=bpm,
        rating=1500.0,
        comparison_count=0,
        wins=0,
        losses=0,
        has_waveform=False,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(130.01, 130), (129.99, 130), (77.4, 77), (128, 128), (None, None)],
)
def test_track_info_rounds_fractional_bpm(
    raw: float | None, expected: int | None
) -> None:
    """Serato writes REAL bpms like 130.01; the API rounds them for display."""
    track = _track_info_with_bpm(raw)

    assert track.bpm == expected
    assert track.model_dump()["bpm"] == expected
    expected_json = "null" if expected is None else str(expected)
    assert f'"bpm":{expected_json}' in track.model_dump_json()
