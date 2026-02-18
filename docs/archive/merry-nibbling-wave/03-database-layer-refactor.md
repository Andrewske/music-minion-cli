---
task: 03-database-layer-refactor
status: done
depends: [01-database-migration, 02-config-cache-playlist-id]
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Database Layer Refactoring

## Context
Remove all global rating functions and session management. Add stateless progress queries with strategic pairing. Update recording to use single transaction for 30% speed improvement and ensure track_a_id < track_b_id constraint compliance.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify - removing ~350 lines, adding ~120 lines)

## Implementation Details

### 1. Remove Global Rating Functions (Delete Entirely)
Delete these functions (lines ~107-600):
- `record_comparison()` - global version
- `get_elo_rating()` - global version
- `update_elo_rating()` - global version
- `get_comparison_history()` - global version
- `get_session_history()` - session-based queries
- `get_tracks_by_rating()` - global version
- `calculate_rating_coverage()` - global version (if exists)

Keep only playlist versions:
- `record_playlist_comparison()`
- `get_playlist_elo_rating()`
- `get_playlist_comparison_history()`
- `get_playlist_tracks_by_rating()`

### 2. Remove Session Management Functions (lines 1027-1143)
Delete:
- `get_playlist_ranking_session()`
- `create_playlist_ranking_session()`
- `update_playlist_ranking_session()`
- `delete_playlist_ranking_session()`

### 3. Update record_playlist_comparison() with Single Transaction
Make session_id optional and ensure track_a_id < track_b_id:

```python
def record_playlist_comparison(
    playlist_id: int,
    track_a_id: str,
    track_b_id: str,
    winner_id: str,
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
        track_a_rating_before, track_b_rating_before = track_b_rating_before, track_a_rating_before
        track_a_rating_after, track_b_rating_after = track_b_rating_after, track_a_rating_after

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
                playlist_id, track_a_id, track_b_id, winner_id,
                track_a_rating_before, track_b_rating_before,
                track_a_rating_after, track_b_rating_after,
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
                track_a_id, playlist_id, track_a_rating_after,
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
                track_b_id, playlist_id, track_b_rating_after,
                1 if winner_id == track_b_id else 0,
                track_b_rating_after,
                1 if winner_id == track_b_id else 0,
                0 if winner_id == track_b_id else 1,
            ),
        )

        conn.commit()  # Single commit for all updates
```

### 4. Add Stateless Progress Queries
Add new exception and functions:

```python
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
    with get_db_connection() as conn:
        # Validate playlist has tracks
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,)
        )
        track_count = cursor.fetchone()['count']

        if track_count < 2:
            raise ValueError(f"Playlist {playlist_id} has {track_count} tracks - need at least 2 for comparison")

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
            raise RankingComplete(f"All pairs in playlist {playlist_id} have been compared")

        # Pick random from top 10 least-compared
        import random
        track_a_id = random.choice(candidates)['track_id']

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
            (playlist_id, playlist_id, track_a_id, track_a_id, playlist_id, track_a_id),
        )
        track_b_row = cursor.fetchone()

        if not track_b_row:
            raise RankingComplete(f"Track {track_a_id} has been compared to all other tracks")

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
        track_count = cursor.fetchone()['count']

        if track_count < 2:
            return {"compared": 0, "total": 0, "percentage": 0.0}

        # Calculate total possible pairs
        total_possible = (track_count * (track_count - 1)) // 2

        # Count existing comparisons
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM playlist_comparison_history WHERE playlist_id = ?",
            (playlist_id,),
        )
        compared = cursor.fetchone()[0]

        percentage = (compared / total_possible * 100) if total_possible > 0 else 0.0

        return {
            "compared": compared,
            "total": total_possible,
            "percentage": round(percentage, 2)
        }
```

## Verification

Test pair selection performance for 5000 tracks:
```bash
uv run python -c "
import time
from music_minion.domain.rating.database import get_next_playlist_pair, RankingComplete
from music_minion.core.config import get_all_playlist_id

all_id = get_all_playlist_id()

start = time.time()
for i in range(10):
    try:
        pair = get_next_playlist_pair(all_id)
        assert pair is not None, f'No pair found on iteration {i}'
    except RankingComplete:
        print(f'✅ Ranking complete after {i} iterations')
        break
elapsed = time.time() - start

print(f'✅ 10 pair queries in {elapsed:.2f}s ({elapsed/10*1000:.1f}ms avg)')
# Should be <100ms per query even for 5000 tracks with composite index
"
```

Expected: <100ms per query average
