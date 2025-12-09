"""Database operations for Elo rating system.

Pure functions for rating storage and retrieval.
All operations use connection context managers and single transactions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypedDict

from loguru import logger

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


def get_or_create_rating(track_id: int) -> EloRating:
    """Get rating for track, creating if doesn't exist.

    Args:
        track_id: Track ID to get/create rating for

    Returns:
        EloRating dataclass with current rating data

    Raises:
        Exception: If track_id doesn't exist in tracks table
    """
    with get_db_connection() as conn:
        # Try to get existing rating
        cursor = conn.execute(
            """
            SELECT track_id, rating, comparison_count, wins, last_compared
            FROM elo_ratings
            WHERE track_id = ?
            """,
            (track_id,),
        )
        row = cursor.fetchone()

        if row:
            return EloRating(
                track_id=row["track_id"],
                rating=row["rating"],
                comparison_count=row["comparison_count"],
                wins=row["wins"] or 0,
                last_compared=(
                    datetime.fromisoformat(row["last_compared"])
                    if row["last_compared"]
                    else None
                ),
            )

        # Create new rating entry
        try:
            conn.execute(
                """
                INSERT INTO elo_ratings (track_id, rating, comparison_count, wins)
                VALUES (?, 1500.0, 0, 0)
                """,
                (track_id,),
            )
            conn.commit()

            return EloRating(
                track_id=track_id,
                rating=1500.0,
                comparison_count=0,
                wins=0,
                last_compared=None,
            )
        except Exception:
            logger.exception(f"Failed to create rating for track_id={track_id}")
            raise


def record_comparison(
    track_a_id: int,
    track_b_id: int,
    winner_id: int,
    track_a_rating_before: float,
    track_b_rating_before: float,
    track_a_rating_after: float,
    track_b_rating_after: float,
    session_id: str,
) -> None:
    """Record a comparison in history and update ratings.

    Single transaction ensures atomic update of both history and ratings.

    Args:
        track_a_id: First track ID
        track_b_id: Second track ID
        winner_id: ID of winning track (must be track_a_id or track_b_id)
        track_a_rating_before: Track A rating before comparison
        track_b_rating_before: Track B rating before comparison
        track_a_rating_after: Track A rating after comparison
        track_b_rating_after: Track B rating after comparison
        session_id: UUID for grouping comparisons into sessions

    Raises:
        ValueError: If winner_id is not track_a_id or track_b_id
        Exception: If database operation fails
    """
    if winner_id not in (track_a_id, track_b_id):
        raise ValueError(
            f"winner_id must be either track_a_id or track_b_id, got {winner_id}"
        )

    try:
        with get_db_connection() as conn:
            # Insert comparison history
            conn.execute(
                """
                INSERT INTO comparison_history (
                    track_a_id, track_b_id, winner_id,
                    track_a_rating_before, track_b_rating_before,
                    track_a_rating_after, track_b_rating_after,
                    session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_a_id,
                    track_b_id,
                    winner_id,
                    track_a_rating_before,
                    track_b_rating_before,
                    track_a_rating_after,
                    track_b_rating_after,
                    session_id,
                ),
            )

            # Update track A rating
            # Only increment wins if track A is the winner
            track_a_win_increment = 1 if winner_id == track_a_id else 0

            conn.execute(
                """
                UPDATE elo_ratings
                SET rating = ?,
                    comparison_count = comparison_count + 1,
                    wins = wins + ?,
                    last_compared = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE track_id = ?
                """,
                (track_a_rating_after, track_a_win_increment, track_a_id),
            )

            # Update track B rating
            # Only increment wins if track B is the winner
            track_b_win_increment = 1 if winner_id == track_b_id else 0

            conn.execute(
                """
                UPDATE elo_ratings
                SET rating = ?,
                    comparison_count = comparison_count + 1,
                    wins = wins + ?,
                    last_compared = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE track_id = ?
                """,
                (track_b_rating_after, track_b_win_increment, track_b_id),
            )

            # Single commit for all operations
            conn.commit()

    except Exception:
        logger.exception(
            f"Failed to record comparison: A={track_a_id} B={track_b_id} winner={winner_id}"
        )
        raise


