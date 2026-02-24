"""SoundCloud import endpoints for Music Minion Web API.

SoundCloud tracks are imported as streaming-only (no download).
Metadata is stored with permalink URLs that are resolved via yt-dlp at playback time.
"""

import sqlite3
import time
import uuid
from enum import Enum
from threading import Lock
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from requests.exceptions import Timeout

from music_minion.domain.library.providers.soundcloud.exceptions import (
    DuplicateTrackError,
    InvalidSoundCloudURLError,
    SoundCloudError,
    TrackUnavailableError,
)
from music_minion.domain.library.providers.soundcloud.import_handlers import (
    get_playlist_preview as get_sc_playlist_preview,
    import_playlist,
    import_single_track,
)
from music_minion.domain.library.providers.soundcloud.api import (
    get_playlists as sc_get_playlists,
    get_playlist_tracks as sc_get_playlist_tracks,
)
from music_minion.domain.library.deduplication import find_best_matches_tfidf
from music_minion.domain.playlists.crud import (
    create_playlist as crud_create_playlist,
    add_track_to_playlist,
    get_playlist_by_name,
)
from web.backend.soundcloud_auth import get_web_provider_state
from web.backend.deps import get_db
from web.backend.schemas import (
    MatchPlaylistResponse,
    ScPlaylistMatch,
    ScCreatePlaylistRequest,
    ScCreatePlaylistResponse,
)

router = APIRouter()

# Job storage (in-memory for single-instance deployment)
# Jobs are cleaned up after JOB_TTL_SECONDS to prevent memory leaks
_jobs: dict[str, dict] = {}
_jobs_lock = Lock()
JOB_TTL_SECONDS = 3600  # 1 hour


