# Playlist ELO Ranker Implementation Plan

## Overview
Implement playlist-specific ELO ranking system that allows ranking tracks within playlists using ELO comparisons, while controlling the impact on global ELO ratings. First 5 comparisons per track in playlist context affect global ratings; subsequent comparisons are playlist-specific only.

## Core Requirements
- **Playlist-Specific Ratings**: Separate ELO ratings per playlist with inheritance from global ratings
- **Threshold Control**: Only first 5 playlist comparisons per track affect global ratings
- **Dual Display**: Show both playlist and global ELO scores (playlist more prominent)
- **Resumable Sessions**: Single session per playlist that persists across app restarts
- **UI Integration**: Available in both CLI (`/rate --playlist-rank=<id>`) and web interfaces
- **Automatic Migration**: One-time script to initialize playlist ratings from global ratings

## Architecture

### Database Schema Changes
```sql
-- Playlist-specific ELO ratings
CREATE TABLE playlist_elo_ratings (
    track_id TEXT NOT NULL,
    playlist_id INTEGER NOT NULL,
    rating REAL DEFAULT 1500.0,
    comparison_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    last_compared TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (track_id, playlist_id),
    FOREIGN KEY (track_id) REFERENCES tracks(id),
    FOREIGN KEY (playlist_id) REFERENCES playlists(id)
);

-- Playlist comparison history
CREATE TABLE playlist_comparison_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_a_id TEXT NOT NULL,
    track_b_id TEXT NOT NULL,
    winner_id TEXT NOT NULL,
    playlist_id INTEGER NOT NULL,
    affects_global BOOLEAN NOT NULL,
    track_a_playlist_rating_before REAL,
    track_a_playlist_rating_after REAL,
    track_b_playlist_rating_before REAL,
    track_b_playlist_rating_after REAL,
    track_a_global_rating_before REAL,
    track_a_global_rating_after REAL,
    track_b_global_rating_before REAL,
    track_b_global_rating_after REAL,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (track_a_id) REFERENCES tracks(id),
    FOREIGN KEY (track_b_id) REFERENCES tracks(id),
    FOREIGN KEY (winner_id) REFERENCES tracks(id),
    FOREIGN KEY (playlist_id) REFERENCES playlists(id)
);

-- Session tracking for resumable playlist ranking
CREATE TABLE playlist_ranking_sessions (
    playlist_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    last_track_a_id TEXT,
    last_track_b_id TEXT,
    progress_stats TEXT, -- JSON: {"compared": 45, "total": 120}
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id)
);
```

### Core Logic Changes

#### Enhanced ELO Engine
- Modify `calculate_elo_update()` to accept optional `playlist_id` parameter
- Add `get_playlist_comparison_count(track_id, playlist_id)` function
- Implement threshold logic:
  ```python
  def should_affect_global(track_id: str, playlist_id: int) -> bool:
      count = get_playlist_comparison_count(track_id, playlist_id)
      return count < 5
  ```

#### Rating Inheritance
- New playlist ratings initialize from global rating: `playlist_rating = get_global_rating(track_id) or 1500`
- Maintain separate comparison counts for global vs playlist contexts

#### Session Management
- Single active session per playlist
- Automatic resumption: Check for existing session on ranking start
- Progress tracking with JSON stats

### Command Interface

#### Extended `/rate` Command
```bash
# Start playlist ranking session
/rate --playlist-rank=<playlist_id>

# Alternative shorter alias
/playlist rank <playlist_id>

# Resume existing session
/rate --playlist-rank=<playlist_id> --resume
```

#### Enhanced `/rankings` Command
```bash
# Show playlist-specific rankings
/rankings --playlist=<playlist_id>
```

### UI Integration

#### Blessed CLI
- Extend comparison mode with playlist filtering
- Dual rating display: `Playlist: 1720 | Global: 1650`
- Progress indicator: `Playlist Ranking: 45/120 compared (38%)`
- Visual threshold indicator: Show when ratings become playlist-only

