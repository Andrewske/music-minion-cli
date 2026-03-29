"""
Discovery API endpoints.

Provides artist seed, SC user ID resolution, sync trigger/status, and
WebSocket progress broadcasting for the SoundCloud discovery workflow.
"""

import asyncio
import threading
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger
from pydantic import BaseModel
from typing import Optional, Any
import time

from web.backend.queries import discovery as discovery_queries
from web.backend.soundcloud_auth import get_web_provider_state
from web.backend.discovery_sync import run_discovery_sync
from music_minion.domain.library.providers.soundcloud.api import resolve_user_by_slug

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

# === Job Tracking ===

_sync_jobs: dict[str, dict] = {}
_sync_lock = threading.Lock()


# === Pydantic Models ===


class SeedArtistsRequest(BaseModel):
    csv_path: str = "/home/kevin/coding/soundcloud-discovery/config/artist_tiers.csv"


class SeedArtistsResponse(BaseModel):
    artists_imported: int
    resolution_started: bool


class ArtistResponse(BaseModel):
    id: int
    slug: str
    display_name: Optional[str] = None
    soundcloud_user_id: Optional[str] = None
    ranking: int
    tier: Optional[str] = None
    hit_rate: float
    tracks_seen: int
    tracks_liked: int
    tracks_dismissed: int
    check_interval_days: int
    is_following: bool


class SyncRequest(BaseModel):
    dry_run: bool = False


class SyncJobResponse(BaseModel):
    job_id: str


class SyncStatusResponse(BaseModel):
    status: str  # running/completed/failed
    progress_message: Optional[str] = None
    progress_current: int = 0
    progress_total: int = 0
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class UpdateStatsRequest(BaseModel):
    liked_sc_ids: list[str]
    dismissed_sc_ids: list[str]


# === Background Tasks ===


def _resolve_artists_background() -> None:
    """Background task: resolve SC user IDs for all unresolved artists."""
    state = get_web_provider_state()
    if state is None:
        logger.warning("Cannot resolve artists: not authenticated with SoundCloud")
        return

    unresolved = discovery_queries.get_artists_needing_resolution()
    logger.info(f"Resolving SC user IDs for {len(unresolved)} artists...")

    resolved = 0
    failed = 0
    for artist in unresolved:
        state, user_data, error = resolve_user_by_slug(state, artist["slug"])
        if user_data and user_data.get("id"):
            discovery_queries.update_artist_sc_id(
                slug=artist["slug"],
                sc_user_id=str(user_data["id"]),
                display_name=user_data.get("username", artist["slug"]),
            )
            resolved += 1
        else:
            logger.warning(f"Failed to resolve '{artist['slug']}': {error}")
            failed += 1

        # Rate limiting: 200ms between requests
        time.sleep(0.2)

    logger.info(f"Artist resolution complete: {resolved} resolved, {failed} failed")


def _broadcast_sync_progress(message: str, current: int, total: int) -> None:
    """Broadcast sync progress to all connected WebSocket clients (best-effort)."""
    try:
        from web.backend.sync_manager import sync_manager

        payload = {
            "message": message,
            "current": current,
            "total": total,
        }
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            sync_manager.broadcast("discovery_sync_progress", payload), loop
        )
    except Exception:
        pass  # WebSocket broadcast is best-effort


