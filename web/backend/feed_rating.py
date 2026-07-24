"""SC-side effects of feed +1 ratings: like + monthly playlist add.

Runs in FastAPI BackgroundTasks (per rating) and as a retry sweep inside the
feed worker for rows whose SC calls failed (429s etc.). Progress is tracked
per-row via sc_like_done / sc_playlist_done flags, giving at-least-once
semantics with no queue infrastructure.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    create_playlist,
    get_playlists,
    like_track,
)

from web.backend.queries import feed as feed_queries


def monthly_playlist_name(now: Optional[datetime] = None) -> str:
    """Monthly SC playlist naming convention, e.g. 'Jul 26'."""
    return (now or datetime.now(timezone.utc)).strftime("%b %y")


def get_or_create_monthly_sc_playlist(
    state: Any,
) -> tuple[Any, Optional[str], Optional[str]]:
    """Resolve this month's SC playlist id, creating the playlist if needed.

    Ladder: local cache (sc_monthly_playlists / imported playlists row) ->
    GET /me/playlists scan by name -> POST /me/playlists. Write-through cache.
    """
    name = monthly_playlist_name()
    cached = feed_queries.get_cached_monthly_playlist_id(name)
    if cached:
        return state, cached, None

    state, playlists = get_playlists(state)
    match = next((p for p in playlists if p.get("name") == name), None)
    if match:
        feed_queries.cache_monthly_playlist_id(name, match["id"])
        return state, match["id"], None

    state, playlist_id, err = create_playlist(
        state, name, description="Music Minion monthly feed picks"
    )
    if playlist_id:
        feed_queries.cache_monthly_playlist_id(name, playlist_id)
        logger.info(f"feed: created monthly SC playlist '{name}' ({playlist_id})")
    return state, playlist_id, err


def run_sc_like_flow(state: Any, upload: dict[str, Any]) -> Any:
    """Finish the SC side of a +1: like the track, add to monthly playlist.

    Each step flips its done-flag on success and only logs on failure — the
    worker sweep retries unfinished rows on the next feed sync.
    """
    upload_id = upload["id"]
    sc_track_id = upload["soundcloud_id"]

    if not upload.get("sc_like_done"):
        state, ok, err = like_track(state, sc_track_id)
        if ok:
            feed_queries.mark_sc_like_done(upload_id)
        else:
            logger.warning(f"feed: SC like failed for upload {upload_id}: {err}")

    if not upload.get("sc_playlist_done"):
        state, playlist_id, err = get_or_create_monthly_sc_playlist(state)
        if not playlist_id:
            logger.warning(f"feed: monthly playlist unavailable: {err}")
            return state
        state, ok, err = add_track_to_playlist(state, playlist_id, sc_track_id)
        if ok:
            feed_queries.mark_sc_playlist_done(upload_id)
        else:
            logger.warning(f"feed: playlist add failed for upload {upload_id}: {err}")
    return state


def sync_pending_feed_likes(state: Any) -> int:
    """Retry sweep: run the SC like flow for all unfinished +1 rows."""
    pending = feed_queries.get_unsynced_liked_uploads()
    for upload in pending:
        state = run_sc_like_flow(state, upload)
    if pending:
        logger.info(f"feed: retry sweep processed {len(pending)} pending +1 rows")
    return len(pending)
