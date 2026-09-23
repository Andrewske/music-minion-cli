"""Deduplicated SoundCloud releases/reposts feed API."""

import base64
import binascii
import json
import threading
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from web.backend.feed_rating import monthly_playlist_name
from web.backend.feed_uploads_sync import run_uploads_backfill
from web.backend.queries import discovery as discovery_queries
from web.backend.queries import feed as feed_queries
from web.backend.sc_push_worker import enqueue_feed_action_drain
from web.backend.soundcloud_auth import get_web_provider_state

router = APIRouter(prefix="/api/feed", tags=["feed"])

_RATING_TO_DECISION = {-1: "nope", 0: "hide", 1: "keep"}


class RateRequest(BaseModel):
    """Either `decision` (canonical) or legacy `value` (-1/0/+1) must be set."""

    decision: Optional[Literal["keep", "nope", "hide"]] = None
    value: Optional[Literal[-1, 0, 1]] = None
    surface: str = "web_feed"
    model_version: Optional[str] = None
    feature_snapshot: Optional[dict[str, Any]] = None


def _resolve_decision(body: RateRequest) -> str:
    if body.decision is not None:
        return body.decision
    if body.value is not None:
        return _RATING_TO_DECISION[body.value]
    raise HTTPException(status_code=422, detail="decision or value is required")


def _encode_cursor(item: dict[str, Any], sort: str) -> str:
    if sort == "score":
        # Unscored tracks share the sentinel used for SQL ordering (-1.0).
        score = item["keep_probability"] if item["keep_probability"] is not None else -1.0
        values: list[Any] = ["score", score, item["soundcloud_id"]]
    else:
        values = [item["event_at"], item["soundcloud_id"]]
    payload = json.dumps(values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(
    cursor: Optional[str], sort: str
) -> tuple[Optional[str], Optional[str], Optional[float]]:
    """Returns (event_at, soundcloud_id, score); rejects cross-sort cursors."""
    if not cursor:
        return None, None, None
    try:
        padding = "=" * (-len(cursor) % 4)
        values = json.loads(base64.urlsafe_b64decode(cursor + padding).decode())
        if len(values) == 3 and values[0] == "score":
            if sort != "score" or not isinstance(values[2], str):
                raise ValueError("cursor does not match the requested sort")
            return None, values[2], float(values[1])
        event_at, soundcloud_id = values
        if sort != "event_at":
            raise ValueError("cursor does not match the requested sort")
        if not isinstance(event_at, str) or not isinstance(soundcloud_id, str):
            raise ValueError("cursor values must be strings")
        return event_at, soundcloud_id, None
    except (
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        raise HTTPException(status_code=400, detail="Invalid feed cursor")


@router.get("")
def get_feed(
    limit: int = Query(default=30, ge=1, le=100),
    cursor: Optional[str] = None,
    source: Literal["all", "releases", "reposts"] = "all",
    max_rank: Optional[int] = Query(default=None, ge=1),
    in_library: bool = False,
    show_hidden: bool = False,
    top200: bool = False,
    sort: Literal["event_at", "score"] = "event_at",
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
) -> dict[str, Any]:
    cursor_event_at, cursor_soundcloud_id, cursor_score = _decode_cursor(cursor, sort)
    items = feed_queries.get_feed_page(
        limit=limit,
        cursor_event_at=cursor_event_at,
        cursor_soundcloud_id=cursor_soundcloud_id,
        source=source,
        max_rank=max_rank,
        in_library=in_library,
        show_hidden=show_hidden,
        top200=top200,
        sort=sort,
        min_score=min_score,
        cursor_score=cursor_score,
    )
    next_cursor = _encode_cursor(items[-1], sort) if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/backfill")
def start_backfill() -> dict[str, Any]:
    """Kick off the one-time uploads backfill in a background thread."""
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


def _resolve_compat_identifier(identifier: str) -> str:
    """Accept a legacy numeric upload-row id during the API transition."""
    if feed_queries.get_feed_track(identifier) is not None:
        return identifier
    if identifier.isdigit():
        upload = feed_queries.get_upload(int(identifier))
        if upload:
            return upload["soundcloud_id"]
    return identifier


@router.post("/{soundcloud_id}/rate")
def rate_track(soundcloud_id: str, body: RateRequest) -> dict[str, Any]:
    soundcloud_id = _resolve_compat_identifier(soundcloud_id)
    decision = _resolve_decision(body)
    updated = feed_queries.record_decision(
        soundcloud_id,
        decision,
        body.surface,
        body.model_version,
        body.feature_snapshot,
    )
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"SoundCloud track {soundcloud_id} not found"
        )

    local_track_id = None
    if decision == "keep":
        local_track_id = feed_queries.materialize_feed_track(soundcloud_id)
        feed_queries.enqueue_keep_actions(soundcloud_id, monthly_playlist_name())
        enqueue_feed_action_drain()
    else:
        feed_queries.cancel_pending_actions(soundcloud_id)

    # A re-rating can remove as well as add a training label, so refresh every
    # artist who contributed this track (uploader + reposters).
    for artist_id in feed_queries.get_contributing_artist_ids(soundcloud_id):
        discovery_queries.recalculate_artist_stats(artist_id)
    return {
        "soundcloud_id": soundcloud_id,
        "current_decision": decision,
        "status": {"keep": "liked", "nope": "dismissed", "hide": "hidden"}[decision],
        "decided_at": updated["decided_at"],
        "local_track_id": local_track_id,
        "action_state": feed_queries.get_action_state(soundcloud_id),
    }


@router.post("/{soundcloud_id}/materialize")
def materialize_track(soundcloud_id: str) -> dict[str, Any]:
    soundcloud_id = _resolve_compat_identifier(soundcloud_id)
    local_track_id = feed_queries.materialize_feed_track(soundcloud_id)
    if local_track_id is None:
        raise HTTPException(
            status_code=404, detail=f"SoundCloud track {soundcloud_id} not found"
        )
    return {"soundcloud_id": soundcloud_id, "local_track_id": local_track_id}


@router.get("/{soundcloud_id}/decisions")
def get_decision_history(soundcloud_id: str) -> dict[str, Any]:
    soundcloud_id = _resolve_compat_identifier(soundcloud_id)
    return {
        "soundcloud_id": soundcloud_id,
        "history": feed_queries.get_decision_history(soundcloud_id),
    }


@router.post("/actions/reconcile")
def reconcile_actions(soundcloud_id: Optional[str] = None) -> dict[str, Any]:
    reset = feed_queries.reconcile_actions(soundcloud_id)
    enqueue_feed_action_drain()
    return {"reset": reset}
