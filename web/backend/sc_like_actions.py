"""Like / unlike a track on SoundCloud from anywhere (player heart).

The track's one durable 'like' job row (sc_feed_action_jobs, shared with the
feed's Keep) holds the DESIRED state: want_liked plus a generation bumped on
every request. The SC push worker runs the current desired state, and a job
that finishes after a newer request is re-queued instead of writing sc_likes
(feed_queries.settle_action). So the last request always wins, survives
restarts, and stays ordered with every other SC mutation (one writer thread).

Relative to Keep:
- Like records no verdict, adds nothing to the monthly playlist and trains
  nothing. On success sc_likes gets the like, exactly as for a Keep.
- Unlike overrides a pending Keep like; the Keep verdict itself is never
  touched. sc_likes is cleared only after SoundCloud confirms (404 counts).
- Un-keep cancels only Keep-created jobs (generation 0), never a request
  made from the player.
"""

from web.backend.queries import feed as feed_queries
from web.backend.sc_push_worker import enqueue_feed_action_drain


def request_like_state(soundcloud_id: str, liked: bool) -> dict:
    """Record the desired like state and wake the SC writer."""
    generation = feed_queries.set_like_intent(soundcloud_id, liked)
    enqueue_feed_action_drain()
    return {
        "soundcloud_id": soundcloud_id,
        "sc_liked": liked,
        "like_status": "pending",
        "generation": generation,
    }
