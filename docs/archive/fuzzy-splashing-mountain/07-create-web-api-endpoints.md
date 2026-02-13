# Create Web API Endpoints for YouTube Import

## Files to Create
- `web/backend/routers/youtube.py` (new)

## Files to Modify
- `web/backend/main.py` (modify - register router)

## Implementation Details

Create FastAPI endpoints for YouTube imports with **background task processing** to avoid gateway timeouts.

### Create `routers/youtube.py`

#### Request/Response Models

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ImportVideoRequest(BaseModel):
    url: str
    artist: Optional[str] = None  # Falls back to YouTube uploader
    title: Optional[str] = None   # Falls back to YouTube title
    album: Optional[str] = None

class ImportPlaylistRequest(BaseModel):
    playlist_id: str

class TrackResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str]
    album: Optional[str]
    youtube_id: str
    local_path: str
    duration: float

class ImportJobResponse(BaseModel):
    job_id: str
    status: JobStatus

class ImportJobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: Optional[int] = None  # Percentage 0-100
    result: Optional[dict] = None   # ImportResult as dict when completed
    error: Optional[str] = None     # Error message if failed

class PlaylistInfoResponse(BaseModel):
    title: str
    video_count: int
    videos: list[dict]  # [{id, title, duration}, ...]
```

#### Job Storage

Use simple in-memory dict for job tracking (acceptable for single-instance deployment):

```python
import uuid
from threading import Lock

_jobs: dict[str, dict] = {}
_jobs_lock = Lock()

def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": JobStatus.PENDING, "result": None, "error": None}
    return job_id

def update_job(job_id: str, **kwargs):
    with _jobs_lock:
        _jobs[job_id].update(kwargs)

def get_job(job_id: str) -> Optional[dict]:
    with _jobs_lock:
        return _jobs.get(job_id)
```

#### Endpoints

##### `POST /youtube/import`

Start a background import for a single YouTube video.

```python
from fastapi import BackgroundTasks

@router.post("/youtube/import")
async def import_youtube_video(
    req: ImportVideoRequest,
    background_tasks: BackgroundTasks
) -> ImportJobResponse:
    """Start background import of single YouTube video.

    Returns job_id immediately. Poll /youtube/import/{job_id} for status.
    """
    job_id = create_job()
    background_tasks.add_task(run_video_import, job_id, req)
    return ImportJobResponse(job_id=job_id, status=JobStatus.PENDING)

def run_video_import(job_id: str, req: ImportVideoRequest):
    update_job(job_id, status=JobStatus.RUNNING)
    try:
        track = import_single_video(req.url, req.artist, req.title, req.album)
        update_job(job_id, status=JobStatus.COMPLETED, result=track_to_dict(track))
    except DuplicateVideoError as e:
        update_job(job_id, status=JobStatus.FAILED, error=f"Duplicate: track #{e.track_id}")
    except YouTubeError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
```

##### `GET /youtube/import/{job_id}`

Check status of an import job.

```python
@router.get("/youtube/import/{job_id}")
async def get_import_status(job_id: str) -> ImportJobStatusResponse:
    """Get status of import job. Poll until status is COMPLETED or FAILED."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ImportJobStatusResponse(job_id=job_id, **job)
```

##### `POST /youtube/import-playlist`

Start a background import for a playlist.

```python
@router.post("/youtube/import-playlist")
async def import_youtube_playlist(
    req: ImportPlaylistRequest,
    background_tasks: BackgroundTasks
) -> ImportJobResponse:
    """Start background import of YouTube playlist.

    Returns job_id immediately. Poll /youtube/import/{job_id} for status.
    """
    job_id = create_job()
    background_tasks.add_task(run_playlist_import, job_id, req)
    return ImportJobResponse(job_id=job_id, status=JobStatus.PENDING)

def run_playlist_import(job_id: str, req: ImportPlaylistRequest):
    update_job(job_id, status=JobStatus.RUNNING)
    try:
        result = import_playlist(req.playlist_id)
        update_job(job_id, status=JobStatus.COMPLETED, result=result_to_dict(result))
    except YouTubeError as e:
        update_job(job_id, status=JobStatus.FAILED, error=str(e))
```

##### `GET /youtube/playlist/{playlist_id}` (NEW)

Get playlist info for preview before importing.

```python
@router.get("/youtube/playlist/{playlist_id}")
async def get_playlist_info(playlist_id: str) -> PlaylistInfoResponse:
    """Fetch playlist metadata for preview before importing.

    Allows users to see playlist title and video count before committing.
    """
    try:
        info = download.get_playlist_info(playlist_id)
        return PlaylistInfoResponse(
            title=info["title"],
            video_count=info["video_count"],
            videos=info["videos"]
        )
    except YouTubeError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Register Router in `main.py`

Add import and registration:
```python
from routers import youtube

# In create_app() or main setup:
app.include_router(youtube.router, prefix="/youtube", tags=["youtube"])
```

### Error Handling

Map domain exceptions to HTTP status codes:

```python
from fastapi import HTTPException
from music_minion.domain.library.providers.youtube.exceptions import (
    DuplicateVideoError,
    InvalidYouTubeURLError,
    VideoUnavailableError,
    AgeRestrictedError,
    YouTubeError
)

# In synchronous endpoints (preview):
try:
    ...
except InvalidYouTubeURLError:
    raise HTTPException(status_code=400, detail="Invalid YouTube URL")
except VideoUnavailableError:
    raise HTTPException(status_code=404, detail="Video unavailable or deleted")
except AgeRestrictedError:
    raise HTTPException(status_code=403, detail="Age-restricted content not supported")
except DuplicateVideoError as e:
    raise HTTPException(status_code=409, detail=f"Already imported as track #{e.track_id}")
except YouTubeError as e:
    raise HTTPException(status_code=500, detail=str(e))
```

## Acceptance Criteria

- [ ] POST /youtube/import returns job_id immediately (background processing)
- [ ] GET /youtube/import/{job_id} returns job status and result
- [ ] POST /youtube/import-playlist returns job_id immediately
- [ ] GET /youtube/playlist/{playlist_id} returns playlist preview info
- [ ] Metadata is optional, falls back to YouTube metadata
- [ ] Domain exceptions mapped to proper HTTP status codes (400, 403, 404, 409, 500)
- [ ] Job storage thread-safe with Lock
- [ ] Router registered in main.py with /youtube prefix
- [ ] Pydantic models validate request data

## Dependencies

- Task 06 (CLI commands) must be complete - reuses same import functions