class JobStatus(str, Enum):
    """Status of an import job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportTrackRequest(BaseModel):
    """Request model for single track import."""

    url: str  # SoundCloud track permalink
    artist: Optional[str] = None  # Falls back to track uploader
    title: Optional[str] = None  # Falls back to track title


class ImportPlaylistRequest(BaseModel):
    """Request model for playlist import."""

    playlist_url: str  # Full SoundCloud playlist URL


class TrackResponse(BaseModel):
    """Response model for imported track."""

    id: int
    title: str
    artist: Optional[str]
    soundcloud_id: str
    source_url: str  # Permalink for streaming
    duration: float


class ImportJobResponse(BaseModel):
    """Response model for job creation."""

    job_id: str
    status: JobStatus


class ImportJobStatusResponse(BaseModel):
    """Response model for job status polling."""

    job_id: str
    status: JobStatus
    progress: Optional[int] = None  # Percentage 0-100
    result: Optional[dict] = None  # ImportResult as dict when completed
    error: Optional[str] = None  # Error message if failed


class PlaylistInfoResponse(BaseModel):
    """Response model for playlist preview."""

    title: str
    track_count: int
    tracks: list[dict]  # [{id, title, duration}, ...]


# Job management functions


def _cleanup_old_jobs() -> None:
    """Remove jobs older than JOB_TTL_SECONDS. Must be called with _jobs_lock held."""
    cutoff = time.time() - JOB_TTL_SECONDS
    expired_ids = [
        job_id for job_id, job in _jobs.items() if job.get("created_at", 0) < cutoff
    ]
    for job_id in expired_ids:
        del _jobs[job_id]
    if expired_ids:
        logger.debug(f"Cleaned up {len(expired_ids)} expired SoundCloud import jobs")


def create_job() -> str:
    """Create a new import job and return its ID."""
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        # Clean up old jobs to prevent memory leak
        _cleanup_old_jobs()
        _jobs[job_id] = {
            "status": JobStatus.PENDING,
            "progress": None,
            "result": None,
            "error": None,
            "created_at": time.time(),
        }
    return job_id


def update_job(job_id: str, **kwargs) -> None:
    """Update job status and metadata."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[dict]:
    """Get job status and metadata."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            # Return copy without internal fields
            return {k: v for k, v in job.items() if k != "created_at"}
        return None


# Helper functions


def track_to_dict(track) -> dict:
    """Convert Track object to dict for API response."""
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "soundcloud_id": track.soundcloud_id,
        "source_url": track.source_url,
        "duration": track.duration,
    }


def import_result_to_dict(result) -> dict:
    """Convert SoundCloudImportResult to dict for API response."""
    return {
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count,
        "failures": [{"track_url": url, "error": err} for url, err in result.failures],
        "tracks": [track_to_dict(track) for track in result.tracks],
    }


# Background task workers


def run_track_import(job_id: str, req: ImportTrackRequest):
    """Background worker for single track import."""
    update_job(job_id, status=JobStatus.RUNNING)
    try:
        track = import_single_track(url=req.url, artist=req.artist, title=req.title)
        update_job(job_id, status=JobStatus.COMPLETED, result=track_to_dict(track))
        logger.info(
            f"SoundCloud track import job {job_id} completed: {track.artist} - {track.title}"
        )
    except DuplicateTrackError as e:
        error_msg = f"Track already imported as track #{e.track_id}"
        update_job(job_id, status=JobStatus.FAILED, error=error_msg)
        logger.warning(f"SoundCloud track import job {job_id} failed: {error_msg}")
    except InvalidSoundCloudURLError as e:
        update_job(
            job_id, status=JobStatus.FAILED, error=f"Invalid SoundCloud URL: {e}"
        )
        logger.warning(f"SoundCloud track import job {job_id} failed: Invalid URL")
    except TrackUnavailableError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
        logger.warning(f"SoundCloud track import job {job_id} failed: Unavailable")
    except SoundCloudError as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Import failed: {e}")
        logger.exception(
            f"SoundCloud track import job {job_id} failed with SoundCloudError"
        )
    except Exception as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Unexpected error: {e}")
        logger.exception(
            f"SoundCloud track import job {job_id} failed with unexpected error"
        )


def run_playlist_import(job_id: str, req: ImportPlaylistRequest):
    """Background worker for playlist import."""
    update_job(job_id, status=JobStatus.RUNNING)
    try:
        result = import_playlist(req.playlist_url)
        update_job(
            job_id, status=JobStatus.COMPLETED, result=import_result_to_dict(result)
        )
        logger.info(
            f"SoundCloud playlist import job {job_id} completed: {result.imported_count} imported, "
            f"{result.skipped_count} skipped, {result.failed_count} failed"
        )
    except SoundCloudError as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Import failed: {e}")
        logger.exception(
            f"SoundCloud playlist import job {job_id} failed with SoundCloudError"
        )
    except Exception as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Unexpected error: {e}")
        logger.exception(
            f"SoundCloud playlist import job {job_id} failed with unexpected error"
        )


# API Endpoints


@router.post("/import", response_model=ImportJobResponse)
async def import_soundcloud_track(
    req: ImportTrackRequest, background_tasks: BackgroundTasks
) -> ImportJobResponse:
    """Start background import of single SoundCloud track.

    SoundCloud tracks are stored as metadata only (no download).
    The permalink URL is used for streaming via yt-dlp at playback time.

    Returns job_id immediately. Poll /soundcloud/import/{job_id} for status.

    Args:
        req: Import request with URL and optional metadata overrides
        background_tasks: FastAPI background tasks

    Returns:
        Job ID and initial status
    """
    job_id = create_job()
    background_tasks.add_task(run_track_import, job_id, req)
    logger.info(f"Started SoundCloud track import job {job_id} for URL: {req.url}")
    return ImportJobResponse(job_id=job_id, status=JobStatus.PENDING)


@router.get("/import/{job_id}", response_model=ImportJobStatusResponse)
async def get_import_status(job_id: str) -> ImportJobStatusResponse:
    """Get status of import job. Poll until status is COMPLETED or FAILED.

    Args:
        job_id: Job ID from /soundcloud/import or /soundcloud/import-playlist

    Returns:
        Job status, progress, result, or error

    Raises:
        HTTPException: 404 if job not found
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ImportJobStatusResponse(job_id=job_id, **job)


@router.post("/import-playlist", response_model=ImportJobResponse)
async def import_soundcloud_playlist(
    req: ImportPlaylistRequest, background_tasks: BackgroundTasks
) -> ImportJobResponse:
    """Start background import of SoundCloud playlist.

    All tracks are imported as streaming-only (no download).

    Returns job_id immediately. Poll /soundcloud/import/{job_id} for status.

    Args:
        req: Import request with playlist URL
        background_tasks: FastAPI background tasks

    Returns:
        Job ID and initial status
    """
    job_id = create_job()
    background_tasks.add_task(run_playlist_import, job_id, req)
    logger.info(
        f"Started SoundCloud playlist import job {job_id} for URL: {req.playlist_url}"
    )
    return ImportJobResponse(job_id=job_id, status=JobStatus.PENDING)


@router.get("/playlist-preview")
async def get_playlist_preview(url: str) -> PlaylistInfoResponse:
    """Fetch playlist metadata for preview before importing.

    Allows users to see playlist title and track count before committing.

    Args:
        url: SoundCloud playlist URL (as query param)

    Returns:
        Playlist title, track count, and track list

    Raises:
        HTTPException: 400 for invalid playlist, 500 for other errors
    """
    try:
        info = get_sc_playlist_preview(url)
        return PlaylistInfoResponse(
            title=info["title"],
            track_count=info["track_count"],
            tracks=info["tracks"],
        )
    except InvalidSoundCloudURLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid playlist URL: {e}")
    except SoundCloudError as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch playlist: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error fetching SoundCloud playlist {url}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


