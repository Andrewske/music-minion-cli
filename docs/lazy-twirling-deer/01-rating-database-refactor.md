---
task: 01-rating-database-refactor
status: done
depends: []
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Refactor record_playlist_comparison() with Centralized "First 5 Affect All" Logic

## Context
The comparison winner button fails with a SQLite column mismatch error. The code uses `track_a_rating_before` but the table has `track_a_playlist_rating_before`. Additionally, this task centralizes the "first 5 affect All" business logic in the database layer rather than splitting it across callers.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

### 1. Add imports and constants at top of file

```python
from music_minion.core.config import get_all_playlist_id
from music_minion.domain.rating.elo import update_ratings

# Number of comparisons per playlist that propagate to All playlist
FIRST_N_AFFECT_ALL = 5
```

### 2. Add helper function to DRY up rating updates

```python
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
```

### 3. Refactor `record_playlist_comparison()` - KEEP SAME SIGNATURE

The function signature stays the same. Internally, the function now:
1. Checks if we're comparing in the "All" playlist (skip propagation if so)
2. Checks comparison counts for each track (inlined query, no extra round-trip)
3. Fetches All playlist ratings for BOTH tracks (needed for ELO calc)
4. Calculates new All ratings for tracks that affect All
5. Records history with correct column names
6. Updates ratings using helper (DRY)
7. Wraps everything in try/except with rollback

```python
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

    Handles "first 5 affect All" logic internally:
    - If track has < FIRST_N_AFFECT_ALL comparisons in this playlist, propagate to All playlist
    - Skipped when comparing directly in All playlist
    """
    # Ensure track_a_id < track_b_id for constraint compliance
    # Note: winner_id stays unchanged - it's a reference to the actual winner,
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

    # Get All playlist ID with explicit error if not configured
    all_playlist_id = get_all_playlist_id()
    if all_playlist_id is None:
        raise ValueError(
            "All playlist not found. Create a playlist named 'All' with no filters."
        )

    # Guard: Skip propagation when comparing directly in All playlist
    if playlist_id == all_playlist_id:
        track_a_affects_all = False
        track_b_affects_all = False
        track_a_all_before = None
        track_b_all_before = None
        track_a_all_after = None
        track_b_all_after = None
    else:
        # Will check counts and fetch All ratings within the same connection below
        track_a_affects_all = None  # Determined after count check
        track_b_affects_all = None
        track_a_all_before = None
        track_b_all_before = None
        track_a_all_after = None
        track_b_all_after = None

    with get_db_connection() as conn:
        try:
            # If not in All playlist, check comparison counts (inlined, no extra round-trip)
            if playlist_id != all_playlist_id:
                cursor = conn.execute(
                    """
                    SELECT track_id, comparison_count
                    FROM playlist_elo_ratings
                    WHERE playlist_id = ? AND track_id IN (?, ?)
                    """,
                    (playlist_id, track_a_id, track_b_id)
                )
                counts = {row["track_id"]: row["comparison_count"] for row in cursor.fetchall()}
                track_a_count = counts.get(track_a_id, 0)
                track_b_count = counts.get(track_b_id, 0)
                track_a_affects_all = track_a_count < FIRST_N_AFFECT_ALL
                track_b_affects_all = track_b_count < FIRST_N_AFFECT_ALL

                # Fetch All playlist ratings for BOTH tracks if either affects All
                # (opponent rating needed for ELO calc even if opponent doesn't affect All)
                if track_a_affects_all or track_b_affects_all:
                    track_a_all_before = get_playlist_elo_rating(track_a_id, all_playlist_id)
                    track_b_all_before = get_playlist_elo_rating(track_b_id, all_playlist_id)

                    # Calculate new All ratings
                    k_factor = 32
                    if winner_id == track_a_id:
                        new_winner, new_loser = update_ratings(track_a_all_before, track_b_all_before, k_factor)
                        if track_a_affects_all:
                            track_a_all_after = new_winner
                        if track_b_affects_all:
                            track_b_all_after = new_loser
                    else:
                        new_winner, new_loser = update_ratings(track_b_all_before, track_a_all_before, k_factor)
                        if track_b_affects_all:
                            track_b_all_after = new_winner
                        if track_a_affects_all:
                            track_a_all_after = new_loser

            affects_global = bool(track_a_affects_all or track_b_affects_all)

            # Record history with CORRECT column names
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
                    affects_global,
                    track_a_rating_before,
                    track_b_rating_before,
                    track_a_rating_after,
                    track_b_rating_after,
                    track_a_all_before,
                    track_a_all_after,
                    track_b_all_before,
                    track_b_all_after,
                    session_id,
                ),
            )

            # Update playlist ratings using helper
            _update_playlist_rating(conn, track_a_id, playlist_id, track_a_rating_after, winner_id == track_a_id)
            _update_playlist_rating(conn, track_b_id, playlist_id, track_b_rating_after, winner_id == track_b_id)

            # Update All playlist ratings if affected
            if track_a_affects_all and track_a_all_after is not None:
                _update_playlist_rating(conn, track_a_id, all_playlist_id, track_a_all_after, winner_id == track_a_id)

            if track_b_affects_all and track_b_all_after is not None:
                _update_playlist_rating(conn, track_b_id, all_playlist_id, track_b_all_after, winner_id == track_b_id)

            conn.commit()

        except Exception:
            conn.rollback()
            raise
```