def _run_sync_background(job_id: str, dry_run: bool) -> None:
    """Background task: run discovery sync with progress tracking."""

    def progress_callback(message: str, current: int, total: int) -> None:
        with _sync_lock:
            if job_id in _sync_jobs:
                _sync_jobs[job_id]["progress_message"] = message
                _sync_jobs[job_id]["progress_current"] = current
                _sync_jobs[job_id]["progress_total"] = total
        _broadcast_sync_progress(message, current, total)

    try:
        result = run_discovery_sync(dry_run=dry_run, progress_callback=progress_callback)
        with _sync_lock:
            _sync_jobs[job_id]["status"] = "completed"
            _sync_jobs[job_id]["result"] = {
                "tracks_fetched": result.tracks_fetched,
                "tracks_new": result.tracks_new,
                "tracks_added_to_playlist": result.tracks_added_to_playlist,
                "mixes_added": result.mixes_added,
                "artists_checked": result.artists_checked,
                "errors": result.errors,
                "dry_run": result.dry_run,
            }
        _broadcast_sync_progress(
            "Sync complete!", result.artists_checked, result.artists_checked
        )
    except Exception as e:
        logger.exception("Discovery sync failed")
        with _sync_lock:
            _sync_jobs[job_id]["status"] = "failed"
            _sync_jobs[job_id]["error"] = str(e)
        _broadcast_sync_progress(f"Sync failed: {e}", 0, 0)


# === Endpoints ===


@router.post("/seed-artists", response_model=SeedArtistsResponse)
async def seed_artists(
    body: SeedArtistsRequest, background_tasks: BackgroundTasks
) -> SeedArtistsResponse:
    """Import artists from CSV and start background SC user ID resolution."""
    try:
        count = discovery_queries.seed_artists_from_csv(body.csv_path)
        background_tasks.add_task(_resolve_artists_background)
        return SeedArtistsResponse(artists_imported=count, resolution_started=True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"CSV not found: {body.csv_path}")
    except Exception as e:
        logger.exception("Failed to seed artists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artists")
async def list_artists(
    limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """List discovery artists with stats."""
    try:
        all_artists = discovery_queries.get_ranked_artists(include_not_due=True)
        total = len(all_artists)
        page = all_artists[offset : offset + limit]
        return {"artists": page, "total": total}
    except Exception as e:
        logger.exception("Failed to list artists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolution-status")
async def resolution_status() -> dict[str, int]:
    """Get artist resolution progress."""
    try:
        return discovery_queries.get_resolution_status()
    except Exception as e:
        logger.exception("Failed to get resolution status")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/last-sync")
async def last_sync() -> Optional[dict[str, Any]]:
    """Get the most recent sync run info."""
    try:
        return discovery_queries.get_last_sync()
    except Exception as e:
        logger.exception("Failed to get last sync")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=SyncJobResponse)
async def trigger_sync(body: SyncRequest, background_tasks: BackgroundTasks) -> SyncJobResponse:
    """Trigger a discovery sync in the background."""
    with _sync_lock:
        for job in _sync_jobs.values():
            if job["status"] == "running":
                raise HTTPException(status_code=409, detail="Sync already in progress")

    job_id = str(uuid.uuid4())[:8]
    with _sync_lock:
        _sync_jobs[job_id] = {
            "status": "running",
            "progress_message": "Starting sync...",
            "progress_current": 0,
            "progress_total": 0,
            "result": None,
            "error": None,
        }

    background_tasks.add_task(_run_sync_background, job_id, body.dry_run)
    return SyncJobResponse(job_id=job_id)


@router.get("/sync/status/{job_id}", response_model=SyncStatusResponse)
async def get_sync_status(job_id: str) -> SyncStatusResponse:
    """Get status of a sync job."""
    with _sync_lock:
        job = _sync_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return SyncStatusResponse(**job)


@router.post("/update-stats")
async def update_discovery_stats(body: UpdateStatsRequest) -> dict[str, str]:
    """Update discovery track statuses and recalculate artist stats."""
    try:
        if body.liked_sc_ids:
            discovery_queries.mark_tracks_liked(body.liked_sc_ids)
        if body.dismissed_sc_ids:
            discovery_queries.mark_tracks_dismissed(body.dismissed_sc_ids)
        if body.liked_sc_ids or body.dismissed_sc_ids:
            discovery_queries.recalculate_artist_stats()
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to update discovery stats")
        raise HTTPException(status_code=500, detail=str(e))
