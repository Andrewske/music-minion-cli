# Smart Playlist Builder Refactoring

## Overview
Unify smart playlist builder with manual playlist builder to share code and have consistent visual design. The smart playlist builder currently has a different theme (slate/purple) and overcomplicated UI (two modes). After this refactoring, both builders share the same obsidian theme and component structure, with smart playlists adding a filter sidebar.

## Key Architectural Decisions (from plan review)
1. **Sessions removed**: No "Begin" screen for manual playlists. Skips are permanent for both types.
2. **No Review mode**: Smart playlists use table navigation + Skip button (no Keep/Previous/Next).
3. **Infinite query for both**: Backend pagination for smart playlist tracks endpoint.
4. **Left-aligned layout**: Both types use left-aligned track display (obsidian style).
5. **Unified hook owns state**: Hook manages sorting, infinite query, mutations.
6. **Feature parity**: Both types get IPC WebSocket, EmojiTrackActions, loop toggle.

## Task Sequence
1. [00-backend-pagination.md](./00-backend-pagination.md) - Add pagination to smart playlist tracks endpoint
2. [01-extract-shared-components.md](./01-extract-shared-components.md) - Extract TrackDisplay, WaveformSection, BuilderActions
3. [02-extend-builder-hook.md](./02-extend-builder-hook.md) - Create unified usePlaylistBuilder hook
4. [03-unify-playlist-builder.md](./03-unify-playlist-builder.md) - Modify PlaylistBuilder to handle smart playlists inline
5. [04-restyle-filter-panel.md](./04-restyle-filter-panel.md) - Update FilterPanel components to obsidian theme
6. [05-cleanup-old-files.md](./05-cleanup-old-files.md) - Delete SmartPlaylistEditor, useSmartPlaylistEditor, session code

## Success Criteria
1. Smart playlist builder looks exactly like manual builder (obsidian theme)
2. Filter panel appears in sidebar for smart playlists
3. Skips are persistent for both playlist types (no sessions)
4. View Skipped dialog works for restoring tracks
5. Both types: Add/Skip buttons, table navigation, IPC hotkeys, emoji reactions, loop toggle
6. Keyboard shortcuts work in both (Space, 0-9, IPC)
7. No TypeScript errors, build succeeds

## Dependencies
- Existing components: WaveformPlayer, TrackQueueTable, EmojiTrackActions, SkippedTracksDialog
- Existing hooks: useIPCWebSocket
- Backend APIs: builder endpoints (refactored), smart playlist filter/skip endpoints
