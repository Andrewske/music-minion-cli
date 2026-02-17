---
task: 03-unify-playlist-builder
status: pending
depends:
  - 01-extract-shared-components
  - 02-extend-builder-hook
files:
  - path: web/frontend/src/pages/PlaylistBuilder.tsx
    action: modify
---

# Unify PlaylistBuilder Component

## Context
PlaylistBuilder currently delegates to SmartPlaylistEditor for smart playlists. Modify it to handle both playlist types inline, using the extracted shared components and unified hook. Sessions are removed - no "Begin" screen.

## Files to Modify/Create
- `web/frontend/src/pages/PlaylistBuilder.tsx` (modify)

## Implementation Details

### Remove Smart Delegation
Delete lines 21-23 that route to SmartPlaylistEditor:
```typescript
// REMOVE THIS:
if (playlistType === 'smart') {
  return <SmartPlaylistEditor playlistId={playlistId} playlistName={playlistName} />;
}
```

### Use Unified Hook
```typescript
const builder = usePlaylistBuilder(playlistId, playlistType);
```

### No "Begin" Screen
Sessions are removed. Both playlist types render the builder immediately.
Delete the entire "Begin" screen conditional block.

### Layout: Smart Playlist with Sidebar
For smart playlists, use a two-column layout:
```typescript
{playlistType === 'smart' ? (
  <div className="flex gap-8">
    {/* Sidebar */}
    <aside className="w-64 shrink-0">
      <FilterPanel filters={builder.filters} onUpdate={...} />
      <button onClick={() => setIsSkippedDialogOpen(true)}>
        View Skipped ({builder.skippedTracks?.length ?? 0})
      </button>
    </aside>
    {/* Main content */}
    <main className="flex-1">
      {/* Track, Waveform, Actions, Queue */}
    </main>
  </div>
) : (
  // Full width for manual
  <main>...</main>
)}
```

### Conditional Action Buttons
Use BuilderActions component:
```typescript
<BuilderActions
  playlistType={playlistType}
  onAdd={playlistType === 'manual' ? handleAdd : undefined}
  onSkip={handleSkip}
  isAddingTrack={builder.isAddingTrack}
  isSkippingTrack={builder.isSkippingTrack}
/>
```

### Skipped Dialog for Both Types
Both manual and smart playlists have permanent skips, so both need the dialog:
```typescript
<SkippedTracksDialog
  open={isSkippedDialogOpen}
  onClose={() => setIsSkippedDialogOpen(false)}
  tracks={builder.skippedTracks ?? []}
  onUnskip={(trackId) => builder.unskipTrack.mutate(trackId)}
  isUnskipping={builder.unskipTrack.isPending}
/>
```

### IPC WebSocket for Both Types
Both playlist types get hotkey support:
```typescript
useIPCWebSocket({
  onBuilderAdd: () => {
    if (playlistType === 'manual' && currentTrack && !builder.isAddingTrack && !builder.isSkippingTrack) {
      handleAdd();
    }
  },
  onBuilderSkip: () => {
    if (currentTrack && !builder.isAddingTrack && !builder.isSkippingTrack) {
      handleSkip();
    }
  }
});
```

### Use Extracted Components
Replace inline JSX with:
- `<TrackDisplay track={currentTrack} onEmojiUpdate={handleTrackEmojiUpdate} />`
- `<WaveformSection track={currentTrack} isPlaying={isPlaying} loopEnabled={loopEnabled} ... />`
- `<BuilderActions playlistType={playlistType} ... />`

### Table Navigation
Both types use TrackQueueTable for navigation. Clicking a row previews that track:
```typescript
<TrackQueueTable
  tracks={builder.tracks}
  queueIndex={queueIndex}
  nowPlayingId={nowPlayingTrack?.id ?? null}
  onTrackClick={(track) => setNowPlayingTrack(track)}
  sorting={builder.sorting}
  onSortingChange={builder.setSorting}
  onLoadMore={() => builder.fetchNextPage()}
  hasMore={builder.hasNextPage}
  isLoadingMore={builder.isFetchingNextPage}
/>
```

## Verification
1. Both playlist types render immediately (no "Begin" screen)
2. Smart playlist renders with filter sidebar
3. Smart playlist shows Skip button only (no Add)
4. Manual playlist shows Add + Skip buttons
5. View Skipped dialog works for both types
6. IPC hotkeys work for both types
7. Table navigation works for both types
8. Visual styling matches (obsidian theme throughout)
