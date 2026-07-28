"""Uploads sync for the SoundCloud feed page.

Fetches followed artists' own track uploads (not reposts) into
sc_artist_uploads, importing each as a streaming-only local track so the
feed is instantly playable. Runs inside the feed worker BEFORE the reposts
sync: the reposts sync owns the adaptive last_checked cadence, so this
module must never touch last_checked.
"""

import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import get_user_tracks

from web.backend.discovery_sync import _parse_sc_datetime
from web.backend.queries import discovery as discovery_queries

# Feed floor: uploads older than this are never ingested. Keeps the first
# backfill bounded and the tracks table from bloating with ancient uploads.
UPLOAD_CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _upload_cutoff() -> datetime:
    return UPLOAD_CUTOFF


def _get_known_upload_ids() -> set[str]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT soundcloud_id FROM sc_artist_uploads").fetchall()
    return {row["soundcloud_id"] for row in rows}


def _upgrade_artwork_url(url: Optional[str]) -> Optional[str]:
    """SC artwork defaults to -large (100x100); t500x500 exists for all tracks."""
    if not url:
        return None
    return url.replace("-large.", "-t500x500.")


def _fetch_artist_uploads(
    state: Any, artist: dict[str, Any], max_pages: int = 2
) -> tuple[Any, list[dict[str, Any]], Optional[str]]:
    """Fetch one artist's uploads with bounded 429 retry (2s/4s/8s)."""
    retries = 0
    backoff = 2
    while True:
        state, tracks, api_error = get_user_tracks(
            state, artist["soundcloud_user_id"], max_pages=max_pages
        )
        if api_error and "Rate limited" in api_error and retries < 3:
            retries += 1
            logger.warning(
                f"Rate limited fetching uploads for {artist['slug']}, "
                f"retry {retries}/3 after {backoff}s"
            )
            time.sleep(backoff)
            backoff *= 2
            continue
        return state, tracks, api_error


def _import_upload_to_library(conn: Any, track: dict[str, Any]) -> Optional[int]:
    """Insert SC track as streaming-only local track, return local track id."""
    sc_id = str(track["id"])
    conn.execute(
        """INSERT OR IGNORE INTO tracks
            (title, artist, duration, soundcloud_id, artwork_url, source)
        VALUES (?, ?, ?, ?, ?, 'soundcloud')""",
        (
            track.get("title", ""),
            track.get("user", {}).get("username", "Unknown"),
            (track.get("duration", 0) or 0) / 1000.0,
            sc_id,
            _upgrade_artwork_url(track.get("artwork_url")),
        ),
    )
    row = conn.execute(
        "SELECT id FROM tracks WHERE soundcloud_id = ?", (sc_id,)
    ).fetchone()
    if not row:
        logger.warning(f"feed_uploads: no local track after insert sc_id={sc_id}")
        return None
    return row["id"]


