"""Database operations for Elo rating system.

Pure functions for rating storage and retrieval.
All operations use connection context managers and single transactions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypedDict

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.playlists.crud import get_playlist_track_count
from music_minion.domain.rating.elo import update_ratings


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


def get_contextual_track_stats(track_id: int, playlist_id: int) -> tuple[int, int]:
    """Calculate wins/losses for a track against opponents in this playlist.

    Counts comparisons from the global history where the opponent is also
    a current member of the given playlist. This is the "contextual view"
    of a track's performance — same comparison graph, filtered by context.

    Args:
        track_id: Track to get stats for
        playlist_id: Playlist context (only count opponents in this playlist)

    Returns:
        Tuple of (wins, losses)
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                SUM(CASE WHEN pch.winner_id = ? THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pch.winner_id != ? THEN 1 ELSE 0 END) as losses
            FROM playlist_comparison_history pch
            WHERE (pch.track_a_id = ? OR pch.track_b_id = ?)
              AND EXISTS (
                  SELECT 1 FROM playlist_tracks pt
                  WHERE pt.playlist_id = ?
                    AND pt.track_id = CASE
                        WHEN pch.track_a_id = ? THEN pch.track_b_id
                        ELSE pch.track_a_id
                    END
              )
            """,
            (track_id, track_id, track_id, track_id, playlist_id, track_id),
        )
        row = cursor.fetchone()
        wins = row["wins"] or 0
        losses = row["losses"] or 0
        logger.debug(
            f"Contextual stats track={track_id} playlist={playlist_id}: "
            f"{wins}W / {losses}L"
        )
        return (wins, losses)



def _update_playlist_rating(
    conn,
    track_id: int,
    playlist_id: int,
    new_rating: float,
    is_winner: bool,
) -> None:
    """Update a single track's rating in a playlist (internal helper).

    Uses INSERT ... ON CONFLICT for upsert semantics.
    Also updates last_compared timestamp.

    Note: The `wins` and `losses` columns track comparisons recorded IN this
    specific playlist context (i.e., when this playlist was active during
    record_playlist_comparison). They are NOT contextual wins — use
    get_contextual_track_stats() for wins against opponents in this playlist.
    """
    conn.execute(
        """
        INSERT INTO playlist_elo_ratings (track_id, playlist_id, rating, comparison_count, wins, losses, last_compared)
        VALUES (?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (track_id, playlist_id) DO UPDATE SET
            rating = ?,
            comparison_count = comparison_count + 1,
            wins = wins + ?,
            losses = losses + ?,
            last_compared = CURRENT_TIMESTAMP
        """,
        (
            track_id,
            playlist_id,
            new_rating,
            1 if is_winner else 0,
            0 if is_winner else 1,
            new_rating,
            1 if is_winner else 0,
            0 if is_winner else 1,
        ),
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
    session_id: str = "",
) -> None:
    """Record a playlist comparison with ELO updates.

    Records the comparison to the global history and updates playlist-specific
    ratings. No propagation to other playlists — the global comparison graph
    handles cross-playlist visibility via get_contextual_track_stats().
    """
    # Ensure track_a_id < track_b_id for constraint compliance.
    # winner_id stays unchanged — it's a reference to the actual winner,
    # not positional. The swap only affects which ratings go in which columns.
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
        try:
            conn.execute(
                """
                INSERT INTO playlist_comparison_history (
                    playlist_id, track_a_id, track_b_id, winner_id,
                    affects_global,
                    track_a_playlist_rating_before, track_b_playlist_rating_before,
                    track_a_playlist_rating_after, track_b_playlist_rating_after,
                    track_a_global_rating_before, track_a_global_rating_after,
                    track_b_global_rating_before, track_b_global_rating_after,
                    session_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    playlist_id,
                    track_a_id,
                    track_b_id,
                    winner_id,
                    False,  # affects_global is always False in the global graph model
                    track_a_rating_before,
                    track_b_rating_before,
                    track_a_rating_after,
                    track_b_rating_after,
                    None, None, None, None,  # No separate global ratings
                    session_id,
                ),
            )

            _update_playlist_rating(conn, track_a_id, playlist_id, track_a_rating_after, winner_id == track_a_id)
            _update_playlist_rating(conn, track_b_id, playlist_id, track_b_rating_after, winner_id == track_b_id)

            conn.commit()

        except Exception:
            logger.exception("Failed to record playlist comparison")
            conn.rollback()
            raise


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
        # Check playlist has enough tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )
        track_count = cursor.fetchone()["count"]
        if track_count < 2:
            raise ValueError(
                f"Playlist {playlist_id} has {track_count} tracks - need at least 2"
            )

        # Step 1: Find top 10 tracks with fewest comparisons
        # Uses stored comparison_count from playlist_elo_ratings (updated on each comparison)
        # with idx_playlist_elo_comparison_count index for fast sorting
        cursor = conn.execute(
            """
            SELECT t.id as track_id,
                   COALESCE(per.comparison_count, 0) as comp_count
            FROM tracks t
            INNER JOIN playlist_tracks pt ON t.id = pt.track_id AND pt.playlist_id = ?
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
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

        track_a_id = random.choice(candidates)["track_id"]

        # Step 2: Find another track it hasn't been compared to (globally).
        # NOT IN checks global history without playlist_id filter — a pair compared
        # in any playlist is considered done and won't be offered again.
        cursor = conn.execute(
            """
            SELECT t.*,
                   COALESCE(per.rating, 1500.0) as rating,
                   COALESCE(per.comparison_count, 0) as comparison_count,
                   COALESCE(per.wins, 0) as wins
            FROM tracks t
            INNER JOIN playlist_tracks pt ON t.id = pt.track_id AND pt.playlist_id = ?
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            WHERE t.id != ?
              AND t.id NOT IN (
                  SELECT track_b_id FROM playlist_comparison_history WHERE track_a_id = ?
                  UNION
                  SELECT track_a_id FROM playlist_comparison_history WHERE track_b_id = ?
              )
            ORDER BY per.comparison_count ASC, RANDOM()
            LIMIT 1
            """,
            (playlist_id, playlist_id, track_a_id, track_a_id, track_a_id),
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
                   COALESCE(per.comparison_count, 0) as comparison_count,
                   COALESCE(per.wins, 0) as wins
            FROM tracks t
            LEFT JOIN playlist_elo_ratings per ON t.id = per.track_id AND per.playlist_id = ?
            WHERE t.id = ?
            """,
            (playlist_id, track_a_id),
        )
        track_a_row = cursor.fetchone()

        track_b_id = track_b_row["id"]

        # Inject contextual stats (wins/losses against opponents in this playlist)
        a_wins, a_losses = get_contextual_track_stats(track_a_id, playlist_id)
        b_wins, b_losses = get_contextual_track_stats(track_b_id, playlist_id)

        track_a = dict(track_a_row)
        track_b = dict(track_b_row)

        track_a["wins"] = a_wins
        track_a["comparison_count"] = a_wins + a_losses
        track_b["wins"] = b_wins
        track_b["comparison_count"] = b_wins + b_losses

        return (track_a, track_b)


