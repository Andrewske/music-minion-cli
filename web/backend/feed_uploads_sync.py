"""Uploads sync for the SoundCloud feed page.

Fetches followed artists' own track uploads (not reposts) into
sc_artist_uploads, importing each as a streaming-only local track so the
feed is instantly playable. Runs inside the feed worker BEFORE the reposts
sync, with its own uploads_last_checked checkpoint and hourly cadence.
"""

import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import get_user_tracks

from web.backend.queries import discovery as discovery_queries
from web.backend.soundcloud_metadata import (
    parse_soundcloud_datetime,
    track_metadata,
)

# Feed floor: uploads older than this are never ingested. Keeps the first
# backfill bounded and the tracks table from bloating with ancient uploads.
UPLOAD_CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _upload_cutoff() -> datetime:
    return UPLOAD_CUTOFF


def _get_known_upload_ids() -> set[str]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT soundcloud_id FROM sc_artist_uploads").fetchall()
    return {row["soundcloud_id"] for row in rows}


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
    """Upsert an owned SC streaming track and return its local track id."""
    sc_id = str(track["id"])
    metadata = track_metadata(track)
    conn.execute(
        """INSERT OR IGNORE INTO tracks
            (title, artist, duration, soundcloud_id, artwork_url, source_url,
             genre, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'soundcloud')""",
        (
            metadata["title"],
            metadata["artist_name"],
            metadata["duration_ms"] / 1000.0,
            sc_id,
            metadata["artwork_url"],
            metadata["permalink_url"],
            metadata["genre"],
        ),
    )
    # Only update provider-owned rows; never overwrite metadata on a user's
    # local-file track that happens to carry the same SoundCloud ID.
    conn.execute(
        """UPDATE tracks
        SET title = COALESCE(NULLIF(?, ''), title),
            artist = COALESCE(NULLIF(?, ''), artist),
            duration = CASE WHEN ? > 0 THEN ? ELSE duration END,
            artwork_url = COALESCE(?, artwork_url),
            source_url = COALESCE(?, source_url),
            genre = COALESCE(NULLIF(?, ''), genre),
            updated_at = CURRENT_TIMESTAMP
        WHERE soundcloud_id = ? AND source = 'soundcloud'""",
        (
            metadata["title"],
            metadata["artist_name"],
            metadata["duration_ms"],
            metadata["duration_ms"] / 1000.0,
            metadata["artwork_url"],
            metadata["permalink_url"],
            metadata["genre"],
            sc_id,
        ),
    )
    row = conn.execute(
        """SELECT id FROM tracks
        WHERE soundcloud_id = ?
        ORDER BY source = 'soundcloud' DESC
        LIMIT 1""",
        (sc_id,),
    ).fetchone()
    if not row:
        logger.warning(f"feed_uploads: no local track after insert sc_id={sc_id}")
        return None
    return row["id"]


