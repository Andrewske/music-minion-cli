"""
Emoji reactions API endpoints.

Provides emoji CRUD operations for track reactions and emoji metadata management.
"""

from typing import Optional

import emoji
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from music_minion.core.database import get_db_connection, normalize_emoji_id
from ..services.emoji_processor import delete_emoji_file


router = APIRouter(tags=["emojis"])


# === Pydantic Models ===


class EmojiInfo(BaseModel):
    """Emoji metadata representation for API responses."""

    emoji_id: str
    type: str = 'unicode'  # 'unicode' | 'custom'
    file_path: Optional[str] = None  # Only for custom emojis
    custom_name: Optional[str]
    default_name: str
    use_count: int
    last_used: Optional[str]


class TrackEmoji(BaseModel):
    """Track-emoji association for API responses."""

    emoji_id: str
    added_at: str


class AddEmojiRequest(BaseModel):
    """Request body for adding emoji to track."""

    emoji_id: str


class UpdateEmojiMetadataRequest(BaseModel):
    """Request body for updating emoji metadata."""

    custom_name: Optional[str]


# === Pure Helper Functions ===


def get_emoji_default_name(emoji_unicode: str) -> str:
    """Get default name for emoji using emoji library fallback.

    Args:
        emoji_unicode: Unicode emoji character

    Returns:
        Human-readable emoji name
    """
    try:
        # emoji.demojize() converts emoji to :name: format
        name = emoji.demojize(emoji_unicode)
        # Remove colons and underscores, e.g., :fire: -> fire
        return name.strip(':').replace('_', ' ')
    except Exception:
        # Fallback to unicode itself if lookup fails
        return emoji_unicode


def get_track_emojis_query(track_id: int, db_conn) -> list[dict]:
    """Query all emojis for a specific track.

    Args:
        track_id: Track database ID
        db_conn: Database connection

    Returns:
        List of emoji dictionaries with emoji_id and added_at
    """
    cursor = db_conn.execute(
        """
        SELECT emoji_id, added_at
        FROM track_emojis
        WHERE track_id = ?
        ORDER BY added_at DESC
        """,
        (track_id,)
    )
    return [dict(row) for row in cursor.fetchall()]


def get_top_emojis_query(db_conn, limit: int = 50) -> list[dict]:
    """Get top N emojis by use_count.

    Args:
        db_conn: Database connection
        limit: Maximum number of emojis to return

    Returns:
        List of emoji metadata dictionaries
    """
    cursor = db_conn.execute(
        """
        SELECT emoji_id, type, file_path, custom_name, default_name, use_count, last_used
        FROM emoji_metadata
        ORDER BY use_count DESC, last_used DESC
        LIMIT ?
        """,
        (limit,)
    )
    return [dict(row) for row in cursor.fetchall()]


def get_recent_emojis_query(db_conn, limit: int = 10) -> list[dict]:
    """Get recently used emojis by last_used timestamp.

    Args:
        db_conn: Database connection
        limit: Maximum number of emojis to return

    Returns:
        List of emoji metadata dictionaries
    """
    cursor = db_conn.execute(
        """
        SELECT emoji_id, type, file_path, custom_name, default_name, use_count, last_used
        FROM emoji_metadata
        WHERE last_used IS NOT NULL
        ORDER BY last_used DESC
        LIMIT ?
        """,
        (limit,)
    )
    return [dict(row) for row in cursor.fetchall()]


def search_emojis_query(db_conn, query: str) -> list[dict]:
    """Search emojis using Full-Text Search.

    Args:
        db_conn: Database connection
        query: Search query string

    Returns:
        List of emoji metadata dictionaries matching query
    """
    if not query.strip():
        return get_all_emojis_query(db_conn)

    # FTS5 MATCH syntax - searches both custom_name and default_name
    cursor = db_conn.execute(
        """
        SELECT m.emoji_id, m.type, m.file_path, m.custom_name, m.default_name, m.use_count, m.last_used
        FROM emoji_metadata_fts fts
        JOIN emoji_metadata m ON fts.rowid = m.rowid
        WHERE emoji_metadata_fts MATCH ?
        ORDER BY m.use_count DESC, m.last_used DESC
        LIMIT 100
        """,
        (query,)
    )
    return [dict(row) for row in cursor.fetchall()]


