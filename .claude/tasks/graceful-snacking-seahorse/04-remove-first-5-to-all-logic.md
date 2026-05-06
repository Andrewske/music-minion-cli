---
task: 04-remove-first-5-to-all-logic
status: complete
depends: [02-update-pair-selection, 03-update-progress-calculation]
files:
  - path: src/music_minion/domain/rating/database.py
    action: modify
---

# Remove "First 5 to ALL" Propagation Logic

## Context
Remove the legacy logic that propagates the first 5 comparisons per track to the "All" playlist. This simplifies `record_playlist_comparison()` and aligns with the new global comparison model.

## Files to Modify/Create
- src/music_minion/domain/rating/database.py (modify)

## Implementation Details

### 1. Delete the constant (line 19)
```python
# DELETE THIS LINE:
FIRST_N_AFFECT_ALL = 5
```

### 2. Simplify `record_playlist_comparison()` (lines 158-301)

**Remove these sections:**
- Lines 189-203: "Get All playlist ID" and guard clause
- Lines 216-252: Comparison count check and "affects All" calculations
- Lines 287-294: Conditional All playlist rating updates

**Keep these sections:**
- Track ID normalization (lines 175-187)
- Recording to `playlist_comparison_history` (but set `affects_global=False` always)
- Updating `playlist_elo_ratings` for the current playlist only

**Simplified function structure:**
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

    Records the comparison to history and updates playlist-specific ratings.
    No propagation to other playlists - the global comparison graph handles
    cross-playlist visibility.
    """
    # Normalize track IDs (ensure track_a_id < track_b_id)
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
        # Record history (affects_global always False now)
        conn.execute(
            """
            INSERT INTO playlist_comparison_history (
                playlist_id, track_a_id, track_b_id, winner_id,
                affects_global,
                track_a_playlist_rating_before, track_a_playlist_rating_after,
                track_b_playlist_rating_before, track_b_playlist_rating_after,
                track_a_global_rating_before, track_a_global_rating_after,
                track_b_global_rating_before, track_b_global_rating_after,
                session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                playlist_id, track_a_id, track_b_id, winner_id,
                False,  # affects_global always False
                track_a_rating_before, track_a_rating_after,
                track_b_rating_before, track_b_rating_after,
                None, None, None, None,  # No global ratings
                session_id,
            ),
        )

        # Update playlist ratings only
        _update_playlist_rating(
            conn, track_a_id, playlist_id, track_a_rating_after, winner_id == track_a_id
        )
        _update_playlist_rating(
            conn, track_b_id, playlist_id, track_b_rating_after, winner_id == track_b_id
        )

        conn.commit()
```

### 3. Remove unused imports (if any)
Check if `get_all_playlist_id` is still used elsewhere. If not, it can remain but won't be called from `record_playlist_comparison()`.

## Verification
1. Make a new comparison in playlist 384
2. Verify it records successfully (no errors)
3. Check `playlist_comparison_history` - new row should have `affects_global=0`
4. Verify "All" playlist ratings are NOT updated by this comparison
5. Run existing tests to ensure no regressions