#### Web UI
- Extend comparison API with `playlist_id` and `ranking_mode` parameters
- Frontend interface mirroring existing comparison UI
- Stats endpoint includes playlist ELO metrics

### Playlist Management

#### Reordering
- `reorder_playlist_by_elo(playlist_id)` function
- Updates `playlist_tracks.position` based on playlist ELO ratings
- Optional auto-reorder on ranking completion

#### Analytics Integration
Extend `get_playlist_analytics()` with:
- `elo_coverage_percentage`: % of tracks with playlist ratings
- `average_playlist_rating`: Mean ELO score within playlist
- `rating_distribution`: Histogram of playlist ratings
- `comparison_progress`: Current ranking completion status

### Migration Strategy

#### One-Time Migration Script
- `scripts/migrate_playlist_ratings.py`
- For each existing playlist:
  1. Get all tracks in playlist
  2. For each track: Initialize `playlist_elo_ratings` with global rating
  3. Log progress and handle errors gracefully
- Safe: Read-only for existing data, creates new table entries
- Revertible: Can drop new tables if needed

### Testing Strategy

#### Unit Tests
- Threshold logic: Verify routing to global vs playlist updates
- Rating inheritance: New playlist ratings start at global values
- Dual display: UI shows correct primary/secondary ratings
- Session management: Resume functionality works correctly

#### Integration Tests
- Full ranking session workflow (CLI and web)
- Session resumption across app restarts
- Playlist reordering accuracy
- Migration script correctness

#### Edge Cases
- Track appears in multiple playlists (separate ratings)
- Threshold boundary (exactly 5 comparisons)
- Empty playlists, single-track playlists
- Migration with missing global ratings

### Implementation Phases

#### Phase 1: Database & Core Logic (2-3 days)
1. Create new database tables and migrations
2. Implement enhanced ELO engine with threshold logic
3. Add session management functions
4. Create migration script and run on existing data

#### Phase 2: Command Interface (1 day)
1. Extend `/rate` command with playlist ranking flag
2. Add `/playlist rank` alias
3. Update `/rankings` with playlist filtering

#### Phase 3: UI Integration (2 days)
1. Blessed UI: Extend comparison mode with dual ratings
2. Web API: Add playlist ranking endpoints
3. Web frontend: Add playlist ranking interface

#### Phase 4: Playlist Management (1 day)
1. Implement playlist reordering by ELO
2. Extend analytics with ELO metrics
3. Update export functionality to respect ELO ordering

#### Phase 5: Testing & Validation (1-2 days)
1. Comprehensive unit and integration tests
2. Edge case testing
3. Performance validation
4. User acceptance testing

### Success Criteria
1. **Functionality**: Can rank any playlist with ELO comparisons
2. **Isolation**: Global ratings affected only by first 5 playlist comparisons per track
3. **UX**: Clear dual rating display, resumable sessions
4. **Integration**: Works seamlessly in CLI and web interfaces
5. **Data Integrity**: All ratings properly inherited and tracked
6. **Performance**: Minimal impact on existing operations

### Risk Mitigation
- **Comprehensive Testing**: Full test coverage for threshold logic and dual rating scenarios
- **Safe Migration**: Logged, revertible migration script
- **Backwards Compatibility**: No changes to existing global rating behavior
- **Incremental Deployment**: Can deploy phases independently
- **Monitoring**: Add logging for playlist ranking operations

## Dependencies
- Existing ELO rating system (domain/rating/)
- Playlist management system (domain/playlists/)
- Web comparison API (web/backend/routers/comparisons.py)
- Database migration system

## Future Enhancements
- Configurable threshold per playlist
- Playlist ranking statistics dashboard
- Batch ranking operations for multiple playlists
- Rating export/import for playlist sharing</content>
<parameter name="filePath">docs/playlist-elo-ranker-plan.md