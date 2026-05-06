"""Background SoundCloud push worker.

Fire-and-forget queue that processes SC API calls in a daemon thread,
keeping bucket assignment fast (local DB only) while SC sync happens async.
Single thread serializes all SC mutations to avoid race conditions.
"""

import queue
import threading
from typing import NamedTuple

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist,
    remove_track_from_playlist,
    reorder_playlist,
)
from web.backend.soundcloud_auth import get_web_provider_state


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
                if isinstance(task, SCPushAdd):
                    _handle_add(task.playlist_id, task.track_id)
                elif isinstance(task, SCPushRemove):
                    _handle_remove(task.playlist_id, task.track_id)
                elif isinstance(task, SCPushBulkSync):
                    _handle_bulk_sync(task.playlist_id)
            except Exception:
                logger.exception("SC push worker error")
            finally:
                _queue.task_done()
        except Exception:
            logger.exception("SC push worker fatal error")


def _handle_add(playlist_id: int, track_id: int) -> None:
    """Push a single track add to SoundCloud."""
    sc_playlist_id, sc_track_id = _resolve_sc_ids(playlist_id, track_id)
    if sc_playlist_id is None or sc_track_id is None:
        return
    state = get_web_provider_state()
    if state is None:
        return
    _, success, err = add_track_to_playlist(state, sc_playlist_id, sc_track_id)
    if success:
        logger.info(f"SC push: added track {sc_track_id} to playlist {sc_playlist_id}")
    else:
        logger.warning(f"SC push add failed: {err}")


def _handle_remove(playlist_id: int, track_id: int) -> None:
    """Push a single track remove to SoundCloud."""
    sc_playlist_id, sc_track_id = _resolve_sc_ids(playlist_id, track_id)
    if sc_playlist_id is None or sc_track_id is None:
        return
    state = get_web_provider_state()
    if state is None:
        return
    _, success, err = remove_track_from_playlist(state, sc_playlist_id, sc_track_id)
    if success:
        logger.info(f"SC push: removed track {sc_track_id} from playlist {sc_playlist_id}")
    else:
        logger.warning(f"SC push remove failed: {err}")


def _handle_bulk_sync(playlist_id: int) -> None:
    """Push full playlist track list to SoundCloud (reorder/sync)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT soundcloud_playlist_id FROM playlists WHERE id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        if not row or not row["soundcloud_playlist_id"]:
            return
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
        return
    state = get_web_provider_state()
    if state is None:
        return
    _, success, err = reorder_playlist(state, sc_playlist_id, sc_track_ids)
    if success:
        logger.info(f"SC push: synced {len(sc_track_ids)} tracks to playlist {sc_playlist_id}")
    else:
        logger.warning(f"SC push bulk sync failed: {err}")


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
