"""Playlist builder API endpoints.

Provides RESTful API for the web-based playlist builder with:
- Session management
- Track operations (add/skip)
- Filter management
- Candidate selection
- Review endpoints
- Context activation (web mode)
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from ..deps import get_db
from ..schemas import (
    BuilderStartSessionRequest,
    BuilderStartSessionResponse,
    SessionResponse,
    TrackActionResponse,
    Filter,
    UpdateFiltersRequest,
    FiltersResponse,
    CandidatesResponse,
    SkippedTracksResponse,
)

from music_minion.domain.playlists import builder
from music_minion.core.database import get_db_connection
from music_minion.ipc import send_command


router = APIRouter()


# Helper: Validate playlist exists and is manual type


def _validate_manual_playlist(playlist_id: int) -> dict:
    """Validate that playlist exists and is manual type.

    Args:
        playlist_id: Playlist ID to validate

    Returns:
        Playlist dict

    Raises:
        HTTPException: 404 if not found, 400 if not manual type
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, type FROM playlists WHERE id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Playlist not found")

        playlist = dict(row)
        if playlist["type"] != "manual":
            raise HTTPException(
                status_code=400,
                detail="Only manual playlists supported. Smart playlists use auto-filtering.",
            )

        return playlist


# Session Management Endpoints


@router.post("/session/start", response_model=BuilderStartSessionResponse)
async def start_session(request: BuilderStartSessionRequest):
    """Start or resume builder session.

    Validates:
    - Playlist exists
    - Playlist is manual (not smart)

    Returns session metadata (no current track).
    Frontend calls /candidates/next separately.
    """
    try:
        # Validate playlist
        _validate_manual_playlist(request.playlist_id)

        # Start/resume session
        session = builder.start_builder_session(request.playlist_id)

        return BuilderStartSessionResponse(**session)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{playlist_id}", response_model=SessionResponse)
async def get_session(playlist_id: int):
    """Get active session state."""
    try:
        session = builder.get_active_session(playlist_id)

        if not session:
            raise HTTPException(status_code=404, detail="No active session")

        return SessionResponse(**session)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{playlist_id}")
async def end_session(playlist_id: int):
    """End builder session and cleanup."""
    try:
        builder.end_builder_session(playlist_id)
        return {"success": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Track Operation Endpoints


@router.post("/add/{playlist_id}/{track_id}", response_model=TrackActionResponse)
async def add_track_to_playlist(playlist_id: int, track_id: int):
    """Add track to playlist.

    Returns success status. Frontend calls /candidates/next for next track.
    """
    try:
        # Validate playlist
        _validate_manual_playlist(playlist_id)

        # Add track
        result = builder.add_track(playlist_id, track_id)

        # Update last processed track
        if result["success"]:
            builder.update_last_processed_track(playlist_id, track_id)

        return TrackActionResponse(success=result["success"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skip/{playlist_id}/{track_id}", response_model=TrackActionResponse)
async def skip_track(playlist_id: int, track_id: int):
    """Skip track permanently.

    Adds track to skipped list. Frontend calls /candidates/next for next track.
    """
    try:
        # Validate playlist
        _validate_manual_playlist(playlist_id)

        # Skip track
        result = builder.skip_track(playlist_id, track_id)

        # Update last processed track
        if result["success"]:
            builder.update_last_processed_track(playlist_id, track_id)

        return TrackActionResponse(success=result["success"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/{playlist_id}/next")
async def get_next_candidate(
    playlist_id: int, exclude_track_id: Optional[int] = None
):
    """Get next random candidate track.

    Excludes last processed track for variety.
    Returns None if no candidates available.

    Query params:
        exclude_track_id: Track ID to exclude (typically last processed)
    """
    try:
        # Validate playlist
        _validate_manual_playlist(playlist_id)

        # Get next candidate
        candidate = builder.get_next_candidate(playlist_id, exclude_track_id)

        return candidate  # Can be None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Filter Management Endpoints


@router.get("/filters/{playlist_id}", response_model=FiltersResponse)
async def get_filters(playlist_id: int):
    """Get current builder filters."""
    try:
        filters = builder.get_builder_filters(playlist_id)

        return FiltersResponse(
            filters=[Filter(**f) for f in filters]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/filters/{playlist_id}")
async def update_filters(playlist_id: int, request: UpdateFiltersRequest):
    """Update builder filters (atomic replace).

    Validates filters using domain logic.
    """
    try:
        # Validate playlist
        _validate_manual_playlist(playlist_id)

        # Convert Pydantic models to dicts
        filters = [f.model_dump() for f in request.filters]

        # Set filters (validates internally)
        builder.set_builder_filters(playlist_id, filters)

        return {"success": True}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/filters/{playlist_id}")
async def clear_filters(playlist_id: int):
    """Remove all builder filters."""
    try:
        builder.clear_builder_filters(playlist_id)
        return {"success": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Review Endpoints


@router.get("/candidates/{playlist_id}", response_model=CandidatesResponse)
async def get_candidates(
    playlist_id: int, limit: int = 50, offset: int = 0
):
    """Get paginated list of candidate tracks."""
    try:
        # Validate playlist
        _validate_manual_playlist(playlist_id)

        # Get all candidates (already limited to 100 by domain logic)
        all_candidates = builder.get_candidate_tracks(playlist_id)

        # Apply pagination
        paginated = all_candidates[offset : offset + limit]

        return CandidatesResponse(
            candidates=paginated,
            total=len(all_candidates),
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skipped/{playlist_id}", response_model=SkippedTracksResponse)
async def get_skipped_tracks(playlist_id: int):
    """Get list of skipped tracks for review."""
    try:
        skipped = builder.get_skipped_tracks(playlist_id)

        return SkippedTracksResponse(
            skipped=skipped,
            total=len(skipped),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skipped/{playlist_id}/{track_id}")
async def unskip_track(playlist_id: int, track_id: int):
    """Remove track from skipped list."""
    try:
        builder.unskip_track(playlist_id, track_id)
        return {"success": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Context Activation Endpoints


@router.post("/activate/{playlist_id}")
async def activate_builder_mode(playlist_id: int):
    """Activate builder mode in CLI context.

    Sends IPC command to set active_web_mode='builder' so that
    web-winner/web-archive hotkeys work correctly.

    Args:
        playlist_id: The playlist being built
    """
    import logging
    log = logging.getLogger(__name__)
    log.info(f"activate_builder_mode called with playlist_id={playlist_id}")

    try:
        # Validate playlist exists
        _validate_manual_playlist(playlist_id)

        # Send IPC command to CLI
        log.info(f"Sending IPC command: set-web-mode builder {playlist_id}")
        success, message = send_command("set-web-mode", ["builder", str(playlist_id)])
        log.info(f"IPC response: success={success}, message={message}")

        if not success:
            raise HTTPException(status_code=503, detail=f"CLI not responding: {message}")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/activate")
async def deactivate_builder_mode():
    """Deactivate builder mode in CLI context.

    Sends IPC command to clear active_web_mode.
    Called when leaving the builder page.
    """
    try:
        # Send IPC command to CLI
        success, message = send_command("set-web-mode", ["none"])

        if not success:
            # Don't fail hard - CLI might have restarted
            return {"success": True, "warning": message}

        return {"success": True}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
