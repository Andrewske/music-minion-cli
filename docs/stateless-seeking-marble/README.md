# Quick Tag Live Update

## Overview
When users vote in the Quick Tag sidebar (e.g., voting "⚡" for energy dimension), the track card should immediately update to show the voted emoji. Currently, Quick Tag votes are stored separately from the emoji display system, causing the UI to appear stale until page refresh.

This plan bridges the two systems by writing the winning emoji to `track_emojis` when a vote is recorded, and broadcasting the update via WebSocket to all connected devices.

## Task Sequence
1. [01-backend-emoji-sync.md](./01-backend-emoji-sync.md) - Write voted emoji to track_emojis table and broadcast via WebSocket
2. [02-frontend-emoji-propagation.md](./02-frontend-emoji-propagation.md) - Handle WebSocket event to update playerStore and comparisonStore

## Success Criteria

**End-to-end test:**
1. Start app: `music-minion --web`
2. Play a track and navigate to Comparison mode
3. Vote on a Quick Tag dimension in sidebar
4. Track card immediately shows the voted emoji (no refresh needed)
5. Navigate to Home - Now Playing also shows the emoji
6. Change vote - emoji swaps immediately
7. Skip vote (dash) - dimension emojis removed

## Dependencies
- Existing `batch_fetch_track_emojis()` in `web/backend/queries/emojis.py`
- Existing `updateTrackInPair()` in `comparisonStore`
- Existing `set()` method in `playerStore`
