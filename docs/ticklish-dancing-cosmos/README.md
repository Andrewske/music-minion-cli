# Fix Listening History Page

## Overview
Track every song play across the site with timestamps AND duration. Remove radio station concepts. Every play() call (not resume) creates a history entry; pause/skip/track-end closes it with duration.

## Task Sequence
1. [01-domain-history-functions.md](./01-domain-history-functions.md) - Add start_play/end_play functions, remove station filtering
2. [02-history-router.md](./02-history-router.md) - Create FastAPI router with /history/* endpoints
3. [03-player-integration.md](./03-player-integration.md) - Hook history recording into player play/skip/pause
4. [04-frontend-api-update.md](./04-frontend-api-update.md) - Update API client to use new endpoints
5. [05-history-page-update.md](./05-history-page-update.md) - Remove station UI, update to use global history

## Success Criteria
1. Start web mode: `music-minion --web`
2. Navigate to History page - loads without errors
3. Play a track from library
4. Skip after 30 seconds - history shows ~30s duration
5. Play same track again - shows second entry with new timestamp
6. Let track finish - verify full duration recorded
7. Play from comparison mode - both A/B track plays recorded
8. Stats show correct totals including hours listened

## Dependencies
- Existing `radio_history` table schema (already supports NULL station_id)
- Global player implementation (already has play/resume distinction)
- Existing domain functions in `src/music_minion/domain/radio/history.py`

## Schema Migration Required
Add `end_reason` column to `radio_history` table:
```sql
ALTER TABLE radio_history ADD COLUMN end_reason TEXT DEFAULT 'skip';
```
This can be done in task 01 before implementing domain functions.
