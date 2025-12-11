from fastapi import APIRouter, Depends
from loguru import logger
from typing import Optional
from ..deps import get_db
from music_minion.domain.rating.database import (
    get_ratings_coverage,
    get_prioritized_coverage,
    get_leaderboard,
)
from ..schemas import StatsResponse, GenreStat, LeaderboardEntry

router = APIRouter()


def _calculate_avg_comparisons_per_day(days: int = 7) -> float:
    """Calculate average comparisons per day over the last N days.

    Args:
        days: Number of days to look back

    Returns:
        Average comparisons per day
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT COUNT(*) as comparison_count
            FROM comparison_history
            WHERE timestamp >= datetime('now', '-{} days')
            """.format(days)
        )
        row = cursor.fetchone()
        total_comparisons = row["comparison_count"] if row else 0

    return total_comparisons / days if days > 0 else 0.0


def _estimate_coverage_time(
    total_tracks: int,
    total_comparisons: int,
    avg_per_day: float,
    target: int = 5,
) -> Optional[float]:
    """Estimate days until all tracks have target+ comparisons.

    Args:
        total_tracks: Total number of tracks in library
        total_comparisons: Total comparisons made so far
        avg_per_day: Average comparisons per day
        target: Target minimum comparisons per track

    Returns:
        Estimated days to reach target coverage, or None if cannot estimate
    """
    if avg_per_day <= 0:
        return None  # Cannot estimate if no comparisons happening

    # Each comparison rates 2 tracks, so:
    # - Total track-comparisons needed = total_tracks * target
    # - Current track-comparisons = total_comparisons * 2
    # - Each day's comparisons add avg_per_day * 2 track-comparisons
    total_track_comparisons_needed = total_tracks * target
    current_track_comparisons = total_comparisons * 2
    remaining = total_track_comparisons_needed - current_track_comparisons

    if remaining <= 0:
        return 0.0

    # Comparisons per day * 2 = track-comparisons per day
    track_comparisons_per_day = avg_per_day * 2
    days_needed = remaining / track_comparisons_per_day

    return max(0.0, days_needed)


def _detect_priority_path_prefix() -> Optional[str]:
    """Detect the most common path prefix that might be prioritized.

    Returns the path prefix with the most tracks, or None if no clear priority.
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                CASE
                    WHEN local_path LIKE '/music/%' THEN substr(local_path, 1, instr(substr(local_path, 8), '/') + 6)
                    ELSE NULL
                END as path_prefix,
                COUNT(*) as track_count
            FROM tracks
            WHERE local_path IS NOT NULL AND TRIM(local_path) != ''
            GROUP BY path_prefix
            HAVING track_count >= 10  -- Only consider prefixes with significant tracks
            ORDER BY track_count DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return row["path_prefix"] if row else None


def _get_genre_stats(limit: int = 10) -> list[GenreStat]:
    """Get genre statistics with average ratings.

    Args:
        limit: Maximum number of genres to return

    Returns:
        List of GenreStat objects for genres with 3+ tracks
    """
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                t.genre,
                COUNT(t.id) as track_count,
                AVG(COALESCE(e.rating, 1500.0)) as average_rating,
                SUM(COALESCE(e.comparison_count, 0)) as total_comparisons
            FROM tracks t
            LEFT JOIN elo_ratings e ON t.id = e.track_id
            WHERE t.genre IS NOT NULL AND TRIM(t.genre) != ''
            GROUP BY t.genre
            HAVING COUNT(t.id) >= 3
            ORDER BY average_rating DESC
            LIMIT ?
            """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                GenreStat(
                    genre=row["genre"],
                    track_count=row["track_count"],
                    average_rating=round(float(row["average_rating"]), 2),
                    total_comparisons=row["total_comparisons"],
                )
            )

        return results


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db=Depends(get_db)):
    """Get comprehensive statistics for the music library."""
    try:
        # Get coverage statistics (local tracks only - comparisons are local-only)
        coverage = get_ratings_coverage(filters={"source_filter": "local"})

        # Detect priority path prefix
        priority_path_prefix = _detect_priority_path_prefix()

        # Get prioritized coverage if we have a priority path
        prioritized_coverage = None
        prioritized_estimated_days = None
        if priority_path_prefix:
            prioritized_coverage = get_prioritized_coverage(
                priority_path_prefix, filters={"source_filter": "local"}
            )
            # Estimate time for prioritized tracks
            prioritized_estimated_days = _estimate_coverage_time(
                total_tracks=prioritized_coverage["total_tracks"],
                total_comparisons=prioritized_coverage["total_comparisons"],
                avg_per_day=_calculate_avg_comparisons_per_day(days=7),
                target=5,
            )

        # Get leaderboard (top 20 tracks with 5+ comparisons)
        leaderboard_data = get_leaderboard(limit=20, min_comparisons=5)
        leaderboard = [
            LeaderboardEntry(
                track_id=row["id"],
                title=row["title"],
                artist=row["artist"],
                rating=round(float(row["rating"]), 2),
                comparison_count=row["comparison_count"],
                wins=row["wins"] or 0,
                losses=row["comparison_count"] - (row["wins"] or 0),
            )
            for row in leaderboard_data
        ]

        # Calculate average comparisons per day (last 7 days)
        avg_comparisons_per_day = _calculate_avg_comparisons_per_day(days=7)

        # Estimate time to full coverage (all tracks with 5+ comparisons)
        estimated_days = _estimate_coverage_time(
            total_tracks=coverage["total_tracks"],
            total_comparisons=coverage["total_comparisons"],
            avg_per_day=avg_comparisons_per_day,
            target=5,
        )

        # Get genre statistics
        genre_stats = _get_genre_stats(limit=10)

        response = StatsResponse(
            total_comparisons=coverage["total_comparisons"],
            compared_tracks=coverage["tracks_with_comparisons"],
            total_tracks=coverage["total_tracks"],
            coverage_percent=round(coverage["coverage_percent"], 2),
            average_comparisons_per_day=round(avg_comparisons_per_day, 2),
            estimated_days_to_coverage=round(estimated_days, 1)
            if estimated_days is not None
            else None,
            prioritized_tracks=prioritized_coverage["total_tracks"]
            if prioritized_coverage
            else None,
            prioritized_coverage_percent=round(
                prioritized_coverage["coverage_percent"], 2
            )
            if prioritized_coverage
            else None,
            prioritized_estimated_days=round(prioritized_estimated_days, 1)
            if prioritized_estimated_days is not None
            else None,
            top_genres=genre_stats,
            leaderboard=leaderboard,
        )

        logger.info(
            f"Stats requested: {coverage['total_tracks']} tracks, {coverage['coverage_percent']:.1f}% coverage"
            + (
                f", prioritized: {prioritized_coverage['total_tracks']} tracks, {prioritized_coverage['coverage_percent']:.1f}%"
                if prioritized_coverage
                else ""
            )
        )
        return response

    except Exception as e:
        logger.exception("Failed to get stats")
        raise
