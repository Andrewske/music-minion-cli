# Global Comparison Graph with Contextual Stats

## Overview
Transform the comparison system from "playlist-isolated" to "global comparison graph with contextual views":
- Comparisons are recorded once and visible across all playlists containing both tracks
- Wins/losses are calculated dynamically based on opponents in the current playlist
- Progress reflects all relevant comparisons (where both tracks are in playlist)
- Removes the legacy "first 5 to ALL" propagation logic

## Mental Model
The comparison history is a **global graph**. When viewing playlist X:
- You see stats filtered to opponents also in playlist X
- You don't get offered pairs you've already judged anywhere
- Progress reflects how many relevant pairs have been compared

## Task Sequence
1. [01-add-contextual-stats-function.md](./01-add-contextual-stats-function.md) - Add function to calculate wins/losses dynamically based on playlist context
2. [02-update-pair-selection.md](./02-update-pair-selection.md) - Change pair skipping to global + integrate dynamic stats
3. [03-update-progress-calculation.md](./03-update-progress-calculation.md) - Count comparisons where both tracks are in playlist
4. [04-remove-first-5-to-all-logic.md](./04-remove-first-5-to-all-logic.md) - Remove legacy propagation logic

## Success Criteria
1. Start comparison mode for playlist 384
2. Verify tracks show non-zero wins/losses for previously compared tracks
3. Make a new comparison, verify stats update
4. Check that pairs compared in "All" playlist don't appear again in playlist 384
5. Deploy to pi and verify on production data

## Dependencies
- SQLite database with existing `playlist_comparison_history` and `playlist_elo_ratings` tables
- No schema changes required - just query/logic changes
