"""Shared emoji query functions."""

from typing import Sequence


def batch_fetch_track_emojis(
    track_ids: Sequence[int], db_conn
) -> dict[int, list[str]]:
    """Batch-fetch emojis for multiple tracks efficiently.

    Args:
        track_ids: Sequence of track database IDs
        db_conn: Database connection with row_factory set

    Returns:
        Dict mapping track_id -> list of emoji unicode strings (oldest first)
    """
    if not track_ids:
        return {}

    placeholders = ",".join("?" * len(track_ids))
    cursor = db_conn.execute(
        f"SELECT track_id, emoji_id FROM track_emojis "
        f"WHERE track_id IN ({placeholders}) "
        f"ORDER BY track_id, added_at ASC",
        list(track_ids),
    )

    result: dict[int, list[str]] = {}
    for row in cursor.fetchall():
        track_id = row["track_id"]
        emoji_id = row["emoji_id"]
        if track_id not in result:
            result[track_id] = []
        result[track_id].append(emoji_id)

    return result
