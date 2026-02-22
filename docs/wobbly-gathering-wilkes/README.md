# Playlist Bucket Organizer

Triage page for organizing playlist tracks into energy-level buckets with automatic emoji tagging.

## Overview

A new web page that allows rapid playlist organization by:
- Playing through tracks and assigning them to buckets via keyboard shortcuts (Shift+1-0)
- Each bucket can have an emoji that auto-applies to all tracks in it
- Drag-and-drop reordering within buckets
- Final "Apply Order" flattens buckets into playlist order

## Task Sequence

1. [01-database-migration.md](./01-database-migration.md) - Modify track_emojis to allow duplicates + create bucket tables
2. [02-emoji-source-type-updates.md](./02-emoji-source-type-updates.md) - Update all emoji operations with source_type tracking
3. [03-bucket-backend-api.md](./03-bucket-backend-api.md) - Create FastAPI router for bucket sessions and operations
4. [04-frontend-api-client.md](./04-frontend-api-client.md) - TypeScript API client for buckets
5. [05-organizer-hook.md](./05-organizer-hook.md) - React Query hook for playlist organizer state
6. [06-organizer-routes.md](./06-organizer-routes.md) - TanStack Router routes and sidebar integration
7. [07-organizer-page.md](./07-organizer-page.md) - Main page with track table and keyboard handling
8. [08-bucket-components.md](./08-bucket-components.md) - Bucket UI with drag-and-drop reordering

## Success Criteria

End-to-end verification:

1. **Navigate** to `/playlist-organizer/{playlistId}` via sidebar
2. **Create bucket** with name and emoji (e.g., "🔥 Peak Energy")
3. **Play a track** from the unassigned list
4. **Press Shift+1** to assign to first bucket
5. **Verify**: Track appears in bucket, emoji added to track, player advances
6. **Assign more tracks** to multiple buckets
7. **Reorder** tracks within bucket via drag-and-drop
8. **Click "Apply Order"**
9. **Verify**: Original playlist now ordered by bucket priority

## Dependencies

- @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities (for drag-and-drop)
- Existing: TanStack Query, TanStack Router, emoji-mart, Zustand

## Key Files

### Backend
- `src/music_minion/core/database.py` - Schema migration
- `web/backend/routers/buckets.py` - API endpoints
- `web/backend/queries/buckets.py` - Database queries
- `web/backend/queries/emojis.py` - Updated for source_type

### Frontend
- `web/frontend/src/api/buckets.ts` - API client
- `web/frontend/src/hooks/usePlaylistOrganizer.ts` - State management
- `web/frontend/src/pages/PlaylistOrganizer.tsx` - Main page
- `web/frontend/src/components/organizer/*.tsx` - UI components
