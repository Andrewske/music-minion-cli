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
PlaylistBuilder currently delegates to SmartPlaylistEditor for smart playlists. Modify it to handle both playlist types inline, using the extracted shared components and extended hook.

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

### Use Extended Hook
```typescript
const builder = useBuilderSession(playlistId, playlistType);
```

### Conditional "Begin" Screen
Only show for manual playlists:
```typescript
if (playlistType === 'manual' && builder.needsSession) {
  return <BeginScreen ... />;
}
```

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

### Add Skipped Dialog for Smart Playlists
Import and render SkippedTracksDialog:
```typescript
{playlistType === 'smart' && (
  <SkippedTracksDialog
    open={isSkippedDialogOpen}
    onClose={() => setIsSkippedDialogOpen(false)}
    tracks={builder.skippedTracks ?? []}
    onUnskip={(trackId) => builder.unskipTrack?.mutate(trackId)}
    isUnskipping={builder.unskipTrack?.isPending}
  />
)}
```

### Use Extracted Components
Replace inline JSX with:
- `<TrackDisplay track={currentTrack} onEmojiUpdate={handleTrackEmojiUpdate} />`
- `<WaveformSection track={currentTrack} isPlaying={isPlaying} ... />`
- `<BuilderActions playlistType={playlistType} ... />`

## Verification
1. Manual playlist flow works exactly as before (no regression)
2. Smart playlist renders with filter sidebar
3. Smart playlist shows Skip button only (no Add)
4. View Skipped dialog opens and allows restoring tracks
5. Visual styling matches (obsidian theme throughout)
