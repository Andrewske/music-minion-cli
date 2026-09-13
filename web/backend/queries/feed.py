"""Query functions for the SoundCloud uploads feed page."""

from typing import Any, Optional

from loguru import logger

from music_minion.core.database import get_db_connection

# Canonical sc_artist_uploads.status values (mirrored as CHECK in v59):
#   - 'visible':   unrated, shown in feed
#   - 'hidden':    0 rating — hidden from feed, no artist penalty
#   - 'dismissed': -1 rating — hidden + counts against artist hit_rate
#   - 'liked':     +1 rating — stays in feed highlighted; SC like + monthly playlist
FEED_STATUSES: tuple[str, ...] = ("visible", "hidden", "dismissed", "liked")


def _validate_status(status: str) -> None:
    if status not in FEED_STATUSES:
        raise ValueError(
            f"Invalid sc_artist_uploads.status {status!r}; valid values are {FEED_STATUSES}"
        )


def _row_to_feed_item(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "local_track_id": row["local_track_id"],
        "soundcloud_id": row["soundcloud_id"],
        "title": row["title"],
        "artwork_url": row["artwork_url"],
        "permalink_url": row["permalink_url"],
        "duration_ms": row["duration_ms"],
        "uploaded_at": row["uploaded_at"],
        "status": row["status"],
        "in_likes": bool(row["in_likes"]),
        "in_playlists": bool(row["in_playlists"]),
        "artist": {
            "id": row["artist_id"],
            "display_name": row["display_name"],
            "slug": row["artist_slug"],
            "avatar_url": row["avatar_url"],
            "in_top_200": bool(row["in_top_200"]),
            "in_library": bool(row["artist_in_library"]),
        },
    }


def get_feed_page(
    limit: int = 30,
    cursor_uploaded_at: Optional[str] = None,
    cursor_id: Optional[int] = None,
    top200: bool = False,
    in_library: bool = False,
    show_hidden: bool = False,
) -> list[dict[str, Any]]:
    """Fetch one feed page, newest uploads first, keyset-paginated.

    Cursor is the (uploaded_at, id) of the last row of the previous page —
    immune to new rows being inserted by the sync mid-scroll. Excludes
    hidden/dismissed unless show_hidden. in_library requires an actually
    saved local file (local_path NOT NULL), not just a streaming import row.
    Only currently-followed artists appear: unfollowing removes an artist's
    uploads from the feed instantly (rows are kept, so re-following restores).
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.soundcloud_id, u.title, u.permalink_url, u.artwork_url,
                   u.duration_ms, u.uploaded_at, u.local_track_id, u.status,
                   da.id AS artist_id, da.display_name, da.slug AS artist_slug,
                   da.avatar_url, da.in_top_200,
                   EXISTS(
                       SELECT 1 FROM tracks t
                       WHERE t.artist_normalized = da.display_name_normalized
                         AND t.local_path IS NOT NULL
                   ) AS artist_in_library,
                   EXISTS(
                       SELECT 1 FROM tracks t
                       JOIN ratings r ON r.track_id = t.id
                         AND r.rating_type = 'like' AND r.source = 'soundcloud'
                       WHERE t.source = 'soundcloud'
                         AND t.soundcloud_id = u.soundcloud_id
                   ) AS in_likes,
                   EXISTS(
                       SELECT 1 FROM tracks t
                       JOIN playlist_tracks pt ON pt.track_id = t.id
                       WHERE t.source = 'soundcloud'
                         AND t.soundcloud_id = u.soundcloud_id
                   ) AS in_playlists
            FROM sc_artist_uploads u
            JOIN discovery_artists da ON da.id = u.discovery_artist_id
            WHERE da.is_following = 1
              AND (? = 1 OR u.status IN ('visible', 'liked'))
              -- Go+ preview snips (30s) and geo-blocked tracks are unplayable
              AND (u.access IS NULL OR u.access = 'playable')
              AND (
                    ? IS NULL
                    OR u.uploaded_at < ?
                    OR (u.uploaded_at = ? AND u.id < ?)
              )
              AND (? = 0 OR da.in_top_200 = 1)
              AND (? = 0 OR EXISTS(
                       SELECT 1 FROM tracks t
                       WHERE t.artist_normalized = da.display_name_normalized
                         AND t.local_path IS NOT NULL
              ))
            ORDER BY u.uploaded_at DESC, u.id DESC
            LIMIT ?
            """,
            (
                int(show_hidden),
                cursor_uploaded_at,
                cursor_uploaded_at,
                cursor_uploaded_at,
                cursor_id or 0,
                int(top200),
                int(in_library),
                limit,
            ),
        ).fetchall()

    return [_row_to_feed_item(row) for row in rows]


def get_upload(upload_id: int) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute(
            """SELECT u.*, da.id AS da_id
            FROM sc_artist_uploads u
            JOIN discovery_artists da ON da.id = u.discovery_artist_id
            WHERE u.id = ?""",
            (upload_id,),
        ).fetchone()
    return dict(row) if row else None


def set_upload_status(upload_id: int, status: str) -> Optional[dict[str, Any]]:
    """Set rating status; returns the updated row dict or None if not found."""
    _validate_status(status)
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE sc_artist_uploads
            SET status = ?, rated_at = datetime('now')
            WHERE id = ?""",
            (status, upload_id),
        )
        conn.commit()
    return get_upload(upload_id)


def mark_sc_like_done(upload_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE sc_artist_uploads SET sc_like_done = 1 WHERE id = ?", (upload_id,)
        )
        conn.commit()


def mark_sc_playlist_done(upload_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE sc_artist_uploads SET sc_playlist_done = 1 WHERE id = ?",
            (upload_id,),
        )
        conn.commit()


def get_unsynced_liked_uploads() -> list[dict[str, Any]]:
    """+1 rows whose SC side (like / monthly playlist add) hasn't finished."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT id, soundcloud_id, sc_like_done, sc_playlist_done
            FROM sc_artist_uploads
            WHERE status = 'liked' AND (sc_like_done = 0 OR sc_playlist_done = 0)"""
        ).fetchall()
    return [dict(row) for row in rows]


def get_cached_monthly_playlist_id(name: str) -> Optional[str]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT sc_playlist_id FROM sc_monthly_playlists WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row["sc_playlist_id"]
        # Fall back to an already-imported local playlist with an SC id.
        row = conn.execute(
            """SELECT soundcloud_playlist_id FROM playlists
            WHERE name = ? AND soundcloud_playlist_id IS NOT NULL""",
            (name,),
        ).fetchone()
    return row["soundcloud_playlist_id"] if row else None


def cache_monthly_playlist_id(name: str, sc_playlist_id: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sc_monthly_playlists (name, sc_playlist_id)
            VALUES (?, ?)""",
            (name, sc_playlist_id),
        )
        conn.commit()
    logger.info(f"feed: cached monthly SC playlist '{name}' -> {sc_playlist_id}")