# ============================================================================
# SoundCloud Import Wizard Endpoints
# ============================================================================


@router.get("/playlists")
async def get_soundcloud_playlists() -> list[dict]:
    """Get user's SoundCloud playlists.

    Returns: [{id, name, track_count}]

    Raises:
        HTTPException: 401 if not authenticated
    """
    state = get_web_provider_state()
    if not state:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

    try:
        updated_state, playlists = sc_get_playlists(state)

        # Check if auth failed during API call
        if not updated_state.authenticated:
            raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

        return [
            {
                "id": p["id"],
                "name": p["name"],
                "track_count": p["track_count"],
            }
            for p in playlists
        ]
    except HTTPException:
        raise
    except Timeout:
        raise HTTPException(
            status_code=503, detail="SoundCloud API timeout, please retry"
        )
    except Exception as e:
        logger.exception("Error fetching SoundCloud playlists")
        raise HTTPException(status_code=500, detail=f"Failed to fetch playlists: {e}")


class MatchPlaylistRequest(BaseModel):
    """Request to match a SoundCloud playlist to local library."""
    playlist_id: str


@router.post("/match-playlist")
async def match_playlist(
    request: MatchPlaylistRequest, db=Depends(get_db)
) -> MatchPlaylistResponse:
    """Match SoundCloud playlist tracks to local library.

    - Fetches tracks from SoundCloud
    - Runs TF-IDF matching against local library
    - Auto-approves matches >= 0.85 confidence
    - Returns all matches sorted by confidence (low to high)

    Args:
        request: Request with playlist_id

    Returns:
        MatchPlaylistResponse with matches and counts

    Raises:
        HTTPException: 401 if not authenticated, 404 if playlist not found
    """
    state = get_web_provider_state()
    if not state:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

    try:
        # Get playlist name first from playlists list
        updated_state, playlists = sc_get_playlists(state)
        if not updated_state.authenticated:
            raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

        playlist_info = next(
            (p for p in playlists if p["id"] == request.playlist_id), None
        )
        if not playlist_info:
            raise HTTPException(
                status_code=404, detail=f"Playlist not found: {request.playlist_id}"
            )

        playlist_name = playlist_info["name"]

        # Fetch tracks from SoundCloud playlist
        updated_state, sc_tracks, _ = sc_get_playlist_tracks(
            updated_state, request.playlist_id
        )
        if not updated_state.authenticated:
            raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

        # Get local tracks from database
        cursor = db.execute(
            "SELECT id, title, artist, album, local_path FROM tracks WHERE local_path IS NOT NULL"
        )
        local_tracks = [dict(row) for row in cursor.fetchall()]

        # Run TF-IDF matching (min_score=0.0 to get all matches)
        match_results = find_best_matches_tfidf(sc_tracks, local_tracks, min_score=0.0)

        # Build matches list
        matches: list[ScPlaylistMatch] = []
        auto_approved_count = 0
        needs_review_count = 0

        for position, (sc_id, sc_metadata) in enumerate(sc_tracks):
            # Find corresponding match result
            match_result = next(
                (r for r in match_results if r[0] == sc_id), (sc_id, None, 0.0)
            )
            _, local_track, confidence = match_result

            # Determine approval status
            is_approved = confidence >= 0.85
            is_missing = local_track is None

            if is_approved and not is_missing:
                auto_approved_count += 1
            elif not is_missing:
                needs_review_count += 1

            match = ScPlaylistMatch(
                sc_track_id=sc_id,
                sc_title=sc_metadata.get("title", ""),
                sc_artist=sc_metadata.get("artist", ""),
                local_track_id=local_track["id"] if local_track else None,
                local_title=local_track.get("title") if local_track else None,
                local_artist=local_track.get("artist") if local_track else None,
                confidence=confidence,
                is_approved=is_approved,
                is_missing=is_missing,
                sc_position=position,
            )
            matches.append(match)

        # Sort by confidence ascending (low first for review)
        matches.sort(key=lambda m: m.confidence)

        return MatchPlaylistResponse(
            playlist_name=playlist_name,
            sc_playlist_id=request.playlist_id,
            matches=matches,
            auto_approved_count=auto_approved_count,
            needs_review_count=needs_review_count,
        )

    except HTTPException:
        raise
    except Timeout:
        raise HTTPException(
            status_code=503, detail="SoundCloud API timeout, please retry"
        )
    except Exception as e:
        logger.exception(f"Error matching playlist {request.playlist_id}")
        raise HTTPException(status_code=500, detail=f"Failed to match playlist: {e}")


