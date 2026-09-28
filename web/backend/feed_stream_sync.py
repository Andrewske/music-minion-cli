"""Feed sync from SoundCloud's own stream (GET /me/feed/tracks).

One or two requests cover a day of activity from every followed artist, and
repost events carry exact repost times. SC throttles prolific accounts in the
stream (measured Sep 2026: ~20% of reposts and ~50% of uploads reach it, but
96% of kept tracks did), so the feed worker still runs the per-artist sweep
daily to backfill what the stream drops.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple, Optional

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import get_feed_tracks
from web.backend.feed_uploads_sync import (
    collect_uploads,
    get_known_upload_ids,
    insert_uploads,
)
from web.backend.queries import discovery as discovery_queries
from web.backend.soundcloud_metadata import track_metadata

# First run (no checkpoint) reaches back this far; later runs re-read an
# overlap so events SC delivers slightly late are not skipped.
FIRST_RUN_LOOKBACK = timedelta(days=60)
CHECKPOINT_OVERLAP = timedelta(hours=1)
MAX_PAGES = 60


class StreamEvents(NamedTuple):
    # (origin track, discovery_artists.id of reposter, exact repost time)
    reposts: list[tuple[dict[str, Any], int, str]]
    uploads_by_artist: dict[int, list[dict[str, Any]]]


def _user_id(value: Any) -> Optional[str]:
    """'soundcloud:users:123', 123, or {'id': 123} -> '123'."""
    if isinstance(value, dict):
        value = value.get("id")
    if value is None or value == "":
        return None
    return str(value).rsplit(":", 1)[-1]


def _followed_artist_ids() -> dict[str, int]:
    """soundcloud_user_id -> discovery_artists.id for followed artists."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT id, soundcloud_user_id FROM discovery_artists
            WHERE is_following = 1 AND soundcloud_user_id IS NOT NULL"""
        ).fetchall()
    return {str(row["soundcloud_user_id"]): row["id"] for row in rows}


def split_stream_items(
    items: list[dict[str, Any]], followed: dict[str, int], since: datetime
) -> StreamEvents:
    """Keep followed artists' reposts and uploads newer than `since`."""
    events = StreamEvents([], {})
    for item in items:
        track = item.get("origin") or {}
        created = item.get("created_at")
        if not track.get("id") or not _is_after(created, since):
            continue
        if item.get("type") == "track:repost":
            artist_id = followed.get(_user_id(item.get("reposter")) or "")
            if artist_id is not None:
                events.reposts.append((track, artist_id, created))
        elif item.get("type") == "track":
            artist_id = followed.get(_user_id(track.get("user")) or "")
            if artist_id is not None:
                events.uploads_by_artist.setdefault(artist_id, []).append(track)
    return events


def _is_after(raw: Any, since: datetime) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        return datetime.strptime(raw, "%Y/%m/%d %H:%M:%S %z") >= since
    except ValueError:
        return False


def _ingest_reposts(reposts: list[tuple[dict[str, Any], int, str]]) -> int:
    if not reposts:
        return 0
    discovery_queries.insert_discovery_tracks(
        [track_metadata(t) for t, _, _ in reposts]
    )
    ids = discovery_queries.get_discovery_track_ids_by_sc_ids(
        [str(t["id"]) for t, _, _ in reposts]
    )
    links = [
        (ids[str(track["id"])], artist_id, reposted_at, reposted_at, "exact")
        for track, artist_id, reposted_at in reposts
        if str(track["id"]) in ids
    ]
    return discovery_queries.insert_track_reposters(links)


def _ingest_uploads(uploads_by_artist: dict[int, list[dict[str, Any]]]) -> int:
    known_ids = get_known_upload_ids()
    return sum(
        insert_uploads(collect_uploads(tracks, artist_id, known_ids))
        for artist_id, tracks in uploads_by_artist.items()
    )


def _read_checkpoint() -> Optional[datetime]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT stream_checkpoint_at FROM sc_feed_sync_state WHERE id = 1"
        ).fetchone()
    raw = row["stream_checkpoint_at"] if row else None
    return datetime.fromisoformat(raw) if raw else None


def _write_checkpoint(at: datetime) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE sc_feed_sync_state SET stream_checkpoint_at = ? WHERE id = 1",
            (at.isoformat(),),
        )
        conn.commit()


def sync_from_stream(state: Any) -> tuple[int, int]:
    """Ingest new stream activity since the checkpoint.

    Returns (repost_events_added, uploads_added). Raises RuntimeError on an
    API failure without advancing the checkpoint, so the next run retries.
    """
    started = datetime.now(timezone.utc)
    checkpoint = _read_checkpoint()
    since = (
        checkpoint - CHECKPOINT_OVERLAP if checkpoint else started - FIRST_RUN_LOOKBACK
    )
    _state, items, error = get_feed_tracks(state, since, MAX_PAGES)
    if error:
        raise RuntimeError(
            f"/me/feed/tracks failed after {len(items)} items (since {since}): {error}"
        )

    events = split_stream_items(items, _followed_artist_ids(), since)
    reposts_added = _ingest_reposts(events.reposts)
    uploads_added = _ingest_uploads(events.uploads_by_artist)
    if reposts_added or uploads_added:
        discovery_queries.recalculate_artist_stats()
    _write_checkpoint(started)
    logger.info(
        f"feed_stream: {len(items)} stream items since {since.isoformat()}, "
        f"{reposts_added} new repost events, {uploads_added} new uploads"
    )
    return reposts_added, uploads_added
