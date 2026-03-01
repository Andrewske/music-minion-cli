# Library Switcher Implementation

## Overview

Add a library switcher to the web UI sidebar that allows switching between "Local" and "SoundCloud" libraries. SoundCloud tracks are synced as separate records that can be browsed and streamed independently from local tracks.

**Key design decisions:**
- Composite unique constraint on `(source, soundcloud_id)` allows both local and SC tracks with the same SoundCloud ID to coexist
- Default to Local library, no "All" option - libraries stay strictly separate
- Preseed likes from existing `soundcloud-discovery` cache, then delta sync only
- Provider interface for future Spotify support

## Task Sequence

1. [01-database-migration.md](./01-database-migration.md) - Migrate to composite unique indexes
2. [02-backend-playlist-filtering.md](./02-backend-playlist-filtering.md) - Add library filter to playlists API + SC streaming
3. [03-backend-soundcloud-sync.md](./03-backend-soundcloud-sync.md) - Provider interface + preseed script + sync endpoint
4. [04-frontend-library-switcher.md](./04-frontend-library-switcher.md) - Library store + switcher + streaming indicator
5. [05-settings-sync-button.md](./05-settings-sync-button.md) - Sync button with last_synced_at + toast

**Deferred:**
- [deferred/07-update-enrich-metadata-skill.md](./deferred/07-update-enrich-metadata-skill.md) - Remove deletion logic (separate PR)

## Success Criteria

End-to-end verification:

1. **Migration works**: Schema version is 47, both sources can have same `soundcloud_id`
2. **Preseed works**: Run script, 6731 likes imported from cache
3. **Sync works**: Click sync in settings, delta fetches only new likes
4. **Switcher works**: Library dropdown changes visible playlists (default: Local)
5. **Playback works**: SC tracks stream via SC API (fast) or yt-dlp (fallback)
6. **Indicators work**: SC tracks show ☁️ streaming indicator
7. **Status works**: Last synced timestamp shown in settings

## Dependencies

- SoundCloud authentication must be configured (`library auth soundcloud`)
- Web mode (`music-minion --web`) for frontend testing
- Existing SoundCloud API functions in `providers/soundcloud/api.py`
- `likes.parquet` from `~/coding/soundcloud-discovery/.cache/` for preseed

## Implementation Order

```
01-database-migration
       │
       ├──────────────────┐
       ▼                  ▼
02-backend-playlist   03-backend-soundcloud-sync
       │                  │
       └────────┬─────────┘
                ▼
    04-frontend-library-switcher
                │
                ▼
    05-settings-sync-button
```

## Key Files

**New files:**
- `src/music_minion/domain/library/providers/base.py` - Provider interface
- `scripts/preseed_soundcloud_likes.py` - One-time import script
- `web/frontend/src/stores/libraryStore.ts` - Library state
- `web/frontend/src/components/sidebar/SidebarLibrarySwitcher.tsx` - Dropdown

**Modified files:**
- `src/music_minion/core/database.py` - Composite unique indexes
- `web/backend/routers/playlists.py` - Library filter param
- `web/backend/routers/tracks.py` - SC API streaming
- `web/backend/routers/soundcloud.py` - Sync endpoint + status
- `web/frontend/src/hooks/usePlaylists.ts` - Library param
- `web/frontend/src/components/tracks/TrackRow.tsx` - Streaming indicator
