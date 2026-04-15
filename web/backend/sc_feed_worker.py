"""Background SoundCloud feed-sync worker.

Daemon thread that periodically pulls /me/activities (track-repost events)
into sc_feed_events. A threading lock coordinates daemon runs with the
manual POST /api/soundcloud/feed-sync trigger.
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.soundcloud_auth import get_web_provider_state

_feed_lock = threading.Lock()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _upsert_discovery_artist(
    conn: Any, user: dict[str, Any]
) -> int | None:
    """Upsert a discovery_artists row by soundcloud_user_id.

    Creates the row if missing (ranking=MAX+1, is_following unchanged).
    Returns the discovery_artist_id, or None if user has no id.
    """
    sc_id = str(user.get("id", "")).strip()
    if not sc_id:
        return None

    row = conn.execute(
        "SELECT id FROM discovery_artists WHERE soundcloud_user_id = ?",
        (sc_id,),
    ).fetchone()

    if row:
        return row["id"]

    # New artist — derive fields and insert at end of ranking
    username = user.get("permalink", "") or user.get("username", "") or sc_id
    display_name = user.get("full_name", "") or user.get("username", "") or username
    avatar_url: str | None = user.get("avatar_url")
    follower_count: int | None = user.get("followers_count")
    slug = username.lower().strip()

    existing_slug = conn.execute(
        "SELECT id FROM discovery_artists WHERE slug = ?", (slug,)
    ).fetchone()
    if existing_slug:
        slug = f"{slug}-{sc_id}"

    max_rank_row = conn.execute(
        "SELECT COALESCE(MAX(ranking), 0) FROM discovery_artists"
    ).fetchone()
    next_rank: int = max_rank_row[0] + 1

    cursor = conn.execute(
        """
        INSERT INTO discovery_artists
            (soundcloud_user_id, slug, display_name, ranking,
             avatar_url, follower_count, is_following, last_sc_sync_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """,
        (sc_id, slug, display_name, next_rank, avatar_url, follower_count),
    )
    logger.info(f"feed_sync: created new discovery_artist {display_name!r} (sc_id={sc_id})")
    return cursor.lastrowid


def _write_events(
    conn: Any, events: list[dict[str, Any]], now_iso: str
) -> int:
    """Write a batch of feed events to the DB. Returns count of new rows inserted."""
    added = 0
    for event in events:
        user = event.get("user") or {}
        track = event.get("track") or event.get("origin") or {}

        if not user or not track:
            logger.warning(f"feed_sync: skipping event with missing user/track: {list(event.keys())}")
            continue

        artist_id = _upsert_discovery_artist(conn, user)
        if artist_id is None:
            logger.warning("feed_sync: skipping event — reposter has no SC id")
            continue

        track_sc_id = str(track.get("id", "")).strip()
        if not track_sc_id:
            logger.warning("feed_sync: skipping event — track has no id")
            continue

        track_title: str | None = track.get("title")
        track_user = track.get("user") or {}
        track_artist_name: str | None = (
            track_user.get("full_name") or track_user.get("username")
        )

        repost_at_raw: str | None = event.get("created_at")
        sc_reposted_at: str | None = None
        if repost_at_raw:
            try:
                cleaned = repost_at_raw.replace("/", "-").replace(" +0000", "+00:00")
                sc_reposted_at = datetime.fromisoformat(cleaned).isoformat()
            except (ValueError, TypeError):
                sc_reposted_at = None

        raw_json = json.dumps(event)

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO sc_feed_events
                (discovery_artist_id, track_sc_id, track_title,
                 track_artist_name, reposted_at, seen_at, raw_json)
            VALUES (?, ?, ?, ?, COALESCE(?, ?), ?, ?)
            """,
            (
                artist_id,
                track_sc_id,
                track_title,
                track_artist_name,
                sc_reposted_at,
                now_iso,
                now_iso,
                raw_json,
            ),
        )
        if cursor.rowcount:
            added += 1
    return added


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

        state_row = conn.execute(
            "SELECT last_run_at FROM sc_feed_sync_state WHERE id = 1"
        ).fetchone()

    last_run_at_raw: str | None = state_row["last_run_at"] if state_row else None
    since: datetime | None = None

    if last_run_at_raw:
        try:
            since = datetime.fromisoformat(last_run_at_raw.replace(" ", "T"))
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            logger.warning(f"feed_sync: could not parse last_run_at={last_run_at_raw!r}, using 48h cap")
            since = None

    if since is None:
        since = _now_utc() - timedelta(hours=24)

    logger.info(f"feed_sync_started since={since.isoformat()}")

    provider_state = get_web_provider_state()
    if provider_state is None:
        _set_sync_error("SC provider state unavailable (not authenticated)")
        raise RuntimeError("SC provider state unavailable")

    from music_minion.domain.library.providers.soundcloud.api import get_stream

    now = _now_utc()
    now_iso = now.isoformat()
    events_added = 0

    def on_page(page_events: list[dict[str, Any]]) -> None:
        """Per-page commit: write the batch and commit immediately."""
        nonlocal events_added
        try:
            with get_db_connection() as conn:
                page_added = _write_events(conn, page_events, now_iso)
                conn.commit()
        except Exception:
            logger.exception("feed_sync: failed to commit page batch")
            raise
        events_added += page_added
        logger.info(f"feed_sync page commit: +{page_added} new (cumulative={events_added})")

    try:
        get_stream(provider_state, since=since, on_page=on_page)
    except Exception as exc:
        logger.exception("feed_sync_error during get_stream")
        _set_sync_error(str(exc))
        raise

    try:
        with get_db_connection() as conn:
            total_events_row = conn.execute(
                "SELECT COUNT(*) FROM sc_feed_events"
            ).fetchone()
            total_events: int = total_events_row[0]
            duration_ms = int((time.monotonic() - start_ms) * 1000)
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
        f"feed_sync_completed events_added={events_added} duration_ms={duration_ms}"
    )
    return {
        "events_added": events_added,
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
                    # Re-check in 1h; next 24h tick handled by next iteration
                    sleep_secs = 3600

                # Shorten sleep if last run errored
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
        raise HTTPException(status_code=429, detail="sync in progress, try again shortly")
    try:
        return _fetch_feed_locked()
    except HTTPException:
        raise
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 429:
            raise HTTPException(status_code=503, detail="SC rate-limited, retry in 5 minutes")
        if status_code is not None and status_code >= 500:
            raise HTTPException(status_code=503, detail="SC upstream error, retry later")
        raise HTTPException(status_code=503, detail=f"Feed sync failed: {exc}") from exc
    finally:
        _feed_lock.release()


def get_sync_status() -> dict[str, Any]:
    """Return the sc_feed_sync_state row as a dict."""
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, last_run_at, last_run_status, last_error,
                   events_added_last_run, total_events, last_run_duration_ms
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
        }

    return {
        "last_run_at": row["last_run_at"],
        "last_run_status": row["last_run_status"],
        "last_error": row["last_error"],
        "events_added_last_run": row["events_added_last_run"],
        "total_events": row["total_events"],
        "last_run_duration_ms": row["last_run_duration_ms"],
    }
