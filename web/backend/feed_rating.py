"""Durable SoundCloud side effects for canonical feed keep decisions."""

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from music_minion.core.local_time import configured_feed_timezone, month_label
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    create_playlist,
    get_playlists,
    like_track,
)
from web.backend.queries import feed as feed_queries


def monthly_playlist_name(now: Optional[datetime] = None) -> str:
    """Monthly SC playlist name ('Jul 26') in the configured feed timezone."""
    instant = now or datetime.now(timezone.utc)
    return month_label(instant, configured_feed_timezone())


def get_or_create_monthly_sc_playlist(
    state: Any, name: Optional[str] = None
) -> tuple[Any, Optional[str], Optional[str]]:
    """Resolve/create one named monthly playlist using a write-through cache."""
    name = name or monthly_playlist_name()
    cached = feed_queries.get_cached_monthly_playlist_id(name)
    if cached:
        return state, cached, None

    state, playlists = get_playlists(state)
    match = next(
        (playlist for playlist in playlists if playlist.get("name") == name), None
    )
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


def _already_complete(err: Optional[str]) -> bool:
    """SoundCloud reports duplicates as errors; for an idempotent job that is success."""
    if not err:
        return False
    lowered = err.lower()
    return "already liked" in lowered or "already in playlist" in lowered


def process_one_pending_action(state: Any) -> tuple[Any, bool]:
    """Claim and execute one durable job. Called only by the SC push worker."""
    job = feed_queries.claim_due_action()
    if job is None:
        return state, False

    try:
        if job["action_type"] == "like":
            state, success, err = like_track(state, job["soundcloud_id"])
        else:
            state, playlist_id, err = get_or_create_monthly_sc_playlist(
                state, job["target_key"]
            )
            if playlist_id:
                state, success, err = add_track_to_playlist(
                    state, playlist_id, job["soundcloud_id"]
                )
            else:
                success = False

        if success or _already_complete(err):
            feed_queries.complete_action(job["id"])
        else:
            feed_queries.fail_action(
                job["id"],
                err or "SoundCloud operation failed",
                job["attempt_count"],
                job["max_attempts"],
            )
    except Exception as exc:
        logger.exception(f"feed action {job['id']} failed")
        feed_queries.fail_action(
            job["id"], str(exc), job["attempt_count"], job["max_attempts"]
        )
    return state, True


def drain_pending_feed_actions(state: Any) -> int:
    """Drain all currently-due jobs in the serialized SC writer thread."""
    processed = 0
    while True:
        state, claimed = process_one_pending_action(state)
        if not claimed:
            break
        processed += 1
    if processed:
        logger.info(f"feed: processed {processed} durable SoundCloud actions")
    return processed