def get_playlist_comparison_progress(playlist_id: int) -> dict:
    """Calculate playlist ranking progress based on relevant comparisons.

    Counts distinct pairs compared where BOTH tracks are current members of
    this playlist, regardless of which playlist the comparison was originally
    recorded in. This reflects the global comparison graph model — work done
    in any playlist counts toward progress here.

    Args:
        playlist_id: Playlist to check progress for

    Returns:
        {
            "compared": int,      # Distinct pairs compared (both tracks in playlist)
            "total": int,         # Total possible pairs: N*(N-1)/2
            "percentage": float   # Progress percentage
        }
    """
    # Get track count - works for both manual and smart playlists
    track_count = get_playlist_track_count(playlist_id)

    if track_count < 2:
        return {"compared": 0, "total": 0, "percentage": 0.0}

    # Calculate total possible pairs
    total_possible = (track_count * (track_count - 1)) // 2

    with get_db_connection() as conn:
        # Count distinct pairs where both tracks are in this playlist.
        # DISTINCT on the normalized pair key prevents double-counting if the
        # same pair was somehow recorded more than once (e.g., from old data).
        cursor = conn.execute(
            """
            SELECT COUNT(DISTINCT
                CAST(pch.track_a_id AS TEXT) || '-' || CAST(pch.track_b_id AS TEXT)
            ) as count
            FROM playlist_comparison_history pch
            WHERE EXISTS (
                SELECT 1 FROM playlist_tracks pt1
                WHERE pt1.track_id = pch.track_a_id AND pt1.playlist_id = ?
            )
            AND EXISTS (
                SELECT 1 FROM playlist_tracks pt2
                WHERE pt2.track_id = pch.track_b_id AND pt2.playlist_id = ?
            )
            """,
            (playlist_id, playlist_id),
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


