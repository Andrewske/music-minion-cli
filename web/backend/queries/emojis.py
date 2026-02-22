"""Shared emoji query and mutation functions."""

import uuid
from typing import Any, Sequence

import emoji


def batch_fetch_track_emojis(track_ids: Sequence[int], db_conn) -> dict[int, list[str]]:
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


def get_emoji_default_name(emoji_unicode: str) -> str:
    """Get default name for emoji using emoji library fallback.

    Args:
        emoji_unicode: Unicode emoji character

    Returns:
        Human-readable emoji name
    """
    try:
        name = emoji.demojize(emoji_unicode)
        return name.strip(":").replace("_", " ")
    except Exception:
        return emoji_unicode


def add_emoji_to_track_mutation(
    track_id: int,
    emoji_id: str,
    db_conn,
    source_type: str = "manual",
    source_id: str | None = None,
) -> bool:
    """Add emoji to track atomically with use_count increment.

    Args:
        track_id: Track database ID
        emoji_id: Normalized emoji identifier
        db_conn: Database connection
        source_type: Source of emoji ('manual' | 'bucket' | 'bulk')
        source_id: Optional source identifier (e.g., bucket_id)

    Returns:
        True if emoji was added, False if already existed
    """
    # Generate 32-char hex UUID (no hyphens, consistent with migration pattern)
    instance_id = uuid.uuid4().hex

    db_conn.execute("BEGIN IMMEDIATE")
    try:
        # Auto-create metadata if missing
        default_name = get_emoji_default_name(emoji_id)
        db_conn.execute(
            """
            INSERT OR IGNORE INTO emoji_metadata (emoji_id, default_name, use_count)
            VALUES (?, ?, 0)
            """,
            (emoji_id, default_name),
        )

        # Insert association with source tracking
        cursor = db_conn.execute(
            """
            INSERT OR IGNORE INTO track_emojis
            (id, track_id, emoji_id, source_type, source_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (instance_id, track_id, emoji_id, source_type, source_id),
        )

        if cursor.rowcount > 0:
            db_conn.execute(
                """
                UPDATE emoji_metadata
                SET use_count = use_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE emoji_id = ?
                """,
                (emoji_id,),
            )
            db_conn.commit()
            return True
        else:
            db_conn.commit()
            return False
    except Exception:
        db_conn.rollback()
        raise


def remove_emoji_from_track_mutation(
    track_id: int,
    emoji_id: str,
    db_conn,
    source_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Remove emoji from track with protected emoji handling.

    Args:
        track_id: Track database ID
        emoji_id: Normalized emoji identifier
        db_conn: Database connection
        source_id: Optional source_id for targeted removal
        force: If True, bypass protected emoji check

    Returns:
        Dict with success status and metadata:
        - success: bool - whether removal occurred
        - protected: bool - whether emoji was protected (bucket/playlist)
        - source_type: str | None - source type of removed emoji
        - source_id: str | None - source id of removed emoji
    """
    # Check if emoji is protected (bucket or playlist source)
    cursor = db_conn.execute(
        """
        SELECT id, source_type, source_id
        FROM track_emojis
        WHERE track_id = ? AND emoji_id = ?
        """,
        (track_id, emoji_id),
    )
    row = cursor.fetchone()

    if not row:
        return {
            "success": False,
            "protected": False,
            "source_type": None,
            "source_id": None,
        }

    source_type = row["source_type"]
    found_source_id = row["source_id"]

    # Protected emojis cannot be deleted directly
    if source_type in ("bucket", "playlist") and not force:
        return {
            "success": False,
            "protected": True,
            "source_type": source_type,
            "source_id": found_source_id,
        }

    # Perform deletion
    if source_id:
        # Targeted removal by source_id
        db_conn.execute(
            "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id = ? AND source_id = ?",
            (track_id, emoji_id, source_id),
        )
    else:
        # Remove all instances of this emoji for the track
        db_conn.execute(
            "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id = ?",
            (track_id, emoji_id),
        )

    db_conn.commit()
    return {
        "success": True,
        "protected": False,
        "source_type": source_type,
        "source_id": found_source_id,
    }


def get_track_emojis_ordered(track_id: int, db_conn) -> list[dict[str, Any]]:
    """Get emojis for track ordered by source priority.

    Priority: playlist → bucket → manual (most authoritative first)

    Args:
        track_id: Track database ID
        db_conn: Database connection

    Returns:
        List of dicts with id, emoji_id, source_type, source_id, added_at
    """
    cursor = db_conn.execute(
        """
        SELECT id, emoji_id, source_type, source_id, added_at
        FROM track_emojis
        WHERE track_id = ?
        ORDER BY
            CASE source_type
                WHEN 'playlist' THEN 1
                WHEN 'bucket' THEN 2
                WHEN 'manual' THEN 3
                WHEN 'bulk' THEN 4
                ELSE 5
            END,
            added_at DESC
        """,
        (track_id,),
    )
    return [dict(row) for row in cursor.fetchall()]