def get_leaderboard(
    limit: int = 50,
    min_comparisons: int = 10,
    genre_filter: Optional[str] = None,
    year_filter: Optional[int] = None,
) -> list[dict]:
    """Get top-rated tracks with optional filters.

    Args:
        limit: Maximum number of tracks to return
        min_comparisons: Minimum number of comparisons required
        genre_filter: Optional genre to filter by (exact match)
        year_filter: Optional year to filter by (exact match)

    Returns:
        List of dicts with: track_id, title, artist, album, genre, year,
                           rating, comparison_count, wins, last_compared
    """
    where_clauses = ["e.comparison_count >= ?"]
    params: list = [min_comparisons]

    if genre_filter:
        where_clauses.append("t.genre LIKE ? COLLATE NOCASE")
        params.append(f"%{genre_filter}%")

    if year_filter:
        where_clauses.append("t.year = ?")
        params.append(year_filter)

    where_clause = " AND ".join(where_clauses)
    params.append(limit)

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                t.id,
                t.title,
                t.artist,
                t.album,
                t.genre,
                t.year,
                t.local_path,
                t.soundcloud_id,
                t.spotify_id,
                t.youtube_id,
                t.source,
                t.duration,
                e.rating,
                e.comparison_count,
                COALESCE(e.wins, 0) as wins,
                e.last_compared
            FROM elo_ratings e
            JOIN tracks t ON e.track_id = t.id
            WHERE {where_clause}
            ORDER BY e.rating DESC
            LIMIT ?
            """,
            params,
        )

        return [dict(row) for row in cursor.fetchall()]


def get_filtered_tracks(
    genre: Optional[str] = None,
    year: Optional[int] = None,
    playlist_id: Optional[int] = None,
    source_filter: Optional[str] = None,
) -> list[dict]:
    """Get tracks matching filters for comparison selection.

    Returns tracks with their current ratings (or 1500 if no rating exists).

    Args:
        genre: Optional genre filter (exact match)
        year: Optional year filter (exact match)
        playlist_id: Optional playlist ID to limit to playlist tracks
        source_filter: Optional source filter ('local', 'spotify', 'soundcloud', 'youtube', 'all')
                      If 'all' or None, includes tracks from all sources

    Returns:
        List of dicts with: id, title, artist, album, genre, year,
                           local_path, soundcloud_id, spotify_id, youtube_id,
                           source, duration, rating, comparison_count, wins
    """
    where_clauses = []
    params: list = []

    if genre:
        where_clauses.append("t.genre LIKE ? COLLATE NOCASE")
        params.append(f"%{genre}%")

    if year:
        where_clauses.append("t.year = ?")
        params.append(year)

    if playlist_id:
        where_clauses.append(
            "t.id IN (SELECT track_id FROM playlist_tracks WHERE playlist_id = ?)"
        )
        params.append(playlist_id)

    if source_filter and source_filter != "all":
        where_clauses.append("t.source = ?")
        params.append(source_filter)

    # Filter out tracks without valid local paths (NULL, empty, or whitespace-only)
    where_clauses.append("t.local_path IS NOT NULL AND TRIM(t.local_path) != ''")

    where_clause = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                t.id,
                t.title,
                t.artist,
                t.album,
                t.genre,
                t.year,
                t.bpm,
                t.local_path,
                t.soundcloud_id,
                t.spotify_id,
                t.youtube_id,
                t.source,
                t.duration,
                COALESCE(e.rating, 1500.0) as rating,
                COALESCE(e.comparison_count, 0) as comparison_count,
                COALESCE(e.wins, 0) as wins
            FROM tracks t
            LEFT JOIN elo_ratings e ON t.id = e.track_id
            {where_clause}
            ORDER BY t.artist, t.title
            """,
            params,
        )

        return [dict(row) for row in cursor.fetchall()]


def _build_coverage_where_clause(
    filters: RatingCoverageFilters | None,
) -> tuple[str, list]:
    """Construct WHERE clause and parameters for coverage queries."""

    if not filters:
        return "", []

    where_clauses: list[str] = []
    params: list = []

    source_filter = filters.get("source_filter")
    if source_filter and source_filter != "all":
        where_clauses.append("t.source = ?")
        params.append(source_filter)

    genre_filter = filters.get("genre_filter")
    if genre_filter:
        where_clauses.append("t.genre LIKE ? COLLATE NOCASE")
        params.append(f"%{genre_filter}%")

    year_filter = filters.get("year_filter")
    if year_filter:
        where_clauses.append("t.year = ?")
        params.append(year_filter)

    playlist_id = filters.get("playlist_id")
    if playlist_id:
        where_clauses.append(
            "t.id IN (SELECT track_id FROM playlist_tracks WHERE playlist_id = ?)"
        )
        params.append(playlist_id)

    if not where_clauses:
        return "", []

    return "WHERE " + " AND ".join(where_clauses), params


