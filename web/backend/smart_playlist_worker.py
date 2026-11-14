"""Background refresh of stale smart playlists.

DB triggers mark smart playlists stale on any track/emoji change, from any
writer (the web app, the host ingest, raw SQL from scripts). This daemon
thread refreshes the stale ones every TICK_SECONDS so those changes show up
without a read. Fresh playlists cost one SELECT per tick.
"""

import sqlite3
import threading
import time

from loguru import logger

from music_minion.domain.playlists.smart_refresh import refresh_stale_smart_playlists

TICK_SECONDS = 30

_started = False
_start_lock = threading.Lock()


def run_tick() -> int:
    """Refresh every stale smart playlist once. Returns how many changed."""
    try:
        results = refresh_stale_smart_playlists()
    except sqlite3.Error:
        logger.exception("smart playlist refresh tick failed")
        return 0
    return sum(1 for r in results if r.changed)


def _loop() -> None:
    threading.current_thread().silent_logging = True  # type: ignore[attr-defined]
    while True:
        run_tick()
        time.sleep(TICK_SECONDS)


def start_smart_playlist_worker() -> None:
    """Start the refresh thread once per process. Called from FastAPI startup."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, daemon=True, name="smart_playlist_refresh").start()
    logger.info("smart playlist refresh worker started")
