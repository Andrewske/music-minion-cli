"""Background SoundCloud feed-sync worker.

Daemon thread that periodically runs sync_followings_reposts (lightweight
variant of discovery sync covering all followed artists, not just top-200)
and writes reposter rows into discovery_track_reposters with seen_at=now.

A threading lock coordinates daemon runs with the manual
POST /api/soundcloud/feed-sync trigger.
"""

import threading
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.discovery_sync import sync_followings_reposts
from web.backend.feed_uploads_sync import sync_followings_uploads
from web.backend.queries import discovery as discovery_queries
from web.backend.queries import feed as feed_queries
from web.backend.sc_push_worker import enqueue_feed_action_drain, recover_feed_actions
from web.backend.soundcloud_auth import get_web_provider_state

_feed_lock = threading.Lock()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sync_sc_likes(provider_state: Any) -> int:
    """Incremental SoundCloud likes sync: import new liked tracks + like markers.

    Keeps the feed's in_likes flag (red heart) fresh without a manual
    `library sync soundcloud likes` run. Returns like markers added.
    """
    from music_minion.core.database import batch_add_soundcloud_likes
    from music_minion.domain.library.import_tracks import batch_insert_provider_tracks
    from music_minion.domain.library.providers.soundcloud.api import (
        sync_library as sc_sync_library,
    )

    _state, provider_tracks = sc_sync_library(provider_state, incremental=True)
    if not provider_tracks:
        return 0

    stats = batch_insert_provider_tracks(provider_tracks, "soundcloud")

    # The provider's marker pass runs BEFORE the import above, so freshly
    # imported tracks have no like marker yet — insert them now.
    sc_ids = [track_id for track_id, _meta in provider_tracks]
    placeholders = ",".join("?" * len(sc_ids))
    with get_db_connection() as conn:
        rows = conn.execute(
            f"SELECT id FROM tracks WHERE source = 'soundcloud' AND soundcloud_id IN ({placeholders})",
            sc_ids,
        ).fetchall()
    markers_added = batch_add_soundcloud_likes([row[0] for row in rows])
    logger.info(
        f"feed_sync: likes sync imported {stats['created']} tracks, "
        f"{markers_added} new like markers"
    )
    return markers_added


def _reset_stale_running_status() -> None:
    """If last_run_status='running' from a prior process that was killed,
    reset to 'error' so the UI doesn't show a fake in-progress spinner."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE sc_feed_sync_state
                SET last_run_status = 'error',
                    last_error = 'interrupted by restart'
                WHERE id = 1 AND last_run_status = 'running'
                """
            )
            conn.execute(
                """
                UPDATE sc_feed_sync_state
                SET uploads_last_status = 'error',
                    uploads_last_error = 'interrupted by restart'
                WHERE id = 1 AND uploads_last_status = 'running'
                """
            )
            conn.execute(
                """
                UPDATE sc_feed_sync_state
                SET metadata_backfill_status = 'error',
                    metadata_backfill_last_error = 'interrupted by restart'
                WHERE id = 1 AND metadata_backfill_status = 'running'
                """
            )
            conn.commit()
    except Exception:
        logger.exception("feed_sync: failed to reset stale running status")


def _fetch_feed_locked() -> dict[str, Any]:
    """Core feed sync. Caller must hold _feed_lock.

    Returns summary dict: {events_added, duration_ms, total_events}.
    """
    start_ms = time.monotonic()

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE sc_feed_sync_state SET last_run_status = 'running' WHERE id = 1"
        )
        conn.commit()

    logger.info("feed_sync_started (uploads + reposts)")

    provider_state = get_web_provider_state()
    if provider_state is None:
        _set_sync_error("SC provider state unavailable (not authenticated)")
        raise RuntimeError("SC provider state unavailable")

    # Uploads have a dedicated per-artist checkpoint. They must not inherit the
    # adaptive repost cadence, which can stretch to 30 days for quiet artists.
    uploads_added = 0
    try:
        due_artists = discovery_queries.get_followed_artists_due_for_upload_check()
        uploads_added, upload_errors = sync_followings_uploads(
            provider_state, due_artists
        )
        if upload_errors:
            logger.warning(
                f"feed_sync: {len(upload_errors)} artist-level upload errors (continuing)"
            )
    except Exception:
        # Uploads failure must not block the reposts sync.
        logger.exception("feed_sync_error during sync_followings_uploads (continuing)")

    try:
        events_added, errors = sync_followings_reposts(provider_state)
    except Exception as exc:
        logger.exception("feed_sync_error during sync_followings_reposts")
        _set_sync_error(str(exc))
        raise

    # Wake the single SC mutation writer. Jobs are durable and remain queued
    # across provider outages and process restarts.
    enqueue_feed_action_drain()

    # Pull likes made outside the feed (SC app/web) into the local library so
    # the feed's in_likes flag stays accurate.
    try:
        _sync_sc_likes(provider_state)
    except Exception:
        logger.exception("feed_sync_error during _sync_sc_likes (continuing)")

    if errors:
        logger.warning(f"feed_sync: {len(errors)} artist-level errors (continuing)")

    try:
        with get_db_connection() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) FROM discovery_track_reposters"
            ).fetchone()
            total_events: int = total_row[0]
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            now_iso = _now_utc().isoformat()
            conn.execute(
                """
                UPDATE sc_feed_sync_state
                SET last_run_status = 'ok',
                    last_run_at = ?,
                    events_added_last_run = ?,
                    total_events = ?,
                    last_run_duration_ms = ?,
                    last_error = NULL
                WHERE id = 1
                """,
                (now_iso, events_added, total_events, duration_ms),
            )
            conn.commit()
    except Exception as exc:
        logger.exception("feed_sync_error during final state write")
        _set_sync_error(str(exc))
        raise

    logger.info(
        f"feed_sync_completed events_added={events_added} "
        f"uploads_added={uploads_added} duration_ms={duration_ms}"
    )
    return {
        "events_added": events_added,
        "uploads_added": uploads_added,
        "duration_ms": duration_ms,
        "total_events": total_events,
    }


