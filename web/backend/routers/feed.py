"""Deduplicated SoundCloud releases/reposts feed API."""

import base64
import binascii
import json
import threading
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from web.backend.feed_rating import monthly_playlist_name
from web.backend.feed_uploads_sync import run_uploads_backfill
from web.backend.queries import discovery as discovery_queries
from web.backend.queries import feed as feed_queries
from web.backend.queries import feed_filters as filter_queries
from web.backend.sc_push_worker import enqueue_feed_action_drain
from web.backend.soundcloud_auth import get_web_provider_state

router = APIRouter(prefix="/api/feed", tags=["feed"])

# Legacy numeric ratings. 0 used to mean 'hide', which can no longer be
# written, so it is rejected rather than silently becoming a training label.
_RATING_TO_DECISION = {-1: "nope", 1: "keep"}
_DECISION_TO_STATUS = {"keep": "liked", "not_quite": "dismissed", "nope": "dismissed"}


class RateRequest(BaseModel):
    """Either `decision` (canonical) or legacy `value` (-1/+1) must be set.

    `listen_seconds` / `max_position_ms` come from the in-app player: time
    actually played before the verdict and the furthest position reached.
    """

    decision: Literal["keep", "not_quite", "nope"] | None = None
    value: Literal[-1, 1] | None = None
    surface: str = "web_feed"
    model_version: str | None = None
    feature_snapshot: dict[str, Any] | None = None
    listen_seconds: float | None = Field(default=None, ge=0)
    max_position_ms: int | None = Field(default=None, ge=0)


class NoteRequest(BaseModel):
    note: str = Field(max_length=feed_queries.MAX_NOTE_LENGTH)


class FlagRequest(BaseModel):
    """Not for feed: a reason chip plus an optional note (shared notes table)."""

    reason: Literal["live_mix", "podcast", "other"]
    note: str | None = Field(default=None, max_length=feed_queries.MAX_NOTE_LENGTH)


def _resolve_decision(body: RateRequest) -> str:
    if body.decision is not None:
        return body.decision
    if body.value is not None:
        return _RATING_TO_DECISION[body.value]
    raise HTTPException(status_code=422, detail="decision or value is required")


def _encode_reviewed_cursor(item: dict[str, Any]) -> str:
    payload = json.dumps([item["decided_key"], item["decision_id"]]).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_reviewed_cursor(
    cursor: str | None,
) -> tuple[str | None, int | None]:
    if not cursor:
        return None, None
    try:
        padding = "=" * (-len(cursor) % 4)
        key, decision_id = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if not isinstance(key, str) or not isinstance(decision_id, int):
            raise TypeError("cursor values have the wrong types")
        return key, decision_id
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid reviewed cursor")


def _encode_cursor(item: dict[str, Any], sort: str) -> str:
    if sort == "score":
        # Unscored tracks share the sentinel used for SQL ordering (-1.0).
        score = (
            item["keep_probability"] if item["keep_probability"] is not None else -1.0
        )
        values: list[Any] = ["score", score, item["soundcloud_id"]]
    else:
        values = [item["event_at"], item["soundcloud_id"]]
    payload = json.dumps(values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(
    cursor: str | None, sort: str
) -> tuple[str | None, str | None, float | None]:
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
    cursor: str | None = None,
    source: Literal["all", "releases", "reposts"] = "all",
    max_rank: int | None = Query(default=None, ge=1),
    in_library: bool = False,
    top200: bool = False,
    sort: Literal["event_at", "score"] = "event_at",
    min_score: float | None = Query(default=None, ge=0.0, le=1.0),
) -> dict[str, Any]:
    cursor_event_at, cursor_soundcloud_id, cursor_score = _decode_cursor(cursor, sort)
    items = feed_queries.get_feed_page(
        limit=limit,
        cursor_event_at=cursor_event_at,
        cursor_soundcloud_id=cursor_soundcloud_id,
        source=source,
        max_rank=max_rank,
        in_library=in_library,
        top200=top200,
        sort=sort,
        min_score=min_score,
        cursor_score=cursor_score,
    )
    next_cursor = _encode_cursor(items[-1], sort) if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.get("/reviewed")