def get_all_emojis_query(db_conn, limit: int = 100, offset: int = 0) -> list[dict]:
    """Get all emojis with pagination support.

    Args:
        db_conn: Database connection
        limit: Maximum number of emojis to return
        offset: Number of emojis to skip

    Returns:
        List of emoji metadata dictionaries
    """
    cursor = db_conn.execute(
        """
        SELECT emoji_id, type, file_path, custom_name, default_name, use_count, last_used
        FROM emoji_metadata
        ORDER BY use_count DESC, last_used DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )
    return [dict(row) for row in cursor.fetchall()]


def add_emoji_to_track_mutation(track_id: int, emoji_id: str, db_conn) -> bool:
    """Add emoji to track atomically with use_count increment.

    Args:
        track_id: Track database ID
        emoji_id: Normalized emoji identifier
        db_conn: Database connection

    Returns:
        True if emoji was added, False if already existed
    """
    # Use IMMEDIATE transaction to prevent race conditions
    db_conn.execute("BEGIN IMMEDIATE")
    try:
        # Auto-create metadata if missing (for emojis outside initial 50)
        default_name = get_emoji_default_name(emoji_id)
        db_conn.execute(
            """
            INSERT OR IGNORE INTO emoji_metadata (emoji_id, default_name, use_count)
            VALUES (?, ?, 0)
            """,
            (emoji_id, default_name)
        )

        # Insert association (UPSERT pattern)
        cursor = db_conn.execute(
            "INSERT OR IGNORE INTO track_emojis (track_id, emoji_id) VALUES (?, ?)",
            (track_id, emoji_id)
        )

        # Only increment if row was actually inserted
        if cursor.rowcount > 0:
            db_conn.execute(
                """
                UPDATE emoji_metadata
                SET use_count = use_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE emoji_id = ?
                """,
                (emoji_id,)
            )
            db_conn.commit()
            return True
        else:
            db_conn.commit()  # No-op but clean transaction
            return False
    except Exception:
        db_conn.rollback()
        raise


def remove_emoji_from_track_mutation(track_id: int, emoji_id: str, db_conn) -> None:
    """Remove emoji from track (no use_count decrement).

    Args:
        track_id: Track database ID
        emoji_id: Normalized emoji identifier
        db_conn: Database connection
    """
    db_conn.execute(
        "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id = ?",
        (track_id, emoji_id)
    )
    db_conn.commit()


def update_emoji_custom_name_mutation(emoji_id: str, custom_name: Optional[str], db_conn) -> None:
    """Update emoji custom name.

    Args:
        emoji_id: Normalized emoji identifier
        custom_name: New custom name (None to clear)
        db_conn: Database connection
    """
    db_conn.execute(
        """
        UPDATE emoji_metadata
        SET custom_name = ?, updated_at = CURRENT_TIMESTAMP
        WHERE emoji_id = ?
        """,
        (custom_name, emoji_id)
    )
    db_conn.commit()


# === Endpoints ===


@router.get("/emojis/tracks/{track_id}/emojis")
def get_track_emojis(track_id: int) -> list[TrackEmoji]:
    """Get all emojis for a track."""
    with get_db_connection() as conn:
        return get_track_emojis_query(track_id, conn)


@router.post("/emojis/tracks/{track_id}/emojis")
def add_emoji_to_track(
    track_id: int,
    request: AddEmojiRequest
) -> dict[str, bool]:
    """Add emoji to track. Returns {"added": true/false}."""
    emoji_id = normalize_emoji_id(request.emoji_id)
    with get_db_connection() as conn:
        added = add_emoji_to_track_mutation(track_id, emoji_id, conn)
    return {"added": added}


@router.delete("/emojis/tracks/{track_id}/emojis/{emoji_id}")
def remove_emoji_from_track(
    track_id: int,
    emoji_id: str
) -> dict[str, bool]:
    """Remove emoji from track."""
    emoji_id = normalize_emoji_id(emoji_id)
    with get_db_connection() as conn:
        remove_emoji_from_track_mutation(track_id, emoji_id, conn)
    return {"removed": True}


@router.get("/emojis/top")
def get_top_emojis(limit: int = 50) -> list[EmojiInfo]:
    """Get top N emojis by usage."""
    with get_db_connection() as conn:
        return get_top_emojis_query(conn, limit)


@router.get("/emojis/recent")
def get_recent_emojis(limit: int = 10) -> list[EmojiInfo]:
    """Get recently used emojis (last N by last_used timestamp)."""
    with get_db_connection() as conn:
        return get_recent_emojis_query(conn, limit)


@router.get("/emojis/search")
def search_emojis(q: str) -> list[EmojiInfo]:
    """Search emojis by custom or default name."""
    with get_db_connection() as conn:
        return search_emojis_query(conn, q)


@router.get("/emojis/all")
def get_all_emojis(
    limit: int = 100,
    offset: int = 0
) -> list[EmojiInfo]:
    """Get all emoji metadata with pagination."""
    with get_db_connection() as conn:
        return get_all_emojis_query(conn, limit, offset)


@router.get("/emojis/custom-picker")
def get_custom_emojis_for_picker() -> list[dict]:
    """Get custom emojis in emoji-mart format for picker component."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT emoji_id, custom_name, default_name, file_path
            FROM emoji_metadata
            WHERE type = 'custom'
            ORDER BY use_count DESC
            """
        )

        return [
            {
                'id': row['emoji_id'],
                'name': row['custom_name'] or row['default_name'],
                'keywords': [row['default_name'].lower()],
                'skins': [{'src': f'/custom_emojis/{row["file_path"]}'}],
            }
            for row in cursor.fetchall()
        ]


@router.put("/emojis/metadata/{emoji_id}")
def update_emoji_metadata(
    emoji_id: str,
    request: UpdateEmojiMetadataRequest
) -> dict[str, bool]:
    """Update emoji custom name."""
    emoji_id = normalize_emoji_id(emoji_id)
    with get_db_connection() as conn:
        update_emoji_custom_name_mutation(emoji_id, request.custom_name, conn)
    return {"updated": True}


@router.delete("/emojis/custom/{emoji_id}")
def delete_custom_emoji(emoji_id: str) -> dict[str, bool]:
    """Delete a custom emoji and its file."""
    with get_db_connection() as conn:
        # Get emoji info and verify it's a custom emoji
        cursor = conn.execute(
            "SELECT type, file_path FROM emoji_metadata WHERE emoji_id = ?",
            (emoji_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Emoji not found")

        if row['type'] != 'custom':
            raise HTTPException(status_code=400, detail="Only custom emojis can be deleted via this endpoint")

        file_path = row['file_path']

        # Delete database records (track_emojis first due to foreign key)
        conn.execute("DELETE FROM track_emojis WHERE emoji_id = ?", (emoji_id,))
        conn.execute("DELETE FROM emoji_metadata WHERE emoji_id = ?", (emoji_id,))
        conn.commit()

        # Delete file
        try:
            delete_emoji_file(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete custom emoji file {file_path}: {e}")

    return {'deleted': True}
