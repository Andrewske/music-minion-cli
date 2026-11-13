"""Unfollow a followed discovery artist on SoundCloud, then locally.

Shared by POST /api/artists/{id}/unfollow and the unfollow suggestions page.
Blocking (SC request + SQLite), so callers must be plain `def` endpoints.
"""

from typing import Any

import requests
from fastapi import HTTPException
from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import unfollow_user
from web.backend.queries.artists import (
    mark_artist_unfollowed,
    remove_artist_tracks_from_reposts_playlist,
)
from web.backend.soundcloud_auth import get_web_provider_state

# Errors that will hit every following request too: stop a batch on these.
SERVICE_WIDE_STATUSES = frozenset({401, 503})


def _sc_user_id(discovery_artist_id: int) -> str | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT soundcloud_user_id FROM discovery_artists WHERE id = ?",
            (discovery_artist_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Artist {discovery_artist_id} not found"
        )
    return row["soundcloud_user_id"]


def _sc_unfollow(discovery_artist_id: int, sc_user_id: str) -> None:
    """SC DELETE; 5xx / timeout / connection error -> 503, no token -> 401."""
    state = get_web_provider_state()
    if not state or not state.authenticated:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")
    where = f"artist {discovery_artist_id} (sc_id={sc_user_id})"
    try:
        unfollow_user(state, sc_user_id)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        logger.exception(f"SC unfollow failed for {where}: HTTP {status}")
        if status == 0:
            raise HTTPException(
                status_code=401, detail="SoundCloud token expired, re-authenticate"
            )
        raise HTTPException(
            status_code=503, detail=f"SoundCloud returned {status}, try again"
        )
    except requests.Timeout:
        logger.exception(f"SC unfollow timeout for {where}")
        raise HTTPException(status_code=503, detail="SoundCloud timed out, try again")
    except requests.ConnectionError:
        logger.exception(f"SC connection error for {where}")
        raise HTTPException(status_code=503, detail="Could not reach SoundCloud")


def unfollow_discovery_artist(discovery_artist_id: int) -> dict[str, Any]:
    """Unfollow on SC (when the artist has an SC id), then mark it locally.

    SC must succeed before any local change. SC 403/404 count as success
    (already unfollowed). Raises HTTPException: 404 unknown artist, 401 not
    authenticated, 503 SC down or failing.
    """
    sc_user_id = _sc_user_id(discovery_artist_id)
    if sc_user_id:
        _sc_unfollow(discovery_artist_id, sc_user_id)
    with get_db_connection() as conn:
        feed_events_deleted = mark_artist_unfollowed(conn, discovery_artist_id)
        reposts_removed = remove_artist_tracks_from_reposts_playlist(
            conn, discovery_artist_id
        )
        conn.commit()
    return {
        "unfollowed": True,
        "sc_called": bool(sc_user_id),
        "feed_events_deleted": feed_events_deleted,
        "reposts_removed": reposts_removed,
    }


def _batch_result(discovery_artist_id: int) -> dict[str, Any]:
    try:
        unfollow_discovery_artist(discovery_artist_id)
        return {"id": discovery_artist_id, "ok": True}
    except HTTPException as exc:
        return {
            "id": discovery_artist_id,
            "ok": False,
            "status": exc.status_code,
            "error": exc.detail,
        }


def unfollow_batch(ids: list[int]) -> dict[str, Any]:
    """Unfollow in order, stopping at the first service-wide SC error.

    Per-artist failures (e.g. unknown id) are recorded and skipped. Ids
    after a stop are left out of results, so the caller can retry them.
    """
    results: list[dict[str, Any]] = []
    for discovery_artist_id in ids:
        result = _batch_result(discovery_artist_id)
        results.append(result)
        if not result["ok"] and result["status"] in SERVICE_WIDE_STATUSES:
            return {"results": results, "stopped": True, "error": result["error"]}
    return {"results": results, "stopped": False, "error": None}
