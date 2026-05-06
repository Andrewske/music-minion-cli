# Per-Bucket SoundCloud Sync Button

## Overview
Add a per-bucket sync button to the playlist organizer that bidirectionally syncs a bucket's linked playlist with SoundCloud. Uses pull-then-push semantics: first pulls new tracks from SC into the local playlist, then pushes local additions/removals to SC. Fire-and-forget UX with toast feedback.

## Task Sequence
1. [01-backend-surface-sc-id.md](./01-backend-surface-sc-id.md) - Add `soundcloud_playlist_id` to bucket session query response
2. [02-backend-sync-logic.md](./02-backend-sync-logic.md) - Sync algorithm + `POST /api/buckets/{id}/sync-soundcloud` endpoint
3. [03-frontend-api-and-hook.md](./03-frontend-api-and-hook.md) - TypeScript types, API function, React Query mutation
4. [04-frontend-sync-button.md](./04-frontend-sync-button.md) - RefreshCw button on bucket header + PlaylistOrganizer wiring

## Success Criteria
1. Sync button (RefreshCw icon) appears only on buckets linked to SC-backed playlists
2. Clicking sync pulls new SC tracks into local playlist
3. Clicking sync pushes local additions to SC
4. Clicking sync removes tracks from SC that were removed locally
5. Loading spinner during sync, toast on completion/failure

## Dependencies
- Existing SoundCloud API functions: `add_track_to_playlist`, `remove_track_from_playlist`, `get_playlist_tracks` in `src/music_minion/domain/library/providers/soundcloud/api.py`
- Existing sync utilities: `get_provider_state()`, `update_playlist_last_synced()` in `src/music_minion/domain/playlists/sync.py`
- Bucket-playlist linking already functional
