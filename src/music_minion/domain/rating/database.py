"""Database operations for Elo rating system.

Pure functions for rating storage and retrieval.
All operations use connection context managers and single transactions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypedDict

from music_minion.core.database import get_db_connection


@dataclass
class EloRating:
    """Immutable Elo rating data."""

    track_id: int
    rating: float
    comparison_count: int
    wins: int
    last_compared: Optional[datetime]


class RatingCoverageStats(TypedDict):
    """Aggregated coverage metrics for Elo comparisons."""

    tracks_with_comparisons: int
    total_tracks: int
    total_comparisons: int
    coverage_percent: float
    average_comparisons_per_track: float
    average_comparisons_per_compared_track: float


class RatingCoverageFilters(TypedDict, total=False):
    """Filters applied when computing rating coverage."""

    source_filter: str
    genre_filter: str
    year_filter: int
    playlist_id: int


# Global rating functions removed - all comparisons now use playlist context


# Coverage and filtering functions removed - use playlist-scoped queries instead


# Playlist-specific rating functions


def get_playlist_elo_rating(track_id: int, playlist_id: int) -> float:
    """Get playlist-specific ELO rating for a track.

    Args:
        track_id: Track ID
        playlist_id: Playlist ID

    Returns:
        Current ELO rating (1500.0 if no rating exists)
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT rating
            FROM playlist_elo_ratings
            WHERE track_id = ? AND playlist_id = ?
            """,
            (track_id, playlist_id),
        )
        row = cursor.fetchone()
        return row["rating"] if row else 1500.0


def get_or_create_playlist_rating(track_id: int, playlist_id: int) -> EloRating:
    """Get playlist-specific ELO rating for a track, creating default if needed.

    Args:
        track_id: Track ID
        playlist_id: Playlist ID

    Returns:
        EloRating with current rating and comparison stats
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT rating, comparison_count, wins, last_compared
            FROM playlist_elo_ratings
            WHERE track_id = ? AND playlist_id = ?
            """,
            (track_id, playlist_id),
        )
        row = cursor.fetchone()
        if row:
            return EloRating(
                track_id=track_id,
                rating=row["rating"],
                comparison_count=row["comparison_count"],
                wins=row["wins"],
                last_compared=row["last_compared"],
            )
        return EloRating(
            track_id=track_id,
            rating=1500.0,
            comparison_count=0,
            wins=0,
            last_compared=None,
        )


def record_playlist_comparison(
    playlist_id: int,
    track_a_id: int,
    track_b_id: int,
    winner_id: int,
    track_a_rating_before: float,
    track_b_rating_before: float,
    track_a_rating_after: float,
    track_b_rating_after: float,
    session_id: str = "",  # Empty string for sessionless (NOT NULL constraint)
) -> None:
    """Record a playlist comparison with ELO updates.

    session_id defaults to empty string for sessionless comparisons.
    Uses single transaction for atomicity and performance.
    """
    # Ensure track_a_id < track_b_id for constraint compliance
    if track_a_id > track_b_id:
        track_a_id, track_b_id = track_b_id, track_a_id
        track_a_rating_before, track_b_rating_before = (
            track_b_rating_before,
            track_a_rating_before,
        )
        track_a_rating_after, track_b_rating_after = (
            track_b_rating_after,
            track_a_rating_after,
        )

    with get_db_connection() as conn:
        # Single transaction for both history + rating updates
        conn.execute(
            """
            INSERT INTO playlist_comparison_history (
                playlist_id, track_a_id, track_b_id, winner_id,
                track_a_rating_before, track_b_rating_before,
                track_a_rating_after, track_b_rating_after,
                session_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                playlist_id,
                track_a_id,
                track_b_id,
                winner_id,
                track_a_rating_before,
                track_b_rating_before,
                track_a_rating_after,
                track_b_rating_after,
                session_id,  # Empty string for sessionless
            ),
        )

        # Update both track ratings in same transaction
        conn.execute(
            """
            INSERT INTO playlist_elo_ratings (track_id, playlist_id, rating, comparison_count, wins, losses)
            VALUES (?, ?, ?, 1, ?, 0)
            ON CONFLICT (track_id, playlist_id) DO UPDATE SET
                rating = ?,
                comparison_count = comparison_count + 1,
                wins = wins + ?,
                losses = losses + ?
            """,
            (
                track_a_id,
                playlist_id,
                track_a_rating_after,
                1 if winner_id == track_a_id else 0,
                track_a_rating_after,
                1 if winner_id == track_a_id else 0,
                0 if winner_id == track_a_id else 1,
            ),
        )

        conn.execute(
            """
            INSERT INTO playlist_elo_ratings (track_id, playlist_id, rating, comparison_count, wins, losses)
            VALUES (?, ?, ?, 1, ?, 0)
            ON CONFLICT (track_id, playlist_id) DO UPDATE SET
                rating = ?,
                comparison_count = comparison_count + 1,
                wins = wins + ?,
                losses = losses + ?
            """,
            (
                track_b_id,
                playlist_id,
                track_b_rating_after,
                1 if winner_id == track_b_id else 0,
                track_b_rating_after,
                1 if winner_id == track_b_id else 0,
                0 if winner_id == track_b_id else 1,
            ),
        )

        conn.commit()  # Single commit for all updates


