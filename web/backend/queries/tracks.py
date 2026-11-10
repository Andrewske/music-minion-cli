"""Shared track query utilities."""

from typing import Sequence

from ..sc_likes import liked_soundcloud_ids
from .emojis import batch_fetch_track_emojis


def batch_fetch_tracks_with_metadata(
    track_ids: Sequence[int],
    db_conn,
    preserve_order: bool = True
) -> list[dict]:
    """Batch-fetch tracks with full metadata and emojis.

    Args:
        track_ids: Track IDs to fetch
        db_conn: Database connection
        preserve_order: If True, returns tracks in same order as track_ids

    Returns:
        List of track dicts with all columns + emojis array + sc_liked
    """
    if not track_ids:
        return []

    placeholders = ",".join("?" * len(track_ids))
    cursor = db_conn.execute(
        f"SELECT * FROM tracks WHERE id IN ({placeholders})",
        list(track_ids)
    )

    # Convert to dicts
    tracks_by_id = {row["id"]: dict(row) for row in cursor.fetchall()}

    # Batch-fetch emojis
    emojis_by_track = batch_fetch_track_emojis(list(tracks_by_id.keys()), db_conn)

    liked = liked_soundcloud_ids(
        db_conn, (t.get("soundcloud_id") for t in tracks_by_id.values())
    )

    # Add emojis and the SoundCloud like flag to each track
    for track_id, track in tracks_by_id.items():
        track["emojis"] = emojis_by_track.get(track_id, [])
        track["sc_liked"] = track.get("soundcloud_id") in liked

    # Preserve order if requested
    if preserve_order:
        return [tracks_by_id[tid] for tid in track_ids if tid in tracks_by_id]
    else:
        return list(tracks_by_id.values())