## Verification

```bash
# Unit test the refactored function
uv run pytest src/music_minion/domain/rating/ -v -k "comparison"

# Verify column names match schema
uv run python -c "
from music_minion.core.database import get_db_connection
with get_db_connection() as conn:
    cursor = conn.execute('PRAGMA table_info(playlist_comparison_history)')
    cols = [row['name'] for row in cursor.fetchall()]
    assert 'track_a_playlist_rating_before' in cols, f'Column not found: {cols}'
    assert 'affects_global' in cols, f'affects_global not found: {cols}'
    print('✅ Column names verified')
"

# Test "first 5 affect All" logic manually
uv run python -c "
from music_minion.core.database import get_db_connection
from music_minion.core.config import get_all_playlist_id
from music_minion.domain.rating.database import record_playlist_comparison, FIRST_N_AFFECT_ALL

print(f'✅ FIRST_N_AFFECT_ALL = {FIRST_N_AFFECT_ALL}')
print('✅ Function imports work')
"
```

## Tests (Minimal)

Add to `tests/domain/rating/test_database.py`:

```python
def test_record_comparison_column_names():
    """Verify INSERT uses correct column names matching schema."""
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute('PRAGMA table_info(playlist_comparison_history)')
        cols = {row['name'] for row in cursor.fetchall()}

    required = {
        'track_a_playlist_rating_before',
        'track_a_playlist_rating_after',
        'track_b_playlist_rating_before',
        'track_b_playlist_rating_after',
        'affects_global',
    }
    assert required.issubset(cols), f"Missing columns: {required - cols}"


def test_record_comparison_basic(test_db, test_playlist):
    """Basic recording works without error."""
    from music_minion.domain.rating.database import record_playlist_comparison

    # Should not raise
    record_playlist_comparison(
        playlist_id=test_playlist.id,
        track_a_id=1,
        track_b_id=2,
        winner_id=1,
        track_a_rating_before=1500.0,
        track_b_rating_before=1500.0,
        track_a_rating_after=1516.0,
        track_b_rating_after=1484.0,
    )
```

## Summary of Improvements

1. **DRY helper** - `_update_playlist_rating()` replaces 4 identical SQL blocks
2. **Inlined count query** - Single query fetches both track counts, no extra round-trips
3. **Top-level imports** - `update_ratings` imported at module level
4. **last_compared** - Updated on every rating change for "recently compared" queries
5. **Configurable threshold** - `FIRST_N_AFFECT_ALL = 5` constant
6. **Explicit All playlist check** - Raises clear error if All playlist missing
7. **Transaction safety** - try/except with rollback on failure
8. **Documented swap logic** - Comment explains winner_id doesn't need swapping
