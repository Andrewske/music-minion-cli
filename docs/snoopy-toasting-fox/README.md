# Bucket-to-Playlist Linking

Link buckets in the playlist organizer to actual playlists for bidirectional sync.

## Overview

This feature allows buckets in the playlist organizer to be linked to real playlists. When a track is assigned to a linked bucket, it's automatically added to the linked playlist. When the organizer loads, buckets show tracks from linked playlists that also exist in the parent playlist being organized.

**Key behaviors:**
- Tracks can be in multiple buckets (no longer exclusive)
- Click bucket to toggle track assignment (click again to remove)
- Bucket shows 🔗 icon + linked playlist name
- Forward sync: assign track to linked bucket → track added to linked playlist

**Deferred to v2:**
- Inverse sync: external playlist changes reflected on organizer load

## Task Sequence

1. [01-database-migration.md](./01-database-migration.md) - Add `bucket_playlist_links` table
2. [02-backend-queries.md](./02-backend-queries.md) - Link/unlink queries, sync functions, multi-bucket support
3. [03-backend-api.md](./03-backend-api.md) - Link endpoints, updated response models
4. [04-frontend-types-api.md](./04-frontend-types-api.md) - TypeScript types and API functions
5. [05-frontend-hook.md](./05-frontend-hook.md) - Multi-bucket mutations, link mutation
6. [06-bucket-edit-popup.md](./06-bucket-edit-popup.md) - Playlist selector + header indicator (merged with 07)
7. ~~[07-bucket-header-indicator.md](./07-bucket-header-indicator.md)~~ - *Merged into 06*
8. [08-toggle-behavior.md](./08-toggle-behavior.md) - Click-to-toggle bucket assignment
9. ~~[09-session-loading.md](./09-session-loading.md)~~ - *Deferred to v2 (inverse sync)*

## Success Criteria

End-to-end verification:

1. **Setup**: Have two playlists - "EDM" (parent) and "Dubstep" (target to link)
2. **Link bucket**: Open organizer for EDM, create bucket "dubstep", edit it, link to "Dubstep" playlist
3. **Visual indicator**: Bucket header shows 🔗 Dubstep
4. **Forward sync**: Assign a track to the dubstep bucket → verify it appears in "Dubstep" playlist
5. **Toggle**: Click dubstep bucket when track is assigned → track removed from bucket AND "Dubstep" playlist
6. **Multi-bucket**: Assign track to bucket A, then bucket B → track shows in both
7. **Delete linked playlist**: Delete "Dubstep" playlist → bucket becomes unlinked, keeps local assignments

**Deferred to v2:**
- Inverse sync: Add a track to "Dubstep" playlist directly → refresh organizer → track appears in dubstep bucket

## Dependencies

- SQLite database (existing)
- FastAPI backend (existing)
- React frontend with TanStack Query (existing)
- shadcn/ui components for Select/Combobox (existing or add)
