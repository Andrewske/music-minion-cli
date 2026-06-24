"""Background SoundCloud push worker.

Fire-and-forget queue that processes SC API calls in a daemon thread,
keeping bucket assignment fast (local DB only) while SC sync happens async.
Single thread serializes all SC mutations to avoid race conditions.
"""

import queue
import threading
import time
from typing import Callable, NamedTuple

import requests
from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    remove_track_from_playlist,
    reorder_playlist,
)
from web.backend.soundcloud_auth import get_web_provider_state

# Seconds to wait before the single bounded retry of a transient failure.
RETRY_DELAY_SECONDS = 30

# Substrings in api error strings that indicate a PERMANENT failure (no retry).
# The api returns (state, success, err) tuples; these err strings are not
# resolvable by retrying (auth/validation/not-found/already-present).
_PERMANENT_ERR_MARKERS = (
    "not authenticated",
    "authentication failed",
    "token expired",
    "not found",
    "already in playlist",
    "not in playlist",
    "http 400",
    "http 401",
    "http 403",
    "http 404",
    "http 422",
)


class SCPushAdd(NamedTuple):
    playlist_id: int
    track_id: int


class SCPushRemove(NamedTuple):
    playlist_id: int
    track_id: int


class SCPushBulkSync(NamedTuple):
    playlist_id: int


_queue: queue.Queue = queue.Queue()
_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()


def _is_transient_error(err: str | None) -> bool:
    """Classify an api error STRING as transient (retryable) vs permanent.

    Permanent: auth/validation/not-found/already-present errors (see markers).
    Transient: network errors, timeouts, rate limits, and 5xx HTTP statuses.
    """
    if err is None:
        return False
    lowered = err.lower()
    if any(marker in lowered for marker in _PERMANENT_ERR_MARKERS):
        return False
    return True


def _is_transient_exception(exc: BaseException) -> bool:
    """Classify a raised exception as transient (retryable) vs permanent.

    Transient: timeouts, connection errors, and 5xx HTTP errors. 4xx HTTP
    errors are permanent; any other exception is treated as permanent.
    """
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        return response is not None and response.status_code >= 500
    return False


def _run_with_retry(handler: Callable[[], tuple[bool, str | None]], label: str) -> None:
    """Invoke a handler once; on a TRANSIENT failure retry exactly once.

    The handler returns (success, err). A falsy success with a transient err,
    or a raised transient exception, triggers a single ~30s-delayed retry.
    Bounded to two attempts total (no backoff, no loop). Runs in the daemon
    worker thread, so the sleep only serializes SC mutations.
    """
    for attempt in (1, 2):
        transient = _attempt_handler(handler, label, attempt)
        if not transient:
            return
        if attempt == 1:
            logger.warning(f"SC push {label}: transient failure, retrying in {RETRY_DELAY_SECONDS}s")
            time.sleep(RETRY_DELAY_SECONDS)
    logger.warning(f"SC push {label}: dropped after retry")


def _attempt_handler(
    handler: Callable[[], tuple[bool, str | None]], label: str, attempt: int
) -> bool:
    """Run handler once. Return True iff it failed transiently (should retry)."""
    try:
        success, err = handler()
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
        if _is_transient_exception(exc):
            return True
        logger.warning(f"SC push {label} permanent error (attempt {attempt}): {exc}")
        return False
    if success:
        return False
    if _is_transient_error(err):
        logger.warning(f"SC push {label} transient error (attempt {attempt}): {err}")
        return True
    logger.warning(f"SC push {label} permanent error (attempt {attempt}): {err}")
    return False


