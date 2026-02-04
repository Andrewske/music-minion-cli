# Frontend: Routes and Playlist Selection

## Files to Modify/Create
- `web/frontend/src/routes/playlist-builder/index.tsx` (modify)
- `web/frontend/src/routes/playlist-builder/$playlistId.tsx` (modify)

## Implementation Details

### Playlist Selection Page (`index.tsx`)

Update to show both manual and smart playlists with visual distinction:

```tsx
// Remove the filter that excludes smart playlists (around line 57-58)
// OLD:
const playlists = playlistsData?.filter(
  (p: Playlist) => p.library === 'local' && p.type === 'manual'
) || [];

// NEW:
const playlists = playlistsData?.filter(
  (p: Playlist) => p.library === 'local'
) || [];

// In the playlist card rendering, add a badge:
<button
  key={playlist.id}
  onClick={() => handleSelectPlaylist(playlist.id)}
  className="bg-slate-900 border border-slate-800 rounded-xl p-6
    hover:border-indigo-500 hover:bg-slate-800/80 transition-all
    text-left group"
>
  <div className="flex items-center gap-2 mb-2">
    <h3 className="text-lg font-semibold text-slate-100
      group-hover:text-indigo-400 transition-colors">
      {playlist.name}
    </h3>
    {/* Type badge */}
    <span className={`text-xs px-2 py-0.5 rounded-full ${
      playlist.type === 'smart'
        ? 'bg-purple-600 text-purple-100'
        : 'bg-slate-700 text-slate-300'
    }`}>
      {playlist.type === 'smart' ? 'Smart' : 'Manual'}
    </span>
  </div>
  <p className="text-slate-400 text-sm">
    {playlist.track_count} {playlist.track_count === 1 ? 'track' : 'tracks'}
  </p>
  {playlist.description && (
    <p className="text-slate-500 text-sm mt-2">{playlist.description}</p>
  )}
</button>
```

Note: Keep "Create New Playlist" section for manual playlists only. Smart playlists are created via CLI.

### Builder Route (`$playlistId.tsx`)

Pass the playlist type to the component:

```tsx
function PlaylistBuilder() {
  const { playlistId } = Route.useParams()
  const { data: playlistsData, isLoading } = usePlaylists()

  // ... existing loading/error handling ...

  const playlist = playlistsData?.find(p => p.id === id)

  if (!playlist) {
    // ... existing not found handling ...
  }

  return (
    <div>
      <Link
        to="/playlist-builder"
        className="inline-block m-4 text-slate-400 hover:text-slate-200 transition-colors"
      >
        ← Back to Playlists
      </Link>
      <PlaylistBuilderComponent
        playlistId={playlist.id}
        playlistName={playlist.name}
        playlistType={playlist.type}  // Add this prop
      />
    </div>
  )
}
```

## Acceptance Criteria
- [ ] Playlist selection shows both manual and smart playlists
- [ ] Smart playlists have purple "Smart" badge
- [ ] Manual playlists have gray "Manual" badge
- [ ] Clicking smart playlist navigates to builder route
- [ ] Builder route passes `playlist.type` to component
- [ ] "Create New Playlist" section only creates manual playlists

## Dependencies
- Task 04: PlaylistBuilder must accept `playlistType` prop
