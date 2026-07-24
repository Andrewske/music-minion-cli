"""SoundCloud uploads feed API endpoints.

Paginated feed of followed artists' newest uploads plus the -1/0/+1 rating
flow. The +1 SC side (like + monthly playlist) runs in BackgroundTasks so
the response returns as soon as the DB write lands.
"""

import threading
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from web.backend.feed_rating import run_sc_like_flow
from web.backend.feed_uploads_sync import run_uploads_backfill
from web.backend.queries import discovery as discovery_queries
from web.backend.queries import feed as feed_queries
from web.backend.soundcloud_auth import get_web_provider_state

router = APIRouter(prefix="/api/feed", tags=["feed"])

_RATING_TO_STATUS: dict[int, str] = {-1: "dismissed", 0: "hidden", 1: "liked"}


class RateRequest(BaseModel):
    value: Literal[-1, 0, 1]


def _encode_cursor(item: dict[str, Any]) -> str:
    return f"{item['uploaded_at']}|{item['id']}"


def _decode_cursor(cursor: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    if not cursor:
        return None, None
    try:
        uploaded_at, raw_id = cursor.rsplit("|", 1)
        return uploaded_at, int(raw_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {cursor!r}")


@router.get("")
def get_feed(
    limit: int = Query(default=30, ge=1, le=100),
    cursor: Optional[str] = None,
    top200: bool = False,
    in_library: bool = False,
) -> dict[str, Any]:
    cursor_uploaded_at, cursor_id = _decode_cursor(cursor)
    items = feed_queries.get_feed_page(
        limit=limit,
        cursor_uploaded_at=cursor_uploaded_at,
        cursor_id=cursor_id,
        top200=top200,
        in_library=in_library,
    )
    next_cursor = _encode_cursor(items[-1]) if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


def _run_sc_like_background(upload: dict[str, Any]) -> None:
    state = get_web_provider_state()
    if state is None:
        logger.warning("feed: +1 SC side skipped — provider not authenticated")
        return
    try:
        run_sc_like_flow(state, upload)
    except Exception:
        logger.exception(f"feed: +1 SC flow failed for upload {upload['id']}")


@router.post("/backfill")
def start_backfill() -> dict[str, Any]:
    """Kick off the one-time uploads backfill (all followed artists, uploads
    since Jan 2026) in a background thread. Poll
    GET /api/soundcloud/feed-sync/status (uploads_* fields) for progress —
    uploads_last_status flips 'running' -> 'ok'/'partial'.
    """
    from web.backend.sc_feed_worker import _feed_lock

    state = get_web_provider_state()
    if state is None:
        raise HTTPException(status_code=503, detail="SoundCloud not authenticated")
    if not _feed_lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A feed sync is already running")

    def _run() -> None:
        threading.current_thread().silent_logging = True  # type: ignore[attr-defined]
        try:
            run_uploads_backfill(state)
        except Exception:
            logger.exception("feed: uploads backfill failed")
        finally:
            _feed_lock.release()

    threading.Thread(target=_run, daemon=True, name="feed_uploads_backfill").start()
    return {"started": True}


@router.post("/{upload_id}/rate")
def rate_upload(
    upload_id: int, body: RateRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    status = _RATING_TO_STATUS[body.value]
    updated = feed_queries.set_upload_status(upload_id, status)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Upload {upload_id} not found")

    if body.value != 0:
        # -1 and +1 both feed the artist hit_rate; 0 is penalty-free.
        discovery_queries.recalculate_artist_stats(updated["discovery_artist_id"])
    if body.value == 1:
        background_tasks.add_task(_run_sc_like_background, updated)

    return {"id": upload_id, "status": status}