def _ensure_worker() -> None:
    """Lazily start the daemon worker thread on first enqueue."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
        _worker_thread.start()
        logger.info("SC push worker thread started")


def enqueue_sc_push_add(playlist_id: int, track_id: int) -> None:
    """Enqueue a single track add to SoundCloud playlist."""
    _ensure_worker()
    _queue.put(SCPushAdd(playlist_id, track_id))


def enqueue_sc_push_remove(playlist_id: int, track_id: int) -> None:
    """Enqueue a single track remove from SoundCloud playlist."""
    _ensure_worker()
    _queue.put(SCPushRemove(playlist_id, track_id))


def enqueue_sc_push_bulk_sync(playlist_id: int) -> None:
    """Enqueue a full playlist sync to SoundCloud."""
    _ensure_worker()
    _queue.put(SCPushBulkSync(playlist_id))


def _worker_loop() -> None:
    """Process SC push tasks from the queue. Runs as daemon thread."""
    threading.current_thread().silent_logging = True
    while True:
        try:
            task = _queue.get()
            try:
                _dispatch(task)
            except Exception:
                logger.exception("SC push worker error")
            finally:
                _queue.task_done()
        except Exception:
            logger.exception("SC push worker fatal error")


def _dispatch(task: object) -> None:
    """Route a queued task to its handler, wrapped in the single-retry helper."""
    if isinstance(task, SCPushAdd):
        _run_with_retry(lambda: _handle_add(task.playlist_id, task.track_id), "add")
    elif isinstance(task, SCPushRemove):
        _run_with_retry(lambda: _handle_remove(task.playlist_id, task.track_id), "remove")
    elif isinstance(task, SCPushBulkSync):
        _run_with_retry(lambda: _handle_bulk_sync(task.playlist_id), "bulk_sync")


def _handle_add(playlist_id: int, track_id: int) -> tuple[bool, str | None]:
    """Push a single track add to SoundCloud. Returns (success, err)."""
    sc_playlist_id, sc_track_id = _resolve_sc_ids(playlist_id, track_id)
    if sc_playlist_id is None or sc_track_id is None:
        return True, None  # Not an SC track / playlist; nothing to push
    state = get_web_provider_state()
    if state is None:
        return True, None  # No SC auth; nothing to retry
    _, success, err = add_track_to_playlist(state, sc_playlist_id, sc_track_id)
    if success:
        logger.info(f"SC push: added track {sc_track_id} to playlist {sc_playlist_id}")
    return success, err


def _handle_remove(playlist_id: int, track_id: int) -> tuple[bool, str | None]:
    """Push a single track remove from SoundCloud. Returns (success, err)."""
    sc_playlist_id, sc_track_id = _resolve_sc_ids(playlist_id, track_id)
    if sc_playlist_id is None or sc_track_id is None:
        return True, None
    state = get_web_provider_state()
    if state is None:
        return True, None
    _, success, err = remove_track_from_playlist(state, sc_playlist_id, sc_track_id)
    if success:
        logger.info(f"SC push: removed track {sc_track_id} from playlist {sc_playlist_id}")
    return success, err


def _handle_bulk_sync(playlist_id: int) -> tuple[bool, str | None]:
    """Push full playlist track list to SoundCloud. Returns (success, err)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        if not row or not row["soundcloud_playlist_id"]:
            return True, None  # Not an SC playlist; nothing to push
        sc_playlist_id = row["soundcloud_playlist_id"]

        tracks_cursor = conn.execute(
            """
            SELECT t.soundcloud_id
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            WHERE pt.playlist_id = ? AND t.soundcloud_id IS NOT NULL
            ORDER BY pt.position ASC
            """,
            (playlist_id,),
        )
        sc_track_ids = [r["soundcloud_id"] for r in tracks_cursor.fetchall()]

    if not sc_track_ids:
        return True, None  # No SC tracks to sync
    state = get_web_provider_state()
    if state is None:
        return True, None  # No SC auth; nothing to retry
    _, success, err = reorder_playlist(state, sc_playlist_id, sc_track_ids)
    if success:
        logger.info(f"SC push: synced {len(sc_track_ids)} tracks to playlist {sc_playlist_id}")
    return success, err


def _resolve_sc_ids(
    playlist_id: int, track_id: int
) -> tuple[str | None, str | None]:
    """Look up SoundCloud IDs for a playlist and track from the DB."""
    with get_db_connection() as conn:
        track_cursor = conn.execute(
            "SELECT soundcloud_id FROM tracks WHERE id = ?",
            (track_id,),
        )
        track_row = track_cursor.fetchone()
        sc_track_id = track_row["soundcloud_id"] if track_row else None

        playlist_cursor = conn.execute(
            "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,),
        )
        playlist_row = playlist_cursor.fetchone()
        sc_playlist_id = playlist_row["soundcloud_playlist_id"] if playlist_row else None

    return sc_playlist_id, sc_track_id
