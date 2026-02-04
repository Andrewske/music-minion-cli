"""SoundCloud import endpoints for Music Minion Web API.

SoundCloud tracks are imported as streaming-only (no download).
Metadata is stored with permalink URLs that are resolved via yt-dlp at playback time.
"""

import time
import uuid
from enum import Enum
from threading import Lock
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel

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
