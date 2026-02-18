# Expand Playlist Stats with Daily Pace

## Overview
Add daily comparison pace and estimated days to coverage for all playlist stats. This unifies global stats into the "All" playlist, removing the separate global stats endpoint. PlaylistTracksTable already serves as the leaderboard (sortable by rating).

## Task Sequence
1. [01-backend-analytics-functions.md](./01-backend-analytics-functions.md) - Add pace function to analytics.py
2. [02-backend-schema-endpoint.md](./02-backend-schema-endpoint.md) - Extend schema and wire up endpoint
3. [03-frontend-stats-modal.md](./03-frontend-stats-modal.md) - Add daily pace stat card, remove global stats code
4. [04-cleanup-dead-code.md](./04-cleanup-dead-code.md) - Remove unused global stats code

## Success Criteria
1. `uv run music-minion --web` starts without errors
2. Open comparison view, select any playlist, click stats button
3. Stats modal shows:
   - Daily pace stat card (comparisons per day)
   - Estimated days to coverage (if applicable)
   - Top Genres and Top Artists (unchanged)
   - PlaylistTracksTable at bottom (sortable by rating = leaderboard)
4. "All" playlist shows library-wide stats (equivalent to old global stats)
5. `uv run pytest web/backend/tests/` passes with no import errors

## Dependencies
- Existing `playlist_comparison_history` table with timestamps
- Existing `get_playlist_comparison_progress()` in `music_minion.domain.rating.database`
- Existing `PlaylistTracksTable` component (serves as leaderboard when sorted by rating)

## Notes
- Backend stats router already deleted (earlier in conversation)
- `LeaderboardEntry` and `GenreStat` schemas kept for potential future use
