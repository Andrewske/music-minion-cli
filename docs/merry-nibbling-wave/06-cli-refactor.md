---
task: 06-cli-refactor
status: done
depends: [03-database-layer-refactor]
files:
  - path: src/music_minion/ui/blessed/state.py
    action: modify
  - path: src/music_minion/ui/blessed/events/keys/comparison.py
    action: modify
  - path: src/music_minion/commands/rating.py
    action: modify
---

# CLI Refactoring

## Context
Remove session ID, session_start, and filter fields from CLI state (filters handled by smart playlists). Update comparison handlers to use stateless queries and handle RankingComplete exception. Always use playlist-based comparison.

## Files to Modify/Create
- src/music_minion/ui/blessed/state.py (modify - remove ~10 lines)
- src/music_minion/ui/blessed/events/keys/comparison.py (modify - ~35 lines)
- src/music_minion/commands/rating.py (modify - ~55 lines)

## Implementation Details

### 1. Remove Filters and Session from CLI State (state.py)

**Remove from ComparisonState:**
- `session_id`
- `session_start`
- `playlist_ranking_mode` (always playlist-based now)
- `genre_filter` (handled by smart playlist)
- `year_filter` (handled by smart playlist)
- `source_filter` (handled by smart playlist)

**Updated ComparisonState:**

```python
@dataclass
class ComparisonState:
    active: bool = False
    loading: bool = False
    track_a: Optional[dict] = None
    track_b: Optional[dict] = None
    highlighted: str = "a"

    # KEEP: Always playlist-based now
    playlist_id: Optional[int] = None  # Required when active=True

    # KEEP: Local UI state
    comparisons_done: int = 0
    filtered_tracks: list = field(default_factory=list)
    ratings_cache: Optional[dict] = None
    coverage_library_stats: Optional[RatingCoverageStats] = None
    coverage_filter_stats: Optional[RatingCoverageStats] = None
    last_autoplay_track_id: Optional[int] = None
    last_autoplay_time: Optional[float] = None
```

### 2. Update Comparison Handlers (comparison.py)

**Update handle_comparison_choice() to use stateless queries:**

```python
def handle_comparison_choice(state: UIState, winner: str) -> tuple[UIState, Optional[InternalCommand]]:
    """Record comparison winner (always playlist-based now)."""
    comparison = state.comparison

    # Always require playlist_id
    if not comparison.playlist_id:
        logger.error("No playlist selected for comparison")
        return state, None

    # Record comparison without session_id, single transaction
    try:
        record_playlist_comparison(
            playlist_id=comparison.playlist_id,
            track_a_id=comparison.track_a['id'],
            track_b_id=comparison.track_b['id'],
            winner_id=winner_id,
            track_a_rating_before=...,
            track_b_rating_before=...,
            track_a_rating_after=...,
            track_b_rating_after=...,
            session_id="",  # Empty string for sessionless
        )
    except Exception as e:
        logger.exception("Failed to record comparison")
        return state, None

    # Get next pair (stateless)
    try:
        track_a, track_b = get_next_playlist_pair(comparison.playlist_id)
        # Update state with next pair...
    except RankingComplete:
        # Show completion message
        log("🎉 Ranking complete! All tracks compared.", level="info")
        return end_comparison_session(state)
```

**Update all handlers:**
- Remove `session_id` from all comparison recording calls
- Handle `RankingComplete` exception
- Remove mode-switching logic

### 3. Update Comparison Commands (rating.py)

**Remove global comparison commands, update playlist comparison:**

```python
def start_playlist_comparison(ctx: AppContext, playlist_id: int) -> AppContext:
    """Start comparison mode for a playlist (no session creation)."""
    comparison_state = ComparisonState(
        active=True,
        playlist_id=playlist_id,
        # No session_id, no filters
    )

    # Get first pair
    try:
        track_a, track_b = get_next_playlist_pair(playlist_id)
        comparison_state.track_a = track_a
        comparison_state.track_b = track_b
    except RankingComplete:
        log("Playlist ranking already complete!", level="info")
        return ctx
    except ValueError as e:
        log(str(e), level="error")
        return ctx

    # Update context...
```

**Delete:**
- All global comparison command functions
- Session initialization code
- Mode-switching code

### 4. Prevent "All" Playlist Deletion

Add guard in playlist delete command/handler:

```python
def handle_delete_playlist(ctx: AppContext, playlist_id: int) -> AppContext:
    """Delete a playlist (protected: cannot delete 'All')."""
    # Get playlist name
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()
        if row and row["name"] == "All":
            log("Cannot delete 'All' playlist - it contains global rankings", level="error")
            return ctx

    # Proceed with deletion...
```

## Verification

Test CLI comparison mode:
```bash
# Start Music Minion
music-minion --dev

# Enter comparison mode for "All" playlist
# Do 5 comparisons
# Quit and restart

# Enter comparison mode for "All" again
# Verify: Progress shows 5 comparisons already done
# Verify: Next pair is #6 (not repeating previous pairs)
```

Test completion:
```bash
# Create small test playlist with 3 tracks
# Enter comparison mode for that playlist
# Complete all 3 comparisons
# Verify: Shows "🎉 Ranking complete!" message
# Verify: Exits comparison mode gracefully
```
