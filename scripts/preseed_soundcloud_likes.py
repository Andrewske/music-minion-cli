"""Preseed SoundCloud likes from soundcloud-discovery cache.

Usage: uv run python scripts/preseed_soundcloud_likes.py
"""

from pathlib import Path

import pandas as pd
from loguru import logger

from music_minion.core.database import get_db_connection

LIKES_PARQUET = Path.home() / "coding/soundcloud-discovery/.cache/likes.parquet"


def preseed_likes() -> None:
    """Import cached SoundCloud likes into database."""
    if not LIKES_PARQUET.exists():
        logger.warning(f"Cache not found: {LIKES_PARQUET}")
        return

    df = pd.read_parquet(LIKES_PARQUET)
    logger.info(f"Found {len(df)} cached likes")

    with get_db_connection() as conn:
        inserted = 0
        for _, row in df.iterrows():
            # Use metadata_artist if available, fall back to artist_name
            artist = row.get("metadata_artist") or row.get("artist_name") or ""

            conn.execute(
                """
                INSERT INTO tracks (
                    title, artist, genre, source, soundcloud_id, source_url
                ) VALUES (?, ?, ?, 'soundcloud', ?, ?)
                ON CONFLICT (source, soundcloud_id) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    genre = excluded.genre
            """,
                (
                    row["title"],
                    artist,
                    row.get("genre"),
                    str(row["track_id"]),
                    f"https://soundcloud.com/{row['track_slug']}",
                ),
            )
            inserted += 1

        # Create "SoundCloud Likes" playlist
        conn.execute(
            """
            INSERT INTO playlists (name, library, track_count, type)
            VALUES ('SoundCloud Likes', 'soundcloud', ?, 'manual')
            ON CONFLICT (name, library) DO UPDATE SET track_count = excluded.track_count
        """,
            (len(df),),
        )

        # Get playlist ID
        cursor = conn.execute(
            """SELECT id FROM playlists
            WHERE name = 'SoundCloud Likes' AND library = 'soundcloud'"""
        )
        playlist_id = cursor.fetchone()[0]

        # Link tracks to playlist
        cursor = conn.execute(
            "SELECT id, soundcloud_id FROM tracks WHERE source = 'soundcloud'"
        )
        id_map = {row["soundcloud_id"]: row["id"] for row in cursor.fetchall()}

        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,)
        )

        playlist_tracks = []
        for idx, (_, row) in enumerate(df.iterrows()):
            sc_id = str(row["track_id"])
            if sc_id in id_map:
                playlist_tracks.append((playlist_id, id_map[sc_id], idx + 1))

        conn.executemany(
            """INSERT INTO playlist_tracks (playlist_id, track_id, position)
            VALUES (?, ?, ?)""",
            playlist_tracks,
        )

        conn.commit()
        logger.info(f"Inserted {inserted} tracks, linked {len(playlist_tracks)} to playlist")


if __name__ == "__main__":
    preseed_likes()
