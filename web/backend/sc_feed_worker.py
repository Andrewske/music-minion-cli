"""Background SoundCloud feed-sync worker.

Daemon thread that reads SoundCloud's stream (/me/feed/tracks) every hour,
and once a day also sweeps followed artists one by one (adaptive cadence) to
backfill the activity SC throttles out of the stream.

A threading lock coordinates daemon runs with the manual
POST /api/soundcloud/feed-sync trigger.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.discovery_sync import sync_followings_reposts
from web.backend.feed_stream_sync import sync_from_stream
from web.backend.feed_uploads_sync import sync_followings_uploads
from web.backend.queries import discovery as discovery_queries
from web.backend.queries import feed as feed_queries
from web.backend.sc_push_worker import enqueue_feed_action_drain, recover_feed_actions
from web.backend.soundcloud_auth import get_web_provider_state

_feed_lock = threading.Lock()

TICK_SECONDS = 3600  # stream read every hour
SWEEP_INTERVAL = timedelta(hours=24)  # per-artist backfill sweep
# Full likes reconcile (drops likes undone on SoundCloud). 23h, not 24h, so
# hourly-tick drift doesn't push it a tick later every day.
LIKES_RECONCILE_INTERVAL = timedelta(hours=23)
# Followings sync (new follows into discovery_artists). 23h for the same reason.
FOLLOWINGS_SYNC_INTERVAL = timedelta(hours=23)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sync_sc_likes(provider_state: Any) -> int:
    """Incremental SoundCloud likes sync: import new liked tracks + like markers.

    Keeps sc_likes (the red heart everywhere) fresh without a manual
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


def _fetch_feed_locked(sweep: bool) -> dict[str, Any]:
    """Core feed sync. Caller must hold _feed_lock.

    Always reads SC's stream (seconds). With sweep=True it also runs the
    per-artist uploads + reposts sweep that backfills what the stream
    throttles (minutes to an hour; the daemon runs it daily).

    Returns summary dict: {events_added, uploads_added, duration_ms, total_events}.
    """
    start_ms = time.monotonic()
    _mark_running()
    logger.info(f"feed_sync_started (stream{' + sweep' if sweep else ''})")

    provider_state = get_web_provider_state()
    if provider_state is None:
        _set_sync_error("SC provider state unavailable (not authenticated)")
        raise RuntimeError("SC provider state unavailable")

    try:
        events_added, uploads_added = sync_from_stream(provider_state)
        if sweep:
            swept_events, swept_uploads = _run_sweep(provider_state)
            events_added += swept_events
            uploads_added += swept_uploads
    except Exception as exc:
        logger.exception("feed_sync_error during stream/sweep")
        _set_sync_error(str(exc))
        raise

    _after_ingest(provider_state)
    duration_ms = int((time.monotonic() - start_ms) * 1000)
    total_events = _write_success(events_added, duration_ms, sweep)
    logger.info(
        f"feed_sync_completed events_added={events_added} "
        f"uploads_added={uploads_added} sweep={sweep} duration_ms={duration_ms}"
    )
    return {
        "events_added": events_added,
        "uploads_added": uploads_added,
        "duration_ms": duration_ms,
        "total_events": total_events,
    }


def _run_sweep(provider_state: Any) -> tuple[int, int]:
    """Per-artist sweep of due artists; returns (repost_events, uploads) added."""
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
        # Uploads failure must not block the reposts sweep.
        logger.exception("feed_sync_error during sync_followings_uploads (continuing)")

    events_added, errors = sync_followings_reposts(provider_state)
    if errors:
        logger.warning(f"feed_sync: {len(errors)} artist-level errors (continuing)")
    return events_added, uploads_added


def _after_ingest(provider_state: Any) -> None:
    """Scoring, SC action drain, likes pull; none may fail the sync."""
    # Score newly ingested tracks with Jev before the feed shows them.
    try:
        from web.backend.jev_scorer import score_new_tracks

        score_new_tracks()
    except Exception:
        logger.exception("feed_sync_error during jev scoring (continuing)")

    # Wake the single SC mutation writer. Jobs are durable and remain queued
    # across provider outages and process restarts.
    enqueue_feed_action_drain()

    # Pull likes made outside the feed (SC app/web) into the local library so
    # sc_likes stays accurate.
    try:
        _sync_sc_likes(provider_state)
    except Exception:
        logger.exception("feed_sync_error during _sync_sc_likes (continuing)")


def _write_success(events_added: int, duration_ms: int, sweep: bool) -> int:
    """Record a successful run; returns total repost events."""
    now_iso = _now_utc().isoformat()
    try:
        with get_db_connection() as conn:
            total_events: int = conn.execute(
                "SELECT COUNT(*) FROM discovery_track_reposters"
            ).fetchone()[0]
            conn.execute(
                """
                UPDATE sc_feed_sync_state
                SET last_run_status = 'ok',
                    last_run_at = ?,
                    events_added_last_run = ?,
                    total_events = ?,
                    last_run_duration_ms = ?,
                    last_error = NULL,
                    sweep_last_run_at = CASE WHEN ? THEN ? ELSE sweep_last_run_at END
                WHERE id = 1
                """,
                (now_iso, events_added, total_events, duration_ms, sweep, now_iso),
            )
            conn.commit()
    except Exception as exc:
        logger.exception("feed_sync_error during final state write")
        _set_sync_error(str(exc))
        raise
    return total_events


def _sweep_due() -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT sweep_last_run_at FROM sc_feed_sync_state WHERE id = 1"
        ).fetchone()
    raw = row["sweep_last_run_at"] if row else None
    if not raw:
        return True
    try:
        return _now_utc() - datetime.fromisoformat(raw) >= SWEEP_INTERVAL
    except ValueError:
        return True


