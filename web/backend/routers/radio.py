"""
Radio station API endpoints.

Provides endpoints for Liquidsoap integration and station management.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel


router = APIRouter(prefix="/radio", tags=["radio"])


# === Pydantic Models ===


class StationResponse(BaseModel):
    """Station representation for API responses."""

    id: int
    name: str
    playlist_id: Optional[int]
    mode: str
    is_active: bool


class ScheduleEntryResponse(BaseModel):
    """Schedule entry representation for API responses."""

    id: int
    station_id: int
    start_time: str
    end_time: str
    target_station_id: int
    position: int


class TrackResponse(BaseModel):
    """Track representation for API responses."""

    id: int
    title: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    duration: Optional[float]
    local_path: Optional[str]


class NowPlayingResponse(BaseModel):
    """Current playback state for API responses."""

    track: TrackResponse
    position_ms: int
    station_id: int
    station_name: str
    source_type: str
    upcoming: list[TrackResponse]


class CreateStationRequest(BaseModel):
    """Request body for creating a station."""

    name: str
    playlist_id: Optional[int] = None
    mode: str = "shuffle"


class UpdateStationRequest(BaseModel):
    """Request body for updating a station."""

    name: Optional[str] = None
    playlist_id: Optional[int] = None
    mode: Optional[str] = None


class CreateScheduleRequest(BaseModel):
    """Request body for creating a schedule entry."""

    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"
    target_station_id: int


class UpdateScheduleRequest(BaseModel):
    """Request body for updating a schedule entry."""

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    target_station_id: Optional[int] = None
    position: Optional[int] = None


# === Helper Functions ===


def _station_to_response(station) -> StationResponse:
    """Convert Station dataclass to response model."""
    return StationResponse(
        id=station.id,
        name=station.name,
        playlist_id=station.playlist_id,
        mode=station.mode,
        is_active=station.is_active,
    )


def _schedule_entry_to_response(entry) -> ScheduleEntryResponse:
    """Convert ScheduleEntry dataclass to response model."""
    return ScheduleEntryResponse(
        id=entry.id,
        station_id=entry.station_id,
        start_time=entry.start_time,
        end_time=entry.end_time,
        target_station_id=entry.target_station_id,
        position=entry.position,
    )


def _track_to_response(track) -> TrackResponse:
    """Convert Track NamedTuple to response model."""
    return TrackResponse(
        id=track.id or 0,
        title=track.title,
        artist=track.artist,
        album=track.album,
        duration=track.duration,
        local_path=track.local_path,
    )


# === Liquidsoap Integration ===


@router.get("/next-track")
def get_next_track() -> Response:
    """
    Get next track path for Liquidsoap.

    Returns plain text file path for direct consumption by Liquidsoap.
    Note: This queues the track - actual playback is reported via /track-started.
    """
    from music_minion.domain.radio import (
        get_active_station,
        get_next_track as _get_next_track,
    )

    station = get_active_station()
    if not station:
        logger.warning("No active station for next-track request")
        raise HTTPException(status_code=404, detail="No active station")

    track = _get_next_track(station.id, datetime.now())
    if not track:
        logger.warning(f"No track available for station {station.id}")
        raise HTTPException(status_code=404, detail="No track available")

    if not track.local_path:
        logger.warning(f"Track {track.id} has no local path")
        raise HTTPException(status_code=404, detail="Track has no local path")

    logger.info(f"Queuing track for Liquidsoap: {track.local_path}")
    return Response(content=track.local_path, media_type="text/plain")


@router.post("/track-error/{track_id}")
def report_track_error(track_id: int, reason: str = "unavailable") -> Response:
    """
    Report that a track failed to play.

    Marks the track as skipped and returns the next available track.
    """
    from music_minion.domain.radio import (
        get_active_station,
        get_next_track as _get_next_track,
        mark_track_skipped,
    )

    station = get_active_station()
    if not station:
        raise HTTPException(status_code=404, detail="No active station")

    # Mark track as skipped for today
    mark_track_skipped(station.id, track_id, reason)

    # Get replacement track
    track = _get_next_track(station.id, datetime.now())
    if not track or not track.local_path:
        raise HTTPException(status_code=404, detail="No replacement track available")

    logger.info(f"Serving replacement track after error: {track.local_path}")
    return Response(content=track.local_path, media_type="text/plain")


@router.post("/track-started")
async def track_started(request: Request) -> Response:
    """
    Called by Liquidsoap when a track actually starts playing.

    This is more accurate than /next-track because Liquidsoap queues
    tracks ahead of time. This callback fires when playback begins.
    """
    from music_minion.core.db_adapter import get_radio_db_connection
    from music_minion.domain.radio import get_active_station, record_now_playing

    # Get the file path from request body
    body = await request.body()
    file_path = body.decode("utf-8").strip()

    if not file_path:
        return Response(content="No path provided", status_code=400)

    station = get_active_station()
    if not station:
        return Response(content="No active station", status_code=404)

    # Look up track by path
    with get_radio_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM tracks WHERE local_path = ?",
            (file_path,),
        )
        row = cursor.fetchone()

    if row:
        record_now_playing(station.id, row["id"])
        logger.info(f"Track started playing: {file_path} (id={row['id']})")
        return Response(content="OK", status_code=200)
    else:
        logger.warning(f"Track not found in database: {file_path}")
        return Response(content="Track not found", status_code=404)


# === Now Playing ===


@router.get("/now-playing", response_model=NowPlayingResponse)
def get_now_playing() -> NowPlayingResponse:
    """Get current now-playing state.

    Uses actual track from Liquidsoap (recorded when it requests /next-track)
    for accurate sync with the stream. Falls back to timeline calculation
    if Liquidsoap hasn't requested a track yet.
    """
    from music_minion.core.db_adapter import get_radio_db_connection
    from music_minion.domain.radio import (
        calculate_now_playing,
        get_active_station,
        get_actual_now_playing,
        get_station,
    )

    station = get_active_station()
    if not station:
        raise HTTPException(status_code=404, detail="No active station")

    # Try to get actual track from Liquidsoap
    actual = get_actual_now_playing()
    if actual:
        track_id, started_at = actual
        # Get track details from database
        with get_radio_db_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, local_path, title, artist, album, duration
                FROM tracks WHERE id = ?
                """,
                (track_id,),
            )
            row = cursor.fetchone()

        if row:
            from music_minion.domain.library.models import Track

            track = Track(
                id=row["id"],
                local_path=row["local_path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
            )

            # Calculate position based on when track started
            elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
            # Cap at track duration to avoid showing > 100%
            duration_ms = int((track.duration or 0) * 1000)
            position_ms = min(elapsed_ms, duration_ms) if duration_ms > 0 else elapsed_ms

            # Get upcoming from timeline calculation
            now_playing = calculate_now_playing(station.id, datetime.now())
            upcoming = now_playing.upcoming if now_playing else []

            return NowPlayingResponse(
                track=_track_to_response(track),
                position_ms=position_ms,
                station_id=station.id,
                station_name=station.name,
                source_type="local",
                upcoming=[_track_to_response(t) for t in upcoming],
            )

    # Fallback to timeline calculation
    now_playing = calculate_now_playing(station.id, datetime.now())
    if not now_playing:
        raise HTTPException(status_code=404, detail="Nothing playing")

    resolved_station = get_station(now_playing.station_id)

    return NowPlayingResponse(
        track=_track_to_response(now_playing.track),
        position_ms=now_playing.position_ms,
        station_id=now_playing.station_id,
        station_name=resolved_station.name if resolved_station else "Unknown",
        source_type=now_playing.source_type,
        upcoming=[_track_to_response(t) for t in now_playing.upcoming],
    )


# === Stations CRUD ===


@router.get("/stations", response_model=list[StationResponse])
def list_stations() -> list[StationResponse]:
    """List all stations."""
    from music_minion.domain.radio import get_all_stations

    return [_station_to_response(s) for s in get_all_stations()]


@router.post("/stations", response_model=StationResponse, status_code=201)
def create_station(req: CreateStationRequest) -> StationResponse:
    """Create a new station."""
    from music_minion.domain.radio import create_station as _create_station

    try:
        station = _create_station(req.name, req.playlist_id, req.mode)
        return _station_to_response(station)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stations/{station_id}", response_model=StationResponse)
def get_station_by_id(station_id: int) -> StationResponse:
    """Get a specific station."""
    from music_minion.domain.radio import get_station

    station = get_station(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return _station_to_response(station)


@router.put("/stations/{station_id}", response_model=StationResponse)
def update_station(station_id: int, req: UpdateStationRequest) -> StationResponse:
    """Update a station."""
    from music_minion.domain.radio import get_station, update_station as _update_station

    updates = {k: v for k, v in req.model_dump().items() if v is not None}

    try:
        if not _update_station(station_id, **updates):
            raise HTTPException(status_code=404, detail="Station not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    station = get_station(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return _station_to_response(station)


@router.delete("/stations/{station_id}")
def delete_station(station_id: int) -> dict[str, bool]:
    """Delete a station."""
    from music_minion.domain.radio import delete_station as _delete_station

    if not _delete_station(station_id):
        raise HTTPException(status_code=404, detail="Station not found")
    return {"ok": True}


@router.post("/stations/{station_id}/activate")
def activate_station(station_id: int) -> dict[str, str | bool]:
    """Activate a station (starts radio)."""
    from music_minion.domain.radio import activate_station as _activate_station

    if not _activate_station(station_id):
        raise HTTPException(status_code=404, detail="Station not found")
    return {"ok": True, "message": "Station activated"}


@router.post("/stations/deactivate")
def deactivate_all() -> dict[str, bool]:
    """Deactivate all stations (stop radio)."""
    from music_minion.domain.radio import deactivate_all_stations

    deactivated = deactivate_all_stations()
    return {"ok": True, "was_active": deactivated}


# === Schedule CRUD ===


@router.get(
    "/stations/{station_id}/schedule", response_model=list[ScheduleEntryResponse]
)
def get_schedule(station_id: int) -> list[ScheduleEntryResponse]:
    """Get schedule entries for a station."""
    from music_minion.domain.radio import get_schedule_entries

    return [_schedule_entry_to_response(e) for e in get_schedule_entries(station_id)]


@router.post(
    "/stations/{station_id}/schedule",
    response_model=ScheduleEntryResponse,
    status_code=201,
)
def add_schedule_entry(
    station_id: int, req: CreateScheduleRequest
) -> ScheduleEntryResponse:
    """Add a schedule entry."""
    from music_minion.domain.radio import (
        add_schedule_entry as _add_schedule_entry,
        get_station,
    )

    # Verify station exists
    if not get_station(station_id):
        raise HTTPException(status_code=404, detail="Station not found")

    try:
        entry = _add_schedule_entry(
            station_id, req.start_time, req.end_time, req.target_station_id
        )
        return _schedule_entry_to_response(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/schedule/{entry_id}", response_model=ScheduleEntryResponse)
def update_schedule_entry(
    entry_id: int, req: UpdateScheduleRequest
) -> ScheduleEntryResponse:
    """Update a schedule entry."""
    from music_minion.domain.radio import (
        get_schedule_entry,
        update_schedule_entry as _update_schedule_entry,
    )

    updates = {k: v for k, v in req.model_dump().items() if v is not None}

    try:
        if not _update_schedule_entry(entry_id, **updates):
            raise HTTPException(status_code=404, detail="Entry not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    entry = get_schedule_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _schedule_entry_to_response(entry)


@router.delete("/schedule/{entry_id}")
def delete_schedule_entry(entry_id: int) -> dict[str, bool]:
    """Delete a schedule entry."""
    from music_minion.domain.radio import (
        delete_schedule_entry as _delete_schedule_entry,
    )

    if not _delete_schedule_entry(entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}


@router.put("/stations/{station_id}/schedule/reorder")
def reorder_schedule(station_id: int, entry_ids: list[int]) -> dict[str, bool]:
    """Reorder schedule entries for a station."""
    from music_minion.domain.radio import reorder_schedule_entries

    try:
        reorder_schedule_entries(station_id, entry_ids)
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Failed to reorder schedule for station {station_id}")
        raise HTTPException(status_code=500, detail=str(e))