@router.post("/create-playlist-from-matches")
async def create_playlist_from_matches(
    request: ScCreatePlaylistRequest, db=Depends(get_db)
) -> ScCreatePlaylistResponse:
    """Create local playlist from matched tracks.

    - Creates playlist with given name
    - Adds matched tracks (excluding is_missing) in sc_position order
    - Links playlist to SoundCloud playlist ID for future sync
    - Sets soundcloud_id on matched local tracks for sync support

    Args:
        request: Request with playlist name, SC playlist ID, and matches

    Returns:
        ScCreatePlaylistResponse with playlist_id and track_count

    Raises:
        HTTPException: 400 if no valid matches, 409 if playlist name exists
    """
    # Filter matches: exclude is_missing=True, keep only with local_track_id
    valid_matches = [
        m
        for m in request.matches
        if not m.is_missing and m.local_track_id is not None
    ]

    if not valid_matches:
        raise HTTPException(status_code=400, detail="No tracks to add")

    # Check for duplicate playlist name using injected connection
    # (replaces get_playlist_by_name() which opens its own connection)
    cursor = db.execute(
        "SELECT id FROM playlists WHERE name = ? AND library = ?",
        (request.playlist_name, "local")
    )
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Playlist name already exists")

    # Sort by sc_position ascending (preserve playlist order)
    valid_matches.sort(key=lambda m: m.sc_position if m.sc_position is not None else 0)

    try:
        # Create playlist using injected connection
        # Note: Using direct SQL instead of crud_create_playlist() to:
        # 1. Avoid opening multiple connections (fixes database lock error)
        # 2. Skip SoundCloud sync trigger (we're importing FROM SoundCloud, not TO it)
        cursor = db.execute(
            "INSERT INTO playlists (name, type, library) VALUES (?, ?, ?)",
            (request.playlist_name, "manual", "local")
        )
        playlist_id = cursor.lastrowid

        # Link to SoundCloud playlist ID
        db.execute(
            "UPDATE playlists SET soundcloud_playlist_id = ? WHERE id = ?",
            (request.sc_playlist_id, playlist_id)
        )

        # Batch insert playlist_tracks (no need for duplicate check - new playlist)
        playlist_tracks = [
            (playlist_id, m.local_track_id, idx + 1)
            for idx, m in enumerate(valid_matches)
        ]
        db.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            playlist_tracks
        )

        # Batch update tracks with soundcloud_id
        # De-duplicate: only keep first occurrence of each sc_track_id
        seen_sc_ids: set[str] = set()
        track_updates = []
        for m in valid_matches:
            if m.sc_track_id and m.sc_track_id not in seen_sc_ids:
                track_updates.append((m.sc_track_id, m.local_track_id))
                seen_sc_ids.add(m.sc_track_id)

        # Update tracks one by one to handle conflicts gracefully
        for sc_track_id, local_track_id in track_updates:
            try:
                db.execute(
                    "UPDATE tracks SET soundcloud_id = ? WHERE id = ? AND soundcloud_id IS NULL",
                    (sc_track_id, local_track_id)
                )
            except sqlite3.IntegrityError:
                # SC track ID already assigned to another track - skip silently
                logger.debug(f"Skipping SC ID {sc_track_id} - already assigned to another track")

        # Update track count
        db.execute(
            "UPDATE playlists SET track_count = ? WHERE id = ?",
            (len(valid_matches), playlist_id)
        )

        db.commit()

        return ScCreatePlaylistResponse(
            playlist_id=playlist_id,
            track_count=len(valid_matches),
        )

    except sqlite3.IntegrityError as e:
        logger.error(f"IntegrityError during playlist creation: {e}")
        db.rollback()
        if "UNIQUE constraint" in str(e):
            # Provide more specific error based on which constraint failed
            error_str = str(e).lower()
            if "playlists.soundcloud_playlist_id" in error_str:
                detail = "This SoundCloud playlist is already linked to another local playlist"
            elif "playlists.spotify_playlist_id" in error_str:
                detail = "This Spotify playlist is already linked to another local playlist"
            elif "playlists.name" in error_str:
                detail = "Playlist name already exists"
            elif "tracks.soundcloud_id" in error_str:
                detail = "A track's SoundCloud ID conflicts with an existing track"
            else:
                detail = f"Database constraint error: {e}"
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.exception("Error creating playlist from matches")
        raise HTTPException(status_code=500, detail=f"Failed to create playlist: {e}")