class RankingComplete(Exception):
    """Raised when all pairs in playlist have been compared."""

    pass


def get_next_playlist_pair(playlist_id: int) -> tuple[dict, dict]:
    """Get next uncompared track pair for playlist ranking (stateless).

    Uses strategic pairing with randomization:
    - Finds top 10 tracks with fewest comparisons
    - Picks random track from that set
    - Pairs it with another low-comparison-count track it hasn't faced

    Args:
        playlist_id: Playlist to get pair from

    Returns:
        Tuple of (track_a, track_b) dicts

    Raises:
        RankingComplete: When all possible pairs have been compared
    """
    import random

    with get_db_connection() as conn:
        # Validate playlist has tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )
        track_count = cursor.fetchone()["count"]

        if track_count < 2:
            raise ValueError(
                f"Playlist {playlist_id} has {track_count} tracks - need at least 2 for comparison"
            )

        # Step 1: Find top 10 tracks with fewest comparisons, pick random
        cursor = conn.execute(
            """
            SELECT pt.track_id, COUNT(pch.id) as comp_count
            FROM playlist_tracks pt
            LEFT JOIN playlist_comparison_history pch ON (
                (pch.track_a_id = pt.track_id OR pch.track_b_id = pt.track_id)
                AND pch.playlist_id = ?
            )
            WHERE pt.playlist_id = ?
            GROUP BY pt.track_id
            ORDER BY comp_count ASC
            LIMIT 10
            """,
            (playlist_id, playlist_id),
        )
        candidates = cursor.fetchall()

        if not candidates:
            raise RankingComplete(
                f"All pairs in playlist {playlist_id} have been compared"
            )

        # Pick random from top 10 least-compared
        track_a_id = random.choice(candidates)["track_id"]

        # Step 2: Find another track it hasn't been compared to
        # Check both orderings since historical data may not be normalized
        cursor = conn.execute(
            """
            SELECT t.*,
                   COALESCE(per.rating, 1500.0) as rating,
                   COALESCE(per.comparison_count, 0) as comparison_count
            FROM playlist_tracks pt
            JOIN tracks t ON pt.track_id = t.id
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            LEFT JOIN playlist_comparison_history pch ON (
                pch.playlist_id = ?
                AND (
                    (pch.track_a_id = ? AND pch.track_b_id = t.id)
                    OR (pch.track_b_id = ? AND pch.track_a_id = t.id)
                )
            )
            WHERE pt.playlist_id = ?
              AND t.id != ?
              AND pch.id IS NULL
            ORDER BY per.comparison_count ASC, RANDOM()
            LIMIT 1
            """,
            (
                playlist_id,
                playlist_id,
                track_a_id,
                track_a_id,
                playlist_id,
                track_a_id,
            ),
        )
        track_b_row = cursor.fetchone()

        if not track_b_row:
            raise RankingComplete(
                f"Track {track_a_id} has been compared to all other tracks"
            )

        # Get full track_a data
        cursor = conn.execute(
            """
            SELECT t.*,
                   COALESCE(per.rating, 1500.0) as rating,
                   COALESCE(per.comparison_count, 0) as comparison_count
            FROM tracks t
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            WHERE t.id = ?
            """,
            (playlist_id, track_a_id),
        )
        track_a_row = cursor.fetchone()

        return (dict(track_a_row), dict(track_b_row))


def get_playlist_comparison_progress(playlist_id: int) -> dict:
    """Calculate playlist ranking progress without sessions.

    Args:
        playlist_id: Playlist to check progress for

    Returns:
        {
            "compared": int,      # Comparisons made so far
            "total": int,         # Total possible pairs: N*(N-1)/2
            "percentage": float   # Progress percentage
        }
    """
    with get_db_connection() as conn:
        # Count tracks in playlist
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )
        track_count = cursor.fetchone()["count"]

        if track_count < 2:
            return {"compared": 0, "total": 0, "percentage": 0.0}

        # Calculate total possible pairs
        total_possible = (track_count * (track_count - 1)) // 2

        # Count existing comparisons
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_comparison_history WHERE playlist_id = ?",
            (playlist_id,),
        )
        compared = cursor.fetchone()["count"]

        percentage = (
            (compared / total_possible * 100) if total_possible > 0 else 0.0
        )

        return {
            "compared": compared,
            "total": total_possible,
            "percentage": round(percentage, 2),
        }


def get_playlist_comparison_history(playlist_id: int, limit: int = 50) -> list[dict]:
    """Get recent comparisons for a specific playlist.

    Args:
        playlist_id: Playlist ID
        limit: Maximum number of comparisons to return

    Returns:
        List of dicts with comparison history
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                pch.id,
                pch.track_a_id,
                pch.track_b_id,
                pch.winner_id,
                pch.session_id,
                pch.timestamp,
                ta.title as track_a_title,
                ta.artist as track_a_artist,
                tb.title as track_b_title,
                tb.artist as track_b_artist
            FROM playlist_comparison_history pch
            JOIN tracks ta ON pch.track_a_id = ta.id
            JOIN tracks tb ON pch.track_b_id = tb.id
            WHERE pch.playlist_id = ?
            ORDER BY pch.timestamp DESC
            LIMIT ?
            """,
            (playlist_id, limit),
        )

        return [dict(row) for row in cursor.fetchall()]


