# Smart Playlist Skip Functionality

## Overview
Add skip functionality to smart playlists. Currently, smart playlists include all tracks matching filters with no way to exclude individual tracks. This feature adds a review mode where users can cycle through tracks and skip ones they don't want, with skips persisting across filter changes.

Key design decision: Reuse existing `playlist_builder_skipped` table rather than creating a new table.

## Task Sequence
1. [01-backend-exclusion-filter.md](./01-backend-exclusion-filter.md) - Modify smart playlist query to exclude skipped tracks
2. [02-backend-skip-endpoints.md](./02-backend-skip-endpoints.md) - Add skip/unskip/list API endpoints
3. [03-frontend-api-functions.md](./03-frontend-api-functions.md) - Add API client functions
4. [04-frontend-hook-mutations.md](./04-frontend-hook-mutations.md) - Add mutations and review mode state to hook
5. [05-frontend-review-mode-ui.md](./05-frontend-review-mode-ui.md) - Add review mode UI with waveform player
6. [06-frontend-skipped-dialog.md](./06-frontend-skipped-dialog.md) - Wire up skipped tracks dialog

## Success Criteria
End-to-end verification:
1. Create smart playlist with filters (e.g., year = 2024)
2. Enter review mode, verify tracks cycle through with waveform playback
3. Skip a track, verify it's excluded from track list
4. Change filters, verify skipped track stays excluded (persistent)
5. View skipped tracks dialog, unskip one, verify it returns to track list
6. Verify existing manual playlist builder still works unchanged

## Dependencies
- Existing `playlist_builder_skipped` table (no schema changes)
- Existing `builder.skip_track()` and `builder.unskip_track()` domain functions
- Existing `WaveformPlayer` component (already in SmartPlaylistEditor)

## Design Decisions
- **Exclusion filter location**: Added to `filters.py:evaluate_filters()` for SQL-level efficiency
- **Track navigation**: Uses `currentTrackId` (not index) as source of truth for robustness after skips
- **Review mode edge cases**: previousTrack() wraps around, skip-last-completes with "All done" state
- **SkippedTracksDialog**: Created as new shared component in `components/builder/`
- **Shared skip table**: Skips are playlist-scoped; a track skipped for playlist A still appears in playlist B if it matches filters
