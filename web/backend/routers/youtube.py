"""YouTube import endpoints for Music Minion Web API."""

import uuid
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel

from music_minion.domain.library.providers.youtube import (
    download,
    import_playlist,
    import_single_video,
)
from music_minion.domain.library.providers.youtube.exceptions import (
    AgeRestrictedError,
    CopyrightBlockedError,
    DuplicateVideoError,
    InsufficientSpaceError,
    InvalidYouTubeURLError,
    VideoUnavailableError,
    YouTubeError,
)

router = APIRouter()

# Job storage (in-memory for single-instance deployment)
_jobs: dict[str, dict] = {}
_jobs_lock = Lock()


class JobStatus(str, Enum):
    """Status of an import job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportVideoRequest(BaseModel):
    """Request model for single video import."""

    url: str
    artist: Optional[str] = None  # Falls back to YouTube uploader
    title: Optional[str] = None  # Falls back to YouTube title
    album: Optional[str] = None


class ImportPlaylistRequest(BaseModel):
    """Request model for playlist import."""

    playlist_id: str


class TrackResponse(BaseModel):
    """Response model for imported track."""

    id: int
    title: str
    artist: Optional[str]
    album: Optional[str]
    youtube_id: str
    local_path: str
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
    video_count: int
    videos: list[dict]  # [{id, title, duration}, ...]


# Job management functions


def create_job() -> str:
    """Create a new import job and return its ID."""
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": JobStatus.PENDING,
            "progress": None,
            "result": None,
            "error": None,
        }
    return job_id


def update_job(job_id: str, **kwargs):
    """Update job status and metadata."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[dict]:
    """Get job status and metadata."""
    with _jobs_lock:
        return _jobs.get(job_id)


# Helper functions


def track_to_dict(track) -> dict:
    """Convert Track object to dict for API response."""
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "youtube_id": track.youtube_id,
        "local_path": track.local_path,
        "duration": track.duration,
    }


def import_result_to_dict(result) -> dict:
    """Convert ImportResult to dict for API response."""
    return {
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count,
        "failures": [{"video_id": vid, "error": err} for vid, err in result.failures],
        "tracks": [track_to_dict(track) for track in result.tracks],
    }


# Background task workers


def run_video_import(job_id: str, req: ImportVideoRequest):
    """Background worker for single video import."""
    update_job(job_id, status=JobStatus.RUNNING)
    try:
        track = import_single_video(
            url=req.url, artist=req.artist, title=req.title, album=req.album
        )
        update_job(job_id, status=JobStatus.COMPLETED, result=track_to_dict(track))
        logger.info(f"Video import job {job_id} completed: {track.artist} - {track.title}")
    except DuplicateVideoError as e:
        error_msg = f"Video already imported as track #{e.track_id}"
        update_job(job_id, status=JobStatus.FAILED, error=error_msg)
        logger.warning(f"Video import job {job_id} failed: {error_msg}")
    except InvalidYouTubeURLError as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Invalid YouTube URL: {e}")
        logger.warning(f"Video import job {job_id} failed: Invalid URL")
    except AgeRestrictedError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
        logger.warning(f"Video import job {job_id} failed: Age-restricted")
    except VideoUnavailableError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
        logger.warning(f"Video import job {job_id} failed: Unavailable")
    except InsufficientSpaceError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
        logger.error(f"Video import job {job_id} failed: Insufficient space")
    except YouTubeError as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Import failed: {e}")
        logger.exception(f"Video import job {job_id} failed with YouTubeError")
    except Exception as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Unexpected error: {e}")
        logger.exception(f"Video import job {job_id} failed with unexpected error")


def run_playlist_import(job_id: str, req: ImportPlaylistRequest):
    """Background worker for playlist import."""
    update_job(job_id, status=JobStatus.RUNNING)
    try:
        result = import_playlist(req.playlist_id)
        update_job(
            job_id, status=JobStatus.COMPLETED, result=import_result_to_dict(result)
        )
        logger.info(
            f"Playlist import job {job_id} completed: {result.imported_count} imported, "
            f"{result.skipped_count} skipped, {result.failed_count} failed"
        )
    except InsufficientSpaceError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
        logger.error(f"Playlist import job {job_id} failed: Insufficient space")
    except YouTubeError as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Import failed: {e}")
        logger.exception(f"Playlist import job {job_id} failed with YouTubeError")
    except Exception as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Unexpected error: {e}")
        logger.exception(f"Playlist import job {job_id} failed with unexpected error")


# API Endpoints


@router.post("/import", response_model=ImportJobResponse)
async def import_youtube_video(
    req: ImportVideoRequest, background_tasks: BackgroundTasks
) -> ImportJobResponse:
    """Start background import of single YouTube video.

    Returns job_id immediately. Poll /youtube/import/{job_id} for status.

    Args:
        req: Import request with URL and optional metadata
        background_tasks: FastAPI background tasks

    Returns:
        Job ID and initial status
    """
    job_id = create_job()
    background_tasks.add_task(run_video_import, job_id, req)
    logger.info(f"Started video import job {job_id} for URL: {req.url}")
    return ImportJobResponse(job_id=job_id, status=JobStatus.PENDING)


@router.get("/import/{job_id}", response_model=ImportJobStatusResponse)
async def get_import_status(job_id: str) -> ImportJobStatusResponse:
    """Get status of import job. Poll until status is COMPLETED or FAILED.

    Args:
        job_id: Job ID from /youtube/import or /youtube/import-playlist

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
async def import_youtube_playlist(
    req: ImportPlaylistRequest, background_tasks: BackgroundTasks
) -> ImportJobResponse:
    """Start background import of YouTube playlist.

    Returns job_id immediately. Poll /youtube/import/{job_id} for status.

    Args:
        req: Import request with playlist ID
        background_tasks: FastAPI background tasks

    Returns:
        Job ID and initial status
    """
    job_id = create_job()
    background_tasks.add_task(run_playlist_import, job_id, req)
    logger.info(f"Started playlist import job {job_id} for playlist: {req.playlist_id}")
    return ImportJobResponse(job_id=job_id, status=JobStatus.PENDING)


@router.get("/playlist/{playlist_id}", response_model=PlaylistInfoResponse)
async def get_playlist_preview(playlist_id: str) -> PlaylistInfoResponse:
    """Fetch playlist metadata for preview before importing.

    Allows users to see playlist title and video count before committing.

    Args:
        playlist_id: YouTube playlist ID

    Returns:
        Playlist title, video count, and video list

    Raises:
        HTTPException: 400 for invalid playlist, 500 for other errors
    """
    try:
        info = download.get_playlist_info(playlist_id)
        return PlaylistInfoResponse(
            title=info["title"], video_count=info["video_count"], videos=info["videos"]
        )
    except InvalidYouTubeURLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid playlist ID: {e}")
    except VideoUnavailableError as e:
        raise HTTPException(status_code=404, detail=f"Playlist not found: {e}")
    except YouTubeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch playlist: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error fetching playlist {playlist_id}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
