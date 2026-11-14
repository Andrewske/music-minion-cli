"""Like / unlike a track on SoundCloud from anywhere (player heart).

Semantics, relative to the feed's Keep verdict:

- Like reuses Keep's durable like job (sc_feed_action_jobs, action 'like').
  It records no verdict, adds nothing to the monthly playlist and trains
  nothing. On success the job writes sc_likes, exactly as for a Keep.
- Unlike cancels any not-yet-done like job (Keep's included), then, when SC
  may hold the like, unlikes on the SC push worker. sc_likes is cleared only
  after SoundCloud confirms. The Keep verdict itself is never touched.

Both run every SoundCloud call on the single SC writer thread, so a like
and an unlike sent in quick succession reach SoundCloud in order.
"""

from music_minion.core.database import get_db_connection
from web.backend.queries import feed as feed_queries
from web.backend.sc_likes import liked_soundcloud_ids
from web.backend.sc_push_worker import enqueue_feed_action_drain, enqueue_sc_unlike


def request_like(soundcloud_id: str) -> dict:
    """Queue (or re-arm) the like job and wake the SC writer.

    Always re-arms, even when sc_likes already has the track: an unlike may
    still be waiting on the writer, and the like must land after it.
    """
    feed_queries.enqueue_like_action(soundcloud_id)
    enqueue_feed_action_drain()
    return {"soundcloud_id": soundcloud_id, "sc_liked": True, "like_status": "pending"}


def request_unlike(soundcloud_id: str) -> dict:
    """Cancel a pending like; unlike on SC when it may already be liked there."""
    cancelled = feed_queries.cancel_pending_like(soundcloud_id)
    with get_db_connection() as conn:
        liked = bool(liked_soundcloud_ids(conn, [soundcloud_id]))
    running = feed_queries.like_job_status(soundcloud_id) == "running"
    if liked or running:
        enqueue_sc_unlike(soundcloud_id)
    return {
        "soundcloud_id": soundcloud_id,
        "sc_liked": False,
        "cancelled_pending_like": cancelled > 0,
        "unlike_queued": liked or running,
    }
