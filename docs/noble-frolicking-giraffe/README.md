# SoundCloud Playlist Import

Import SoundCloud playlists by matching tracks to local library, reviewing low-confidence matches, and creating a local playlist. Optionally sync local order back to SoundCloud.

## Overview

**User Flow:**
1. Select SoundCloud playlist from dropdown
2. System matches tracks using TF-IDF (~3s synchronous)
3. High-confidence matches (≥0.85) auto-approved
4. Review only low-confidence matches, fix via search or mark missing
5. Confirm summary and create local playlist
6. Later: reorder local playlist, sync back to SoundCloud

## Task Sequence

1. [01-backend-track-search.md](./01-backend-track-search.md) - Track search endpoint for autocomplete
2. [02-backend-soundcloud-api.md](./02-backend-soundcloud-api.md) - List playlists, match tracks, create playlist endpoints
3. [03-frontend-settings-tab.md](./03-frontend-settings-tab.md) - Add SoundCloud tab to Settings page
4. [04-frontend-import-wizard.md](./04-frontend-import-wizard.md) - Main import wizard with match review UI
5. [05-playlist-sync.md](./05-playlist-sync.md) - Sync button on playlist page to reorder SoundCloud

## Success Criteria

End-to-end verification:

1. Start web mode: `music-minion --web`
2. Navigate to `/settings?tab=soundcloud`
3. Select a SoundCloud playlist with known tracks
4. Verify auto-approve shows correct count (matches ≥0.85)
5. Fix at least one low-confidence match via search
6. Mark at least one track as missing
7. Create playlist with custom name
8. Verify playlist appears in library with correct tracks
9. Reorder playlist, click "Sync to SoundCloud"
10. Verify SoundCloud playlist order matches local

## Dependencies

- SoundCloud authentication must be configured (via CLI `sync soundcloud` first)
- Local library must have tracks to match against
- `sklearn` for TF-IDF (already installed)

## Performance Notes

- Matching is synchronous (~3s for 100 tracks)
- Playlists over 300 tracks may take 10+ seconds to match
- No progress indicator during matching (acceptable for MVP)

## Key Decisions

- **Synchronous matching** (no job polling) - 3s for 100 tracks is acceptable
- **Local component state** with `useReducer` (no Zustand store)
- **Auto-approve ≥0.85 confidence** - only review low-confidence
- **Sync lives on playlist page** - not part of import wizard