def _interval_elapsed(
    last_run_at: str | None, now: datetime, interval: timedelta
) -> bool:
    """Pure: True when last_run_at is missing, unparseable, or interval old."""
    if not last_run_at:
        return True
    try:
        last = datetime.fromisoformat(last_run_at)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= interval


def likes_reconcile_due(last_run_at: str | None, now: datetime) -> bool:
    """Pure: True when no complete reconcile has run in LIKES_RECONCILE_INTERVAL."""
    return _interval_elapsed(last_run_at, now, LIKES_RECONCILE_INTERVAL)


def _likes_reconcile_last_run_at() -> str | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT likes_reconcile_last_run_at FROM sc_feed_sync_state WHERE id = 1"
        ).fetchone()
    return row[0] if row else None


def _record_likes_reconcile(summary_json: str, complete: bool) -> None:
    """Store the summary; stamp last_run_at only for a complete fetch, so a
    failed fetch retries next tick instead of waiting a day."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE sc_feed_sync_state
            SET likes_reconcile_summary = ?,
                likes_reconcile_last_run_at = CASE WHEN ? THEN ?
                    ELSE likes_reconcile_last_run_at END
            WHERE id = 1
            """,
            (summary_json, complete, _now_utc().isoformat()),
        )
        conn.commit()


def _maybe_reconcile_sc_likes() -> None:
    """Nightly full likes reconcile from the daemon loop; never raises.

    The very first run (no last_run_at yet, i.e. right after deploy) is a dry
    run: it logs and stores what it would change, and deletes start the
    following night, leaving time to check it with `sc-likes-reconcile`.
    """
    from music_minion.domain.library.providers.soundcloud.likes_reconcile import (
        reconcile_for_provider,
        report_json,
    )

    try:
        last_run_at = _likes_reconcile_last_run_at()
        if not likes_reconcile_due(last_run_at, _now_utc()):
            return
        provider_state = get_web_provider_state()
        if provider_state is None:
            return
        report = reconcile_for_provider(provider_state, apply=last_run_at is not None)
        if report is not None:
            _record_likes_reconcile(report_json(report), report.complete)
    except Exception:
        logger.exception("feed_sync_error during sc likes reconcile (continuing)")


def _followings_last_synced_at() -> str | None:
    """When the last full followings sync wrote, or None if one is owed.

    A full sync stamps last_sc_sync_at on every row it leaves followed and
    unfollows the rest, so the oldest stamp among followed rows is the last
    full sync. A single follow from the app stamps one row and can't move
    it. Any unstamped followed row means no full sync since it appeared.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT CASE WHEN COUNT(*) = COUNT(last_sc_sync_at)
                        THEN MIN(last_sc_sync_at) END
            FROM discovery_artists WHERE is_following = 1
            """
        ).fetchone()
    return row[0] if row else None


def _maybe_sync_followings() -> None:
    """Nightly followings sync from the daemon loop; never raises.

    sync_followings aborts without writing on an empty or truncated fetch,
    which leaves the stamps alone, so the next tick retries.
    """
    from music_minion.domain.library.providers.soundcloud.api import get_followings
    from web.backend.queries.artists import sync_followings

    try:
        if not _interval_elapsed(
            _followings_last_synced_at(), _now_utc(), FOLLOWINGS_SYNC_INTERVAL
        ):
            return
        provider_state = get_web_provider_state()
        if provider_state is None:
            return
        _state, followings = get_followings(provider_state)
        with get_db_connection() as conn:
            if not sync_followings(conn, followings)["aborted"]:
                conn.commit()
    except Exception:  # noqa: BLE001 - the daemon loop must never die
        logger.exception("feed_sync_error during followings sync (continuing)")


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
                with _feed_lock:
                    _fetch_feed_locked(sweep=_sweep_due())
            except Exception:
                logger.exception("feed worker tick failed")
            with _feed_lock:
                _maybe_reconcile_sc_likes()
            with _feed_lock:
                _maybe_sync_followings()
            time.sleep(TICK_SECONDS)

    threading.Thread(target=_loop, daemon=True, name="sc_feed_worker").start()
    logger.info("feed_sync worker started")


def _mark_running() -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE sc_feed_sync_state SET last_run_status = 'running' WHERE id = 1"
        )
        conn.commit()


def _run_manual_sync_thread() -> None:
    """Run a feed sync the caller already holds _feed_lock for, then release it.

    Failures land in sc_feed_sync_state via _set_sync_error; the UI polls it.
    """
    threading.current_thread().silent_logging = True  # type: ignore[attr-defined]
    try:
        _fetch_feed_locked(sweep=False)
    except Exception:
        logger.exception("feed_sync: manual sync failed")
    finally:
        _feed_lock.release()


def run_manual_sync() -> dict[str, Any]:
    """Start a stream-only feed sync in the background.

    Called from POST /api/soundcloud/feed-sync. The stream read takes seconds,
    but Jev scoring and the likes pull can take minutes, so it still stays
    off the request path. Returns the status row (now 'running').
    """
    if not _feed_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429, detail="sync in progress, try again shortly"
        )
    try:
        _mark_running()
        threading.Thread(
            target=_run_manual_sync_thread, daemon=True, name="sc_feed_manual_sync"
        ).start()
    except Exception:
        _feed_lock.release()
        raise
    return get_sync_status()


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
                   metadata_backfill_completed_at, stream_checkpoint_at,
                   sweep_last_run_at
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
            "stream_checkpoint_at": None,
            "sweep_last_run_at": None,
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
        "stream_checkpoint_at": row["stream_checkpoint_at"],
        "sweep_last_run_at": row["sweep_last_run_at"],
    }