def _insert_uploads(records: list[dict[str, Any]]) -> int:
    """Import to library + insert sc_artist_uploads rows in one transaction."""
    if not records:
        return 0
    inserted = 0
    with get_db_connection() as conn:
        for rec in records:
            local_id = _import_upload_to_library(conn, rec["track"])
            cursor = conn.execute(
                """INSERT OR IGNORE INTO sc_artist_uploads
                    (discovery_artist_id, soundcloud_id, title, permalink_url,
                     artwork_url, duration_ms, uploaded_at, local_track_id, access)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec["artist_id"],
                    str(rec["track"]["id"]),
                    rec["track"].get("title", ""),
                    rec["track"].get("permalink_url"),
                    _upgrade_artwork_url(rec["track"].get("artwork_url")),
                    rec["track"].get("duration", 0) or 0,
                    rec["uploaded_at"],
                    local_id,
                    rec["track"].get("access"),
                ),
            )
            inserted += cursor.rowcount
        conn.commit()
    return inserted


def _update_known_access(tracks: list[dict[str, Any]]) -> None:
    """Refresh access tier for already-known uploads (populates legacy NULLs).

    SC can also flip a track between playable and preview (Go+ windows), so
    update on every sighting, not just when NULL.
    """
    updates = [
        (t.get("access"), str(t["id"]))
        for t in tracks
        if t.get("id") and t.get("access")
    ]
    if not updates:
        return
    with get_db_connection() as conn:
        conn.executemany(
            """UPDATE sc_artist_uploads SET access = ?1
            WHERE soundcloud_id = ?2 AND (access IS NULL OR access != ?1)""",
            updates,
        )
        conn.commit()


def _collect_new_uploads(
    tracks: list[dict[str, Any]], artist_id: int, known_ids: set[str]
) -> list[dict[str, Any]]:
    """Filter one artist's uploads to new-to-DB tracks within the age cutoff."""
    cutoff = _upload_cutoff()
    records = []
    for track in tracks:
        sc_id = str(track.get("id", ""))
        if not sc_id or sc_id in known_ids:
            continue
        uploaded = _parse_sc_datetime(track.get("created_at"))
        if uploaded is None or uploaded < cutoff:
            continue
        known_ids.add(sc_id)
        records.append(
            {
                "track": track,
                "artist_id": artist_id,
                "uploaded_at": uploaded.isoformat(),
            }
        )
    return records


def _write_uploads_sync_state(status: str, added: int, error: Optional[str]) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE sc_feed_sync_state
            SET uploads_last_run_at = ?, uploads_last_status = ?,
                uploads_last_error = ?, uploads_added_last_run = ?
            WHERE id = 1""",
            (datetime.now(timezone.utc).isoformat(), status, error, added),
        )
        conn.commit()


def sync_followings_uploads(
    state: Any,
    artists: list[dict[str, Any]],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    max_pages: int = 2,
) -> tuple[int, list[str]]:
    """Fetch new uploads from the given (pre-snapshotted) followed artists.

    Never touches discovery_artists.last_checked — the reposts sync that runs
    after this owns the adaptive cadence.

    Returns (uploads_added, errors).
    """
    if not artists:
        logger.info("sync_followings_uploads: no artists due for check")
        _write_uploads_sync_state("ok", 0, None)
        return 0, []

    known_ids = _get_known_upload_ids()
    errors: list[str] = []
    added = 0
    total = len(artists)

    # Insert per artist (not one big end-of-run transaction): a killed run —
    # e.g. uvicorn auto-reload mid-backfill — keeps its progress, and the
    # known_ids skip makes the next run resume where it stopped.
    for i, artist in enumerate(artists):
        if progress_callback:
            progress_callback(
                f"Uploads: {artist['slug']} ({i + 1}/{total})", i + 1, total
            )
        try:
            state, tracks, api_error = _fetch_artist_uploads(state, artist, max_pages)
            if api_error:
                errors.append(f"{artist['slug']}: {api_error}")
            added += _insert_uploads(
                _collect_new_uploads(tracks, artist["id"], known_ids)
            )
            _update_known_access(tracks)
        except Exception as exc:
            logger.exception(f"feed_uploads: failed for {artist['slug']}")
            errors.append(f"{artist['slug']}: {exc}")
        if i < total - 1:
            time.sleep(0.2)

    if added:
        discovery_queries.recalculate_artist_stats()
    _write_uploads_sync_state(
        "ok" if not errors else "partial", added, "; ".join(errors[:5]) or None
    )
    logger.info(
        f"sync_followings_uploads: checked {total} artists, {added} new uploads, "
        f"{len(errors)} errors"
    )
    return added, errors


def get_all_followed_artists() -> list[dict[str, Any]]:
    """All followed artists with an SC id, ignoring the due-check cadence."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM discovery_artists
            WHERE is_following = 1 AND soundcloud_user_id IS NOT NULL
            ORDER BY ranking IS NULL, ranking"""
        ).fetchall()
    return [dict(row) for row in rows]


def run_uploads_backfill(
    state: Any,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> tuple[int, list[str]]:
    """One-time backfill: sweep ALL followed artists for uploads since
    UPLOAD_CUTOFF (Jan 2026), one 200-track page per artist. ~0.5s/artist.

    The daily incremental sync only sees artists as they come due, so without
    this the feed starts empty and fills over ~30 days.
    """
    artists = get_all_followed_artists()
    logger.info(f"feed_uploads: backfill starting over {len(artists)} artists")
    _write_uploads_sync_state("running", 0, None)
    return sync_followings_uploads(state, artists, progress_callback, max_pages=1)