def _insert_uploads(records: list[dict[str, Any]]) -> int:
    """Import to library + upsert sc_artist_uploads rows in one transaction."""
    if not records:
        return 0
    inserted = 0
    with get_db_connection() as conn:
        sc_ids = [str(rec["track"]["id"]) for rec in records]
        placeholders = ",".join("?" * len(sc_ids))
        existing = {
            row["soundcloud_id"]
            for row in conn.execute(
                f"SELECT soundcloud_id FROM sc_artist_uploads "
                f"WHERE soundcloud_id IN ({placeholders})",
                sc_ids,
            ).fetchall()
        }
        for rec in records:
            metadata = track_metadata(rec["track"])
            local_id = _import_upload_to_library(conn, rec["track"])
            conn.execute(
                """INSERT INTO sc_artist_uploads
                    (discovery_artist_id, soundcloud_id, title, permalink_url,
                     artwork_url, duration_ms, uploaded_at, local_track_id, access,
                     event_type, uploader_soundcloud_id, genre, released_at,
                     metadata_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'upload', ?, ?, ?, ?)
                ON CONFLICT(soundcloud_id) DO UPDATE SET
                    discovery_artist_id = excluded.discovery_artist_id,
                    title = COALESCE(NULLIF(excluded.title, ''), sc_artist_uploads.title),
                    permalink_url = COALESCE(
                        excluded.permalink_url, sc_artist_uploads.permalink_url
                    ),
                    artwork_url = COALESCE(
                        excluded.artwork_url, sc_artist_uploads.artwork_url
                    ),
                    duration_ms = CASE
                        WHEN excluded.duration_ms > 0 THEN excluded.duration_ms
                        ELSE sc_artist_uploads.duration_ms
                    END,
                    uploaded_at = COALESCE(
                        excluded.uploaded_at, sc_artist_uploads.uploaded_at
                    ),
                    local_track_id = COALESCE(
                        excluded.local_track_id, sc_artist_uploads.local_track_id
                    ),
                    access = COALESCE(excluded.access, sc_artist_uploads.access),
                    event_type = 'upload',
                    uploader_soundcloud_id = COALESCE(
                        excluded.uploader_soundcloud_id,
                        sc_artist_uploads.uploader_soundcloud_id
                    ),
                    genre = COALESCE(
                        NULLIF(excluded.genre, ''), sc_artist_uploads.genre
                    ),
                    released_at = COALESCE(
                        excluded.released_at, sc_artist_uploads.released_at
                    ),
                    metadata_updated_at = excluded.metadata_updated_at""",
                (
                    rec["artist_id"],
                    metadata["soundcloud_id"],
                    metadata["title"],
                    metadata["permalink_url"],
                    metadata["artwork_url"],
                    metadata["duration_ms"],
                    rec["uploaded_at"],
                    local_id,
                    metadata["access"],
                    metadata["uploader_soundcloud_id"],
                    metadata["genre"],
                    metadata["released_at"],
                    metadata["metadata_updated_at"],
                ),
            )
            if metadata["soundcloud_id"] not in existing:
                inserted += 1
                existing.add(metadata["soundcloud_id"])
        conn.commit()
    return inserted


def _collect_uploads(
    tracks: list[dict[str, Any]], artist_id: int, known_ids: set[str]
) -> list[dict[str, Any]]:
    """Keep known rows for metadata updates and bound only brand-new uploads."""
    cutoff = _upload_cutoff()
    records = []
    for track in tracks:
        sc_id = str(track.get("id", ""))
        if not sc_id:
            continue
        uploaded = parse_soundcloud_datetime(track.get("created_at"))
        if uploaded is None:
            continue
        if sc_id not in known_ids and uploaded < cutoff:
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

    Advances discovery_artists.uploads_last_checked after each successful API
    fetch and never touches the repost-only last_checked field.

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

    # Insert and checkpoint per artist (not one big end-of-run transaction):
    # a killed run keeps completed artists and rows, while idempotent upserts
    # make replaying the interrupted artist safe.
    for i, artist in enumerate(artists):
        if progress_callback:
            progress_callback(
                f"Uploads: {artist['slug']} ({i + 1}/{total})", i + 1, total
            )
        try:
            state, tracks, api_error = _fetch_artist_uploads(state, artist, max_pages)
            if api_error:
                errors.append(f"{artist['slug']}: {api_error}")
            added += _insert_uploads(_collect_uploads(tracks, artist["id"], known_ids))
            if api_error is None:
                discovery_queries.update_artist_uploads_last_checked(artist["id"])
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

    The normal incremental sync uses the independent upload cadence; this
    explicit sweep remains useful for a fresh installation or manual repair.
    """
    artists = get_all_followed_artists()
    logger.info(f"feed_uploads: backfill starting over {len(artists)} artists")
    _write_uploads_sync_state("running", 0, None)
    return sync_followings_uploads(state, artists, progress_callback, max_pages=1)