def _set_sync_error(error: str) -> None:
    """Update sync state to error status."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE sc_feed_sync_state
                SET last_run_status = 'error', last_error = ?
                WHERE id = 1
                """,
                (error,),
            )
            conn.commit()
    except Exception:
        logger.exception("feed_sync: failed to write error state to DB")


def start_feed_worker() -> None:
    """Start the feed-sync daemon thread. Called from FastAPI startup."""

    _reset_stale_running_status()
    recovered = recover_feed_actions()
    if recovered:
        logger.info(f"feed_sync: recovered {recovered} interrupted SC actions")

    def _loop() -> None:
        threading.current_thread().silent_logging = True  # type: ignore[attr-defined]
        while True:
            try:
                with get_db_connection() as conn:
                    row = conn.execute(
                        "SELECT last_run_at, last_run_status FROM sc_feed_sync_state WHERE id = 1"
                    ).fetchone()

                last_run_at_raw: str | None = row["last_run_at"] if row else None
                last_status: str | None = row["last_run_status"] if row else None

                should_run = False
                if last_run_at_raw is None:
                    should_run = True
                else:
                    try:
                        last_run = datetime.fromisoformat(
                            last_run_at_raw.replace(" ", "T")
                        )
                        if last_run.tzinfo is None:
                            last_run = last_run.replace(tzinfo=timezone.utc)
                        age = (_now_utc() - last_run).total_seconds()
                        should_run = age > 86400  # 24h
                    except (ValueError, TypeError):
                        should_run = True

                if should_run:
                    _feed_lock.acquire(blocking=True)
                    try:
                        _fetch_feed_locked()
                        sleep_secs = 86400
                    except Exception:
                        sleep_secs = 3600
                    finally:
                        _feed_lock.release()
                else:
                    sleep_secs = 3600

                if last_status == "error":
                    sleep_secs = min(sleep_secs, 3600)

                time.sleep(sleep_secs)

            except Exception:
                logger.exception("feed worker tick failed")
                time.sleep(3600)

    threading.Thread(target=_loop, daemon=True, name="sc_feed_worker").start()
    logger.info("feed_sync worker started")


def run_manual_sync() -> dict[str, Any]:
    """Trigger an immediate feed sync. Called from POST /api/soundcloud/feed-sync."""
    if not _feed_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429, detail="sync in progress, try again shortly"
        )
    try:
        return _fetch_feed_locked()
    except HTTPException:
        raise
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 429:
            raise HTTPException(
                status_code=503, detail="SC rate-limited, retry in 5 minutes"
            )
        if status_code is not None and status_code >= 500:
            raise HTTPException(
                status_code=503, detail="SC upstream error, retry later"
            )
        raise HTTPException(status_code=503, detail=f"Feed sync failed: {exc}") from exc
    finally:
        _feed_lock.release()


def get_sync_status() -> dict[str, Any]:
    """Return the sc_feed_sync_state row plus durable SC action-job counts."""
    return {**_sync_state_row(), "action_jobs": feed_queries.get_action_counts()}


def _sync_state_row() -> dict[str, Any]:
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, last_run_at, last_run_status, last_error,
                   events_added_last_run, total_events, last_run_duration_ms,
                   uploads_last_run_at, uploads_last_status, uploads_last_error,
                   uploads_added_last_run, metadata_backfill_cursor,
                   metadata_backfill_status, metadata_backfill_last_error,
                   metadata_backfill_completed_at
            FROM sc_feed_sync_state
            WHERE id = 1
            """
        ).fetchone()

    if row is None:
        return {
            "last_run_at": None,
            "last_run_status": None,
            "last_error": None,
            "events_added_last_run": 0,
            "total_events": 0,
            "last_run_duration_ms": None,
            "uploads_last_run_at": None,
            "uploads_last_status": None,
            "uploads_last_error": None,
            "uploads_added_last_run": 0,
            "metadata_backfill_cursor": 0,
            "metadata_backfill_status": None,
            "metadata_backfill_last_error": None,
            "metadata_backfill_completed_at": None,
        }

    return {
        "last_run_at": row["last_run_at"],
        "last_run_status": row["last_run_status"],
        "last_error": row["last_error"],
        "events_added_last_run": row["events_added_last_run"],
        "total_events": row["total_events"],
        "last_run_duration_ms": row["last_run_duration_ms"],
        "uploads_last_run_at": row["uploads_last_run_at"],
        "uploads_last_status": row["uploads_last_status"],
        "uploads_last_error": row["uploads_last_error"],
        "uploads_added_last_run": row["uploads_added_last_run"],
        "metadata_backfill_cursor": row["metadata_backfill_cursor"],
        "metadata_backfill_status": row["metadata_backfill_status"],
        "metadata_backfill_last_error": row["metadata_backfill_last_error"],
        "metadata_backfill_completed_at": row["metadata_backfill_completed_at"],
    }
