# Implement Playlist Builder Dynamic Route

## Files to Modify/Create
- `web/frontend/src/routes/playlist-builder/$playlistId.tsx` (new)

## Implementation Details

Create the dynamic route for the playlist builder with parameter extraction and not-found handling:

```typescript
import { createFileRoute, Link } from '@tanstack/react-router'
import { usePlaylists } from '../../hooks/usePlaylists'
import { PlaylistBuilder as PlaylistBuilderComponent } from '../../pages/PlaylistBuilder'

export const Route = createFileRoute('/playlist-builder/$playlistId')({
  component: PlaylistBuilder,
})

function PlaylistBuilder() {
  const { playlistId } = Route.useParams()
  const { data: playlistsData } = usePlaylists()

  // Parse playlistId to number
  const id = parseInt(playlistId, 10)

  // Look up playlist by ID
  const playlist = playlistsData?.playlists?.find(p => p.id === id)

  // Handle playlist not found
  if (!playlist) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <h1 className="text-2xl font-bold text-slate-100">
          Playlist not found
        </h1>
        <Link
          to="/playlist-builder"
          className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500"
        >
          Back to Selection
        </Link>
      </div>
    )
  }

  // Render the PlaylistBuilder component with the playlist
  return (
    <div>
      <Link
        to="/playlist-builder"
        className="inline-block m-4 text-slate-400 hover:text-slate-200 transition-colors"
      >
        ← Back to Playlists
      </Link>
      <PlaylistBuilderComponent playlistId={playlist.id} />
    </div>
  )
}
```

## Key Features
- **Dynamic Parameter**: `$playlistId` captures URL parameter (numeric ID)
- **Type-Safe Params**: `Route.useParams()` provides typed access
- **Playlist Lookup**: Finds playlist by ID from fetched data
- **Not Found Handling**: Shows error page with back link if playlist doesn't exist
- **Back Navigation**: Link to return to selection page
- **Component Delegation**: Passes `playlistId` to existing PlaylistBuilder component

## Acceptance Criteria
- [ ] Route created at `/playlist-builder/$playlistId`
- [ ] Extracts `playlistId` parameter from URL and parses to number
- [ ] Looks up playlist by ID
- [ ] Shows not-found page for invalid playlist IDs
- [ ] Renders PlaylistBuilder component with `playlistId` prop
- [ ] Back link navigates to `/playlist-builder`

## Testing
- Navigate to `/playlist-builder/123` (should work if playlist exists)
- Navigate to `/playlist-builder/99999` (should show not found)
- Test with valid numeric IDs

## Dependencies
- Task 06 (playlist selection route must exist for back navigation)
- PlaylistBuilder component must exist at `../../pages/PlaylistBuilder`
- PlaylistBuilder must accept `playlistId` prop (see Task 08)
