# Fix Comparisons for Smart Playlists

## Overview
Comparisons fail with 400 error for smart playlists because `get_next_playlist_pair()` and `get_playlist_comparison_progress()` directly query `playlist_tracks` table, which is empty for smart playlists. Smart playlists store filter rules in `playlist_filters` and compute tracks dynamically.

The fix uses existing abstractions (`get_playlist_tracks()`, `get_playlist_track_count()`) that already handle both playlist types.

## Task Sequence
0. [00-delete-dead-leaderboard-code.md](./00-delete-dead-leaderboard-code.md) - Remove unused leaderboard/rankings code
1. [01-fix-rating-functions.md](./01-fix-rating-functions.md) - Fix pair selection to use track IDs from crud abstraction
2. [02-fix-get-playlist-comparison-progress.md](./02-fix-get-playlist-comparison-progress.md) - Fix progress tracking to use track count abstraction
3. [03-verify-end-to-end.md](./03-verify-end-to-end.md) - Manual browser testing for both playlist types

## Success Criteria
- Smart playlists can be selected for comparison without 400 error
- Comparison pairs load and display correctly
- Recording comparisons works (ELO updates)
- Progress percentage updates correctly
- Manual playlists still work (no regression)
- Dead leaderboard code removed

## Dependencies
- Existing `get_playlist_tracks()` in `src/music_minion/domain/playlists/crud.py`
- Existing `get_playlist_track_count()` in `src/music_minion/domain/playlists/crud.py`
