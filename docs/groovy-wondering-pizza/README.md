# Smart Playlist Builder Refactoring

## Overview
Unify smart playlist builder with manual playlist builder to share code and have consistent visual design. The smart playlist builder currently has a different theme (slate/purple) and overcomplicated UI (two modes). After this refactoring, both builders share the same obsidian theme and component structure, with smart playlists adding a filter sidebar.

## Task Sequence
1. [01-extract-shared-components.md](./01-extract-shared-components.md) - Extract TrackDisplay, WaveformSection, BuilderActions
2. [02-extend-builder-hook.md](./02-extend-builder-hook.md) - Extend useBuilderSession to handle both playlist types
3. [03-unify-playlist-builder.md](./03-unify-playlist-builder.md) - Modify PlaylistBuilder to handle smart playlists inline
4. [04-restyle-filter-panel.md](./04-restyle-filter-panel.md) - Update FilterPanel components to obsidian theme
5. [05-cleanup-old-files.md](./05-cleanup-old-files.md) - Delete SmartPlaylistEditor and hook

## Success Criteria
1. Smart playlist builder looks exactly like manual builder (obsidian theme)
2. Filter panel appears in sidebar for smart playlists
3. Skip is persistent (tracks stay skipped across sessions)
4. View Skipped dialog works for restoring tracks
5. Manual builder unchanged (Begin session, Add/Skip, queue navigation)
6. Keyboard shortcuts work in both (Space, 0-9)
7. No TypeScript errors, build succeeds

## Dependencies
- Existing components: WaveformPlayer, TrackQueueTable, EmojiTrackActions, SkippedTracksDialog
- Existing hooks: useBuilderSession, useIPCWebSocket
- Backend APIs: builder endpoints, smart playlist filter/skip endpoints
