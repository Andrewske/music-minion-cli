"""Bucket ops that propagate the bucket emoji must not nest transactions."""

from music_minion.core.database import get_db_connection
from web.backend.queries import buckets as bucket_queries


def _track_emojis(track_id: int) -> list[str]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT emoji_id FROM track_emojis WHERE track_id = ?", (track_id,)
        ).fetchall()
    return [r["emoji_id"] for r in rows]


def _make_emoji_bucket(emoji_id: str | None) -> tuple[str, int]:
    with get_db_connection() as conn:
        playlist_id = conn.execute(
            "INSERT INTO playlists (name, type) VALUES ('p', 'manual')"
        ).lastrowid
        track_id = conn.execute("INSERT INTO tracks (title) VALUES ('t')").lastrowid
        conn.commit()
    session = bucket_queries.get_or_create_session(playlist_id)
    bucket = bucket_queries.create_bucket(session["id"], "Energy", emoji_id, 0)
    return bucket["id"], track_id


def test_assign_and_unassign_with_emoji_bucket() -> None:
    """Regression: assigning to an emoji bucket raised 'cannot start a
    transaction within a transaction'."""
    bucket_id, track_id = _make_emoji_bucket("🔥")

    result = bucket_queries.assign_track_to_bucket(bucket_id, track_id)

    assert result is not None
    assert _track_emojis(track_id) == ["🔥"]

    assert bucket_queries.unassign_track(bucket_id, track_id)
    assert _track_emojis(track_id) == []


def test_update_bucket_emoji_swaps_track_emojis() -> None:
    bucket_id, track_id = _make_emoji_bucket("🔥")
    bucket_queries.assign_track_to_bucket(bucket_id, track_id)

    bucket_queries.update_bucket(bucket_id, None, "🌊")

    assert _track_emojis(track_id) == ["🌊"]
