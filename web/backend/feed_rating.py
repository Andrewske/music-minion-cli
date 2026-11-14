"""Durable SoundCloud side effects for canonical feed keep decisions."""

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from music_minion.core.database import delete_sc_like, upsert_sc_likes
from music_minion.core.local_time import configured_feed_timezone, month_label
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    create_playlist,
    get_playlists,
    like_track,
    unlike_track,
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


def _already_complete(job: dict[str, Any], err: str | None) -> bool:
    """SoundCloud reports no-op mutations as errors; for an idempotent job that is success.

    Like: "already liked" / "already in playlist". Unlike: a 404 means the
    like isn't there, which is the goal state.
    """
    if not err:
        return False
    lowered = err.lower()
    if _is_unlike(job):
        return "404" in lowered
    return "already liked" in lowered or "already in playlist" in lowered


def _is_unlike(job: dict[str, Any]) -> bool:
    return job["action_type"] == "like" and not job.get("want_liked", 1)


def _execute_action(state: Any, job: dict[str, Any]) -> tuple[Any, bool, str | None]:
    """Run one job against SoundCloud: like, unlike, or monthly playlist add."""
    if job["action_type"] == "like":
        mutate = unlike_track if _is_unlike(job) else like_track
        return mutate(state, job["soundcloud_id"])
    state, playlist_id, err = get_or_create_monthly_sc_playlist(
        state, job["target_key"]
    )
    if not playlist_id:
        return state, False, err
    return add_track_to_playlist(state, playlist_id, job["soundcloud_id"])


def _record_like_state(job: dict[str, Any]) -> None:
    """Mirror a confirmed like/unlike into sc_likes ('mm_keep' = liked by MM:
    a Keep or the player heart, which share this job row)."""
    if job["action_type"] != "like":
        return
    if _is_unlike(job):
        delete_sc_like(job["soundcloud_id"])
    else:
        upsert_sc_likes([job["soundcloud_id"]], "mm_keep", liked_now=True)


def process_one_pending_action(state: Any) -> tuple[Any, bool]:
    """Claim and execute one durable job. Called only by the SC push worker.

    sc_likes is written only when the job's generation is still current, so a
    like/unlike that a newer request superseded never lands. Every job runs
    on this one thread, so a superseding job always runs after this one.
    """
    job = feed_queries.claim_due_action()
    if job is None:
        return state, False
    try:
        state, success, err = _execute_action(state, job)
        done = success or _already_complete(job, err)
        if feed_queries.settle_action(job, done, None if done else err) and done:
            _record_like_state(job)
    except Exception as exc:
        logger.exception(f"feed action {job['id']} failed")
        feed_queries.settle_action(job, False, str(exc))
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