def get_ratings_coverage(
    filters: RatingCoverageFilters | None = None,
) -> RatingCoverageStats:
    """Get rating coverage metrics for the requested filters."""

    where_clause, params = _build_coverage_where_clause(filters)

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                COUNT(t.id) as total_tracks,
                SUM(CASE WHEN COALESCE(e.comparison_count, 0) > 0 THEN 1 ELSE 0 END)
                    as compared_tracks,
                COALESCE(SUM(e.comparison_count), 0) as total_comparisons
            FROM tracks t
            LEFT JOIN elo_ratings e ON t.id = e.track_id
            {where_clause}
            """,
            params,
        )
        row = cursor.fetchone()

    total_tracks = row["total_tracks"] or 0
    compared_tracks = row["compared_tracks"] or 0
    total_comparisons = row["total_comparisons"] or 0

    coverage_percent = (compared_tracks / total_tracks * 100) if total_tracks else 0.0
    average_per_track = total_comparisons / total_tracks if total_tracks else 0.0
    average_per_compared = (
        total_comparisons / compared_tracks if compared_tracks else 0.0
    )

    return RatingCoverageStats(
        tracks_with_comparisons=compared_tracks,
        total_tracks=total_tracks,
        total_comparisons=total_comparisons,
        coverage_percent=coverage_percent,
        average_comparisons_per_track=average_per_track,
        average_comparisons_per_compared_track=average_per_compared,
    )


def get_least_compared_tracks(
    limit: int = 100,
    genre_filter: Optional[str] = None,
    year_filter: Optional[int] = None,
    playlist_id: Optional[int] = None,
) -> list[dict]:
    """Get tracks with fewest comparisons for balanced rating.

    Useful for selecting next tracks to compare to ensure all tracks
    get rated evenly.

    Args:
        limit: Maximum number of tracks to return
        genre_filter: Optional genre to filter by
        year_filter: Optional year to filter by
        playlist_id: Optional playlist ID to limit to

    Returns:
        List of dicts with: track_id, title, artist, comparison_count, wins, rating
    """
    where_clauses = []
    params: list = []

    if genre_filter:
        where_clauses.append("t.genre LIKE ? COLLATE NOCASE")
        params.append(f"%{genre_filter}%")

    if year_filter:
        where_clauses.append("t.year = ?")
        params.append(year_filter)

    if playlist_id:
        where_clauses.append(
            "t.id IN (SELECT track_id FROM playlist_tracks WHERE playlist_id = ?)"
        )
        params.append(playlist_id)

    where_clause = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.append(limit)

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                t.id as track_id,
                t.title,
                t.artist,
                COALESCE(e.comparison_count, 0) as comparison_count,
                COALESCE(e.wins, 0) as wins,
                COALESCE(e.rating, 1500.0) as rating
            FROM tracks t
            LEFT JOIN elo_ratings e ON t.id = e.track_id
            {where_clause}
            ORDER BY COALESCE(e.comparison_count, 0) ASC, t.artist, t.title
            LIMIT ?
            """,
            params,
        )

        return [dict(row) for row in cursor.fetchall()]


def get_session_history(session_id: str) -> list[dict]:
    """Get all comparisons for a specific session.

    Args:
        session_id: Session UUID

    Returns:
        List of dicts with: id, track_a_id, track_b_id, winner_id,
                           track_a_rating_before, track_b_rating_before,
                           track_a_rating_after, track_b_rating_after, timestamp
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                id, track_a_id, track_b_id, winner_id,
                track_a_rating_before, track_b_rating_before,
                track_a_rating_after, track_b_rating_after,
                timestamp
            FROM comparison_history
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )

        return [dict(row) for row in cursor.fetchall()]


def get_recent_comparisons(limit: int = 50) -> list[dict]:
    """Get recent comparisons across all sessions.

    Args:
        limit: Maximum number of comparisons to return

    Returns:
        List of dicts with: id, track_a_id, track_b_id, winner_id,
                           session_id, timestamp, plus track metadata
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                ch.id,
                ch.track_a_id,
                ch.track_b_id,
                ch.winner_id,
                ch.session_id,
                ch.timestamp,
                ta.title as track_a_title,
                ta.artist as track_a_artist,
                tb.title as track_b_title,
                tb.artist as track_b_artist
            FROM comparison_history ch
            JOIN tracks ta ON ch.track_a_id = ta.id
            JOIN tracks tb ON ch.track_b_id = tb.id
            ORDER BY ch.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [dict(row) for row in cursor.fetchall()]


def get_track_comparison_count(track_id: int) -> int:
    """Get number of comparisons for a specific track.

    Args:
        track_id: Track ID

    Returns:
        Number of comparisons (0 if track has no rating yet)
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT COALESCE(comparison_count, 0) as count
            FROM elo_ratings
            WHERE track_id = ?
            """,
            (track_id,),
        )

        row = cursor.fetchone()
        return row["count"] if row else 0


def batch_initialize_ratings(track_ids: list[int]) -> int:
    """Batch create rating entries for tracks.

    Uses executemany for efficient bulk creation.

    Args:
        track_ids: List of track IDs to initialize

    Returns:
        Number of ratings created
    """
    if not track_ids:
        return 0

    # Prepare batch data (all start at 1500.0 with 0 comparisons and 0 wins)
    ratings = [(track_id, 1500.0, 0, 0) for track_id in track_ids]

    try:
        with get_db_connection() as conn:
            # Use INSERT OR IGNORE to skip tracks that already have ratings
            conn.executemany(
                """
                INSERT OR IGNORE INTO elo_ratings (track_id, rating, comparison_count, wins)
                VALUES (?, ?, ?, ?)
                """,
                ratings,
            )
            inserted_count = conn.total_changes
            conn.commit()

            return inserted_count

    except Exception:
        logger.exception(f"Failed to batch initialize {len(track_ids)} ratings")
        raise
