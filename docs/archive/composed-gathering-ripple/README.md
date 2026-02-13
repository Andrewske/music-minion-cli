# Smart Playlist Editor for Web Playlist Builder

## Overview

Extend the web playlist builder to support smart playlists. For smart playlists, the builder becomes a filter editor where users can modify filter rules and see which tracks match - but cannot manually add/remove tracks (membership is automatic).

**Key differences:**
| Aspect | Manual Playlist | Smart Playlist |
|--------|-----------------|----------------|
| Filters | Temporary (session) | Permanent (stored rules) |
| Tracks | Add/skip workflow | View-only, click to preview |
| Session | Required | Not needed |

## Task Sequence

1. [01-backend-smart-filter-endpoints.md](./01-backend-smart-filter-endpoints.md) - Add GET/PUT endpoints for smart playlist filters
2. [02-frontend-api-and-types.md](./02-frontend-api-and-types.md) - Add API functions and TypeScript types
3. [03-frontend-smart-playlist-hook.md](./03-frontend-smart-playlist-hook.md) - Create useSmartPlaylistEditor hook
4. [04-frontend-smart-playlist-editor-component.md](./04-frontend-smart-playlist-editor-component.md) - Create SmartPlaylistEditor component, update PlaylistBuilder
5. [05-frontend-routes-and-selection.md](./05-frontend-routes-and-selection.md) - Update routes to show both playlist types with badges

## Success Criteria

1. **Start the app:** `music-minion --web`
2. **Create a smart playlist** (via CLI: `playlist create --smart "Test Smart"`)
3. **Navigate to playlist builder** - should see both manual and smart playlists with badges
4. **Select smart playlist** - should show filter editor mode (no add/skip buttons)
5. **Add a filter** (e.g., genre = "House") - track list should update to show matches
6. **Click a track** - should play in waveform player
7. **Modify filter** - track list should update dynamically
8. **Verify manual playlists** still work with existing add/skip workflow

## Execution Instructions

1. Execute tasks in numerical order (01 → 05)
2. Each task file contains:
   - Files to modify/create
   - Implementation details
   - Acceptance criteria
   - Dependencies
3. Verify acceptance criteria before moving to next task

## Dependencies

- Existing domain layer: `src/music_minion/domain/playlists/filters.py` has all filter CRUD functions
- Existing backend: `GET /playlists/{id}/tracks` already handles smart playlists via `evaluate_filters()`
- Existing frontend components: `FilterPanel`, `FilterEditor`, `TrackQueueTable`, `WaveformPlayer`
