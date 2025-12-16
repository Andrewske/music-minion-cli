#!/usr/bin/env python3
"""
Test script for playlist pair selection.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.core.database import get_db_connection
from music_minion.domain.rating.elo import select_strategic_pair


def test_playlist_pair_selection():
    """Test selecting pairs from playlist tracks."""

    print("=== Testing Playlist Pair Selection ===")

    # Get playlist tracks
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                t.id, t.title, t.artist, t.album, t.genre, t.year,
                t.local_path, t.soundcloud_id, t.spotify_id, t.youtube_id, t.source,
                COALESCE(per.rating, 1500.0) as playlist_rating,
                COALESCE(per.comparison_count, 0) as playlist_comparison_count,
                COALESCE(per.wins, 0) as playlist_wins,
                COALESCE(er.rating, 1500.0) as global_rating
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            LEFT JOIN elo_ratings er ON t.id = er.track_id
            WHERE pt.playlist_id = ?
            ORDER BY pt.position
            LIMIT 10
            """,
            (361, 361),
        )

        tracks = []
        for row in cursor.fetchall():
            track = dict(row)
            track["rating"] = track["playlist_rating"]
            track["comparison_count"] = track["playlist_comparison_count"]
            track["wins"] = track["playlist_wins"]
            track["losses"] = (
                track["playlist_comparison_count"] - track["playlist_wins"]
            )
            tracks.append(track)

    print(f"Loaded {len(tracks)} tracks")

    if len(tracks) < 2:
        print("Not enough tracks!")
        return

    # Create ratings cache
    ratings_cache = {
        track["id"]: {
            "rating": track["playlist_rating"],
            "comparison_count": track["playlist_comparison_count"],
        }
        for track in tracks
    }

    print(f"Ratings cache keys: {list(ratings_cache.keys())[:5]}")

    try:
        track_a, track_b = select_strategic_pair(tracks, ratings_cache)
        print(f"✅ Successfully selected pair:")
        print(
            f"  A: {track_a['title']} by {track_a['artist']} (rating: {track_a['rating']})"
        )
        print(
            f"  B: {track_b['title']} by {track_b['artist']} (rating: {track_b['rating']})"
        )
    except Exception as e:
        print(f"❌ Failed to select pair: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_playlist_pair_selection()
