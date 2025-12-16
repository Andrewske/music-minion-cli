#!/usr/bin/env python3
"""
Migration script to initialize playlist-specific ELO ratings from global ratings.

This script should be run once after deploying the playlist ELO ranker feature.
It creates playlist_elo_ratings entries for all existing playlists, using global
ELO ratings as baselines where available.

Usage:
    python scripts/migrate_playlist_ratings.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from music_minion.core.database import get_db_connection


def migrate_playlist_ratings():
    """Migrate existing playlists to have playlist-specific ELO ratings."""

    logger.info("Starting playlist ELO ratings migration...")

    with get_db_connection() as conn:
        # Get all playlists with their tracks
        cursor = conn.execute("""
            SELECT
                p.id as playlist_id,
                p.name as playlist_name,
                pt.track_id,
                COALESCE(er.rating, 1500.0) as global_rating
            FROM playlists p
            JOIN playlist_tracks pt ON p.id = pt.playlist_id
            LEFT JOIN elo_ratings er ON pt.track_id = er.track_id
            ORDER BY p.id, pt.position
        """)

        playlists_data = {}
        for row in cursor.fetchall():
            playlist_id = row["playlist_id"]
            if playlist_id not in playlists_data:
                playlists_data[playlist_id] = {
                    "name": row["playlist_name"],
                    "tracks": [],
                }
            playlists_data[playlist_id]["tracks"].append(
                {"track_id": row["track_id"], "global_rating": row["global_rating"]}
            )

        logger.info(f"Found {len(playlists_data)} playlists to migrate")

        total_ratings_created = 0

        # Create playlist ratings for each playlist
        for playlist_id, playlist_data in playlists_data.items():
            playlist_name = playlist_data["name"]
            tracks = playlist_data["tracks"]

            logger.info(
                f"Migrating playlist '{playlist_name}' ({len(tracks)} tracks)..."
            )

            # Insert playlist ratings (use INSERT OR IGNORE to skip if already exists)
            rating_data = [
                (track["track_id"], playlist_id, track["global_rating"])
                for track in tracks
            ]

            conn.executemany(
                """
                INSERT OR IGNORE INTO playlist_elo_ratings (
                    track_id, playlist_id, rating, comparison_count, wins
                ) VALUES (?, ?, ?, 0, 0)
            """,
                rating_data,
            )

            ratings_created = conn.total_changes
            total_ratings_created += ratings_created

            logger.info(
                f"Created {ratings_created} playlist ratings for '{playlist_name}'"
            )

        conn.commit()

    logger.info(
        f"Migration complete! Created {total_ratings_created} playlist ratings across {len(playlists_data)} playlists"
    )
    return total_ratings_created


if __name__ == "__main__":
    try:
        migrate_playlist_ratings()
        logger.info("Migration completed successfully!")
    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        sys.exit(1)
