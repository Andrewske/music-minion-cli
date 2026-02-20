"""History router for radio playback tracking."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class StartPlayRequest(BaseModel):
    track_id: int
    source_type: str = "local"


class StartPlayResponse(BaseModel):
    history_id: int


class EndPlayRequest(BaseModel):
    position_ms: int
    reason: str = "skip"


class HistoryEntryResponse(BaseModel):
    id: int
    track_id: int | None
    track_title: str
    track_artist: str
    source_type: str
    started_at: str
    ended_at: str | None
    duration_ms: int  # Actual listening time
    end_reason: str | None  # 'skip', 'completed', 'new_play'


class StatsResponse(BaseModel):
    total_plays: int
    total_minutes: int
    unique_tracks: int


class TopTrackResponse(BaseModel):
    track_id: int
    track_title: str
    track_artist: str
    play_count: int
    total_duration_seconds: int


@router.post("/start", response_model=StartPlayResponse)
def start_play_endpoint(request: StartPlayRequest) -> StartPlayResponse:
    """Start a new play session for a track."""
    from music_minion.domain.radio.history import start_play

    history_id = start_play(request.track_id, request.source_type)
    return StartPlayResponse(history_id=history_id)


@router.post("/{history_id}/end")
def end_play_endpoint(history_id: int, request: EndPlayRequest) -> dict[str, str]:
    """End a play session with duration and reason."""
    from music_minion.domain.radio.history import end_play

    end_play(history_id, request.position_ms, request.reason)
    return {"status": "ok"}


@router.get("", response_model=list[HistoryEntryResponse])
def get_history(
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[HistoryEntryResponse]:
    """Get playback history with optional date filtering."""
    from music_minion.domain.radio.history import get_history_entries

    entries = get_history_entries(
        limit=limit, offset=offset, start_date=start_date, end_date=end_date
    )
    return [_entry_to_response(e) for e in entries]


@router.get("/stats", response_model=StatsResponse)
def get_stats(days: int = 30) -> StatsResponse:
    """Get aggregated playback statistics."""
    from music_minion.domain.radio.history import get_stats

    stats = get_stats(days)
    return StatsResponse(
        total_plays=stats.total_plays,
        total_minutes=stats.total_minutes,
        unique_tracks=stats.unique_tracks,
    )


@router.get("/top-tracks", response_model=list[TopTrackResponse])
def get_top_tracks(limit: int = 10, days: int = 30) -> list[TopTrackResponse]:
    """Get most played tracks with play counts."""
    from music_minion.domain.radio.history import get_most_played_tracks

    tracks = get_most_played_tracks(limit=limit, days=days)
    return [_top_track_to_response(t) for t in tracks]


def _entry_to_response(entry) -> HistoryEntryResponse:
    """Convert domain HistoryEntry to response model."""
    return HistoryEntryResponse(
        id=entry.id,
        track_id=entry.track.id if entry.track else None,
        track_title=entry.track.title if entry.track else "Unknown",
        track_artist=entry.track.artist if entry.track else "Unknown",
        source_type=entry.source_type,
        started_at=entry.started_at.isoformat() if entry.started_at else "",
        ended_at=entry.ended_at.isoformat() if entry.ended_at else None,
        duration_ms=entry.duration_ms,
        end_reason=entry.end_reason,
    )


def _top_track_to_response(stats) -> TopTrackResponse:
    """Convert domain TrackPlayStats to response model."""
    return TopTrackResponse(
        track_id=stats.track.id,
        track_title=stats.track.title,
        track_artist=stats.track.artist,
        play_count=stats.play_count,
        total_duration_seconds=stats.total_duration_seconds,
    )