def get_reviewed(
    decision: Literal["keep", "not_quite", "nope", "hide"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> dict[str, Any]:
    """Current decisions newest first; `hide` lists legacy rows only."""
    cursor_key, cursor_id = _decode_reviewed_cursor(cursor)
    items = feed_queries.get_reviewed_page(decision, limit, cursor_key, cursor_id)
    next_cursor = _encode_reviewed_cursor(items[-1]) if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}


@router.put("/{soundcloud_id}/note")
def put_track_note(soundcloud_id: str, body: NoteRequest) -> dict[str, Any]:
    """Upsert the per-track note; an empty note deletes it."""
    if not feed_queries.track_is_known(soundcloud_id):
        raise HTTPException(
            status_code=404, detail=f"SoundCloud track {soundcloud_id} not found"
        )
    stored = feed_queries.set_track_note(soundcloud_id, body.note)
    return {
        "soundcloud_id": soundcloud_id,
        "note": stored["note"] if stored else None,
        "updated_at": stored["updated_at"] if stored else None,
    }


def _require_known_track(soundcloud_id: str) -> None:
    if not feed_queries.track_is_known(soundcloud_id):
        raise HTTPException(
            status_code=404, detail=f"SoundCloud track {soundcloud_id} not found"
        )


@router.post("/{soundcloud_id}/flag")
def flag_track(
    soundcloud_id: str, body: FlagRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Hide a track as not for feed. Not a verdict: no decision row is written.

    A flagged track stops counting toward artist stats, so they're refreshed.
    """
    _require_known_track(soundcloud_id)
    flag = filter_queries.flag_track(soundcloud_id, body.reason, body.note)
    background_tasks.add_task(filter_queries.refresh_artist_stats_for, [soundcloud_id])
    return {"soundcloud_id": soundcloud_id, "flag": flag}


@router.delete("/{soundcloud_id}/flag")
def unflag_track(
    soundcloud_id: str, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Undo a user flag or rescue a rule/agent flag; the track returns to the feed."""
    result = filter_queries.unflag_track(soundcloud_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"SoundCloud track {soundcloud_id} is not flagged"
        )
    background_tasks.add_task(filter_queries.refresh_artist_stats_for, [soundcloud_id])
    return {
        "soundcloud_id": soundcloud_id,
        "source": result["source"],
        "removed": result["removed"],
        "rescued_at": result.get("rescued_at"),
    }


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


def _refresh_contributor_stats(soundcloud_id: str) -> None:
    """Refresh stats for every artist a decision trains (uploader + reposters).

    Runs after the response: it costs ~2s on the pi and nothing in the
    response depends on it.
    """
    try:
        artist_ids = feed_queries.get_contributing_artist_ids(soundcloud_id)
        if artist_ids:
            discovery_queries.recalculate_artist_stats(artist_ids)
    except Exception:
        logger.exception(f"Artist stats refresh failed after rating {soundcloud_id}")


@router.post("/{soundcloud_id}/rate")
def rate_track(
    soundcloud_id: str, body: RateRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    soundcloud_id = _resolve_compat_identifier(soundcloud_id)
    decision = _resolve_decision(body)
    updated = feed_queries.record_decision(
        soundcloud_id,
        decision,
        body.surface,
        body.model_version,
        body.feature_snapshot,
        listen=feed_queries.ListenStats(body.listen_seconds, body.max_position_ms),
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

    # A re-rating can remove as well as add a training label.
    background_tasks.add_task(_refresh_contributor_stats, soundcloud_id)
    return {
        "soundcloud_id": soundcloud_id,
        "current_decision": decision,
        "status": _DECISION_TO_STATUS[decision],
        "decided_at": updated["decided_at"],
        "local_track_id": local_track_id,
        "action_state": feed_queries.get_action_state(soundcloud_id),
    }


class MaterializeRequest(BaseModel):
    soundcloud_ids: list[str]


@router.post("/materialize")
def materialize_tracks(body: MaterializeRequest) -> dict[str, Any]:
    """Create library rows for feed items so a play queue can keep feed order.

    Unknown ids are left out of the response rather than failing the batch.
    """
    materialized = feed_queries.materialize_feed_tracks(body.soundcloud_ids)
    return {
        "items": [
            {"soundcloud_id": soundcloud_id, "local_track_id": local_track_id}
            for soundcloud_id, local_track_id in materialized.items()
        ]
    }


@router.get("/{soundcloud_id}/decisions")
def get_decision_history(soundcloud_id: str) -> dict[str, Any]:
    soundcloud_id = _resolve_compat_identifier(soundcloud_id)
    return {
        "soundcloud_id": soundcloud_id,
        "history": feed_queries.get_decision_history(soundcloud_id),
    }


@router.post("/actions/reconcile")
def reconcile_actions(soundcloud_id: str | None = None) -> dict[str, Any]:
    reset = feed_queries.reconcile_actions(soundcloud_id)
    enqueue_feed_action_drain()
    return {"reset": reset}
