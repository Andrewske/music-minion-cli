"""Genre query and mutation functions."""
from music_minion.core.database import get_db_connection, normalize_genre_name


def get_all_genres_query() -> list[dict]:
    """List all genres with track counts."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT id, name, emoji_id, track_count, created_at
            FROM genres ORDER BY track_count DESC, name ASC
        """).fetchall()
        return [dict(row) for row in rows]


def get_track_genres_query(track_id: int) -> list[dict]:
    """Get genres for a track, ordered by position."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT g.id, g.name, g.emoji_id, tg.position
            FROM genres g
            JOIN track_genres tg ON g.id = tg.genre_id
            WHERE tg.track_id = ?
            ORDER BY tg.position ASC
        """, (track_id,)).fetchall()
        return [dict(row) for row in rows]


def create_genre_mutation(name: str) -> dict:
    """Create a new genre (normalized)."""
    normalized = normalize_genre_name(name)
    with get_db_connection() as conn:
        conn.execute("INSERT INTO genres (name) VALUES (?)", (normalized,))
        conn.commit()
        row = conn.execute("SELECT * FROM genres WHERE name = ?", (normalized,)).fetchone()
        return dict(row)


def rename_genre_mutation(genre_id: int, new_name: str) -> dict:
    """Rename genre. If target exists, merge into it."""
    normalized = normalize_genre_name(new_name)
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        # Check if target name already exists
        existing = conn.execute(
            "SELECT id FROM genres WHERE name = ? AND id != ?",
            (normalized, genre_id)
        ).fetchone()

        if existing:
            # Merge: move track associations, delete source
            target_id = existing["id"]
            merge_genres_mutation_internal(conn, genre_id, target_id)
            conn.commit()
            return dict(conn.execute("SELECT * FROM genres WHERE id = ?", (target_id,)).fetchone())
        else:
            # Simple rename
            conn.execute("UPDATE genres SET name = ? WHERE id = ?", (normalized, genre_id))
            conn.commit()
            return dict(conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone())


def merge_genres_mutation_internal(conn, source_id: int, target_id: int) -> None:
    """Internal merge: move tracks from source to target, handle duplicates."""
    # For tracks that already have target genre, just delete source association
    conn.execute("""
        DELETE FROM track_genres
        WHERE genre_id = ? AND track_id IN (
            SELECT track_id FROM track_genres WHERE genre_id = ?
        )
    """, (source_id, target_id))

    # Move remaining tracks to target genre
    conn.execute("""
        UPDATE track_genres SET genre_id = ? WHERE genre_id = ?
    """, (target_id, source_id))

    # Delete source genre
    conn.execute("DELETE FROM genres WHERE id = ?", (source_id,))


def delete_genre_mutation(genre_id: int) -> dict:
    """Delete genre. Raises if tracks exist."""
    with get_db_connection() as conn:
        genre = conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone()
        if not genre:
            raise ValueError(f"Genre {genre_id} not found")
        if genre["track_count"] > 0:
            raise ValueError(f"Cannot delete genre with {genre['track_count']} tracks")
        conn.execute("DELETE FROM genres WHERE id = ?", (genre_id,))
        conn.commit()
        return {"deleted": True, "id": genre_id}


def set_track_genres_mutation(track_id: int, genre_ids: list[int]) -> list[dict]:
    """Set genres for a track in order (first = position 1)."""
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM track_genres WHERE track_id = ?", (track_id,))
        for position, genre_id in enumerate(genre_ids, start=1):
            conn.execute(
                "INSERT INTO track_genres (track_id, genre_id, position) VALUES (?, ?, ?)",
                (track_id, genre_id, position)
            )
        conn.commit()
    return get_track_genres_query(track_id)


def assign_genre_emoji_mutation(genre_id: int, emoji_id: str | None) -> dict:
    """Assign or remove emoji from genre. Propagates to track_emojis."""
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        old_emoji = conn.execute("SELECT emoji_id FROM genres WHERE id = ?", (genre_id,)).fetchone()
        old_emoji_id = old_emoji["emoji_id"] if old_emoji else None

        # Remove old genre-based emojis if changing
        if old_emoji_id and old_emoji_id != emoji_id:
            conn.execute("""
                DELETE FROM track_emojis
                WHERE source_type = 'genre' AND source_id = ?
            """, (str(genre_id),))

        # Update genre emoji
        conn.execute("UPDATE genres SET emoji_id = ? WHERE id = ?", (emoji_id, genre_id))

        # Add new emoji to all tracks with this genre
        if emoji_id:
            conn.execute("""
                INSERT OR IGNORE INTO track_emojis (id, track_id, emoji_id, source_type, source_id)
                SELECT hex(randomblob(16)), tg.track_id, ?, 'genre', ?
                FROM track_genres tg WHERE tg.genre_id = ?
            """, (emoji_id, str(genre_id), genre_id))

        conn.commit()
        return dict(conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone())
