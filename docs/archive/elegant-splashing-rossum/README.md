# Global Player with Cross-Device Control

Replace Icecast/Liquidsoap radio stack with a frontend-driven global player.

## Overview

The existing radio architecture uses Docker containers (Icecast + Liquidsoap) to stream audio. This plan replaces it with a simpler frontend-driven player that:

- Persists across all pages (global PlayerBar)
- Supports cross-device control (Spotify Connect style)
- Uses browser-based scheduling instead of server-side orchestration
- Reduces complexity and resource usage

## Task Sequence

1. [01-backend-player-api.md](./01-backend-player-api.md) - Create `/api/player/` endpoints, device registry, WebSocket state sync
2. [02-frontend-player-store.md](./02-frontend-player-store.md) - Zustand playerStore with device management and audio handling
3. [03-player-components.md](./03-player-components.md) - PlayerBar, DeviceSelector, update UpNext to use store
4. [04-queue-and-context.md](./04-queue-and-context.md) - Wire up track clicks everywhere
5. [05-stations-and-schedule.md](./05-stations-and-schedule.md) - Simplify stations to "quick play" presets (schedule mode deferred)
6. [06-home-page.md](./06-home-page.md) - Replace RadioPage with new home layout
7. [07-archive-and-cleanup.md](./07-archive-and-cleanup.md) - Archive radio code, delete deprecated files, update docs

## Success Criteria

- [ ] Single device: Click playlist → tracks play in order
- [ ] Shuffle: Toggle works, backend returns shuffled queue
- [ ] Cross-tab: Open two tabs, state syncs between them
- [ ] Cross-device: Control desktop playback from phone
- [ ] Device selector: Shows all connected devices, can switch active
- [ ] Navigation: Player bar stays visible across all pages
- [ ] Archive: Radio code preserved in `docs/archive/radio-stack/`

## Dependencies

- Existing WebSocket infrastructure (`useSyncWebSocket.ts`, `sync_manager.py`)
- Existing station/playlist models
- shadcn/ui components (Button, Slider, DropdownMenu)

## Key Design Decisions

- **Shuffle on backend**: Client sends `shuffle: true`, backend returns shuffled queue (no client-side shuffle state)
- **Click = replace queue**: Clicking any track replaces entire queue with that context
- **Position interpolation**: No position broadcasts - clients compute position from `trackStartedAt` timestamp with clock sync offset
- **Clock sync**: Server includes `server_time` in playback broadcasts, clients compute offset
- **Device grace period**: 30 seconds before marking device as disconnected, then auto-pause
- **No optimistic updates**: Wait for WebSocket confirmation before updating UI state
- **Playlists are source-specific**: No mixing local/youtube/etc within a playlist
- **Multi-source streaming**: Local files served directly, SoundCloud redirects to `source_url`
- **Gapless playback hook**: `preloadNextTrack()` stub ready for future implementation

## Known v1 Limitations

- **In-memory state**: Server restart clears playback state (queue, position)
- **Shuffle toggle interruption**: Toggling shuffle resets track position to 0
