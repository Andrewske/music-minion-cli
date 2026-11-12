"""Uploader identity on liked tracks (sc_likes.uploader_* columns).

Every /me/likes/tracks item carries the uploading account in `track.user`.
The likes sync (hourly, incremental) and the nightly full reconcile both
record it here, so follow suggestions can key likes by SC account id.
"""

import sqlite3
from collections.abc import Mapping
from typing import Any, NamedTuple
from urllib.parse import urlparse

from loguru import logger

from music_minion.core import database


class LikeUploader(NamedTuple):
    soundcloud_user_id: str
    permalink: str | None
    username: str | None


def uploader_from_track(track: Any) -> LikeUploader | None:
    """The uploader of one SC track payload, or None when it has no user id."""
    user = track.get("user") if isinstance(track, dict) else None
    if not isinstance(user, dict) or user.get("id") in (None, ""):
        return None
    return LikeUploader(
        str(user["id"]), user.get("permalink") or None, user.get("username") or None
    )


def permalink_from_url(url: str | None) -> str | None:
    """'https://soundcloud.com/phrva/shabba?utm=..' -> 'phrva' (the uploader)."""
    parsed = urlparse(url or "")
    if not parsed.netloc.endswith("soundcloud.com"):
        return None
    first = parsed.path.strip("/").split("/")[0]
    return first or None


def uploaders_by_track(tracks: list[Any]) -> dict[str, LikeUploader]:
    """soundcloud track id -> uploader, for every track that has both."""
    found: dict[str, LikeUploader] = {}
    for track in tracks:
        uploader = uploader_from_track(track)
        if uploader and isinstance(track, dict) and track.get("id") not in (None, ""):
            found[str(track["id"])] = uploader
    return found


# A row with no uploader gets one; a row with this uploader's id but no name
# (phase 1 of the backfill stores bare ids) gets the name filled in.
_FILL_SQL = """
    UPDATE sc_likes
    SET uploader_soundcloud_id = :uid,
        uploader_permalink = COALESCE(uploader_permalink, :permalink),
        uploader_username = COALESCE(uploader_username, :username)
    WHERE soundcloud_id = :sc_id AND (
        uploader_soundcloud_id IS NULL
        OR (uploader_soundcloud_id = :uid
            AND (uploader_username IS NULL OR uploader_permalink IS NULL)
            AND (:username IS NOT NULL OR :permalink IS NOT NULL)))
"""


def fill_like_uploaders(uploaders: Mapping[str, LikeUploader]) -> int:
    """Fill missing uploader columns on sc_likes rows; returns rows changed.

    The first known uploader id sticks (a different id never overwrites it),
    and rows are never created here, so this is safe after any likes writer.
    """
    if not uploaders:
        return 0
    rows = [
        {"uid": u.soundcloud_user_id, "permalink": u.permalink,
         "username": u.username, "sc_id": sc_id}
        for sc_id, u in sorted(uploaders.items())
    ]  # fmt: skip
    with database.get_db_connection() as conn:
        before = conn.total_changes
        conn.executemany(_FILL_SQL, rows)
        filled = conn.total_changes - before
        conn.commit()
    return filled


def record_like_uploaders(uploaders: Mapping[str, LikeUploader]) -> None:
    """fill_like_uploaders for background writers: logs, never raises."""
    try:
        filled = fill_like_uploaders(uploaders)
        if filled:
            logger.info(f"sc_likes: filled uploader for {filled} likes")
    except sqlite3.Error:
        logger.exception(f"Failed to fill uploader on {len(uploaders)} sc_likes rows")


# ---------------------------------------------------------------------------
# Backfill (scripts/backfill_like_uploaders.py)
# ---------------------------------------------------------------------------

# Phase 1: uploader ids MM already holds for feed/upload rows of liked tracks.
# The permalink comes from a known discovery_artists account, else from the
# track URL; the display name only from discovery_artists.
_LOCAL_UPLOADERS_SQL = """
    SELECT l.soundcloud_id,
           COALESCE(dt.uploader_soundcloud_id, u.uploader_soundcloud_id) AS uid,
           da.slug, da.display_name,
           COALESCE(dt.permalink_url, u.permalink_url) AS track_url
    FROM sc_likes l
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = l.soundcloud_id
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = l.soundcloud_id
    LEFT JOIN discovery_artists da ON da.id = (
        SELECT id FROM discovery_artists
        WHERE soundcloud_user_id = COALESCE(dt.uploader_soundcloud_id,
                                            u.uploader_soundcloud_id)
        LIMIT 1)
    WHERE l.uploader_soundcloud_id IS NULL
      AND COALESCE(dt.uploader_soundcloud_id, u.uploader_soundcloud_id) IS NOT NULL
"""


def local_uploaders() -> dict[str, LikeUploader]:
    """Phase 1 candidates: liked track id -> uploader from local feed tables."""
    with database.get_db_connection() as conn:
        rows = conn.execute(_LOCAL_UPLOADERS_SQL).fetchall()
    return {
        str(r[0]): LikeUploader(str(r[1]), r[2] or permalink_from_url(r[4]), r[3])
        for r in rows
    }


def missing_uploader_ids() -> list[str]:
    """Liked track ids that still have no uploader."""
    with database.get_db_connection() as conn:
        rows = conn.execute(
            """SELECT soundcloud_id FROM sc_likes
            WHERE uploader_soundcloud_id IS NULL ORDER BY soundcloud_id"""
        ).fetchall()
    return [str(r[0]) for r in rows]


def like_count() -> int:
    with database.get_db_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM sc_likes").fetchone()[0]
