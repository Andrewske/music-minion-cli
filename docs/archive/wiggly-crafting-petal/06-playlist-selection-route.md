# Implement Playlist Selection Route

## Files to Modify/Create
- `web/frontend/src/routes/playlist-builder/index.tsx` (new)

## Implementation Details

Create the playlist selection page at `/playlist-builder` with create and selection functionality:

```typescript
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { usePlaylists } from '../../hooks/usePlaylists'
import { createPlaylist } from '../../api/playlists'

export const Route = createFileRoute('/playlist-builder/')({
  component: PlaylistSelection,
})

function PlaylistSelection() {
  const [newPlaylistName, setNewPlaylistName] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const { data: playlistsData, isLoading, isError, refetch } = usePlaylists()
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (name: string) => createPlaylist(name),
    onSuccess: (playlist) => {
      // Optimistically update cache
      queryClient.setQueryData(['playlists'], (old: any) => ({
        playlists: [...(old?.playlists || []), playlist]
      }))
      // Navigate to builder with type-safe routing (using ID instead of name)
      navigate({
        to: '/playlist-builder/$playlistId',
        params: { playlistId: playlist.id.toString() },
      })
    },
    onError: (error: Error) => {
      setError(error.message)
    },
  })

  const handleCreate = () => {
    if (!newPlaylistName.trim()) {
      setError('Playlist name cannot be empty')
      return
    }
    setError('')
    createMutation.mutate(newPlaylistName)
  }

  const handleSelectPlaylist = (playlistId: number) => {
    navigate({
      to: '/playlist-builder/$playlistId',
      params: { playlistId: playlistId.toString() },
    })
  }

  // Filter local manual playlists
  const playlists = playlistsData?.playlists?.filter(
    (p) => p.library === 'local' && p.type === 'manual'
  ) || [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-slate-400">Loading playlists...</div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <div className="text-rose-400">Failed to load playlists</div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <h1 className="text-3xl font-bold text-slate-100 mb-8">Select Playlist</h1>

      {/* Create New Playlist */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-8">
        <h2 className="text-xl font-semibold text-slate-100 mb-4">Create New Playlist</h2>
        <div className="flex gap-3">
          <input
            type="text"
            value={newPlaylistName}
            onChange={(e) => {
              setNewPlaylistName(e.target.value)
              setError('')
            }}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Enter playlist name..."
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg
              text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2
              focus:ring-indigo-500 focus:border-transparent"
            disabled={createMutation.isPending}
          />
          <button
            onClick={handleCreate}
            disabled={createMutation.isPending || !newPlaylistName.trim()}
            className="px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium
              hover:bg-indigo-500 disabled:bg-slate-700 disabled:cursor-not-allowed
              disabled:text-slate-500 transition-colors"
          >
            {createMutation.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-rose-400 text-sm">{error}</p>
        )}
      </div>

      {/* Playlist Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {playlists.length === 0 ? (
          <div className="col-span-full text-center py-12 text-slate-400">
            No playlists found. Create one to get started!
          </div>
        ) : (
          playlists.map((playlist) => (
            <button
              key={playlist.id}
              onClick={() => handleSelectPlaylist(playlist.id)}
              className="bg-slate-900 border border-slate-800 rounded-xl p-6
                hover:border-indigo-500 hover:bg-slate-800/80 transition-all
                text-left group"
            >
              <h3 className="text-lg font-semibold text-slate-100 mb-2
                group-hover:text-indigo-400 transition-colors">
                {playlist.name}
              </h3>
              <p className="text-slate-400 text-sm">
                {playlist.track_count} {playlist.track_count === 1 ? 'track' : 'tracks'}
              </p>
              {playlist.description && (
                <p className="text-slate-500 text-sm mt-2">{playlist.description}</p>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
```

## Key Features
- **Create Playlist**: Input field + button with validation
- **Filter Logic**: Shows only local manual playlists (library='local', type='manual')
- **Type-Safe Navigation**: Uses TanStack Router's navigate() with typed params
- **Loading State**: Shows loading spinner while fetching playlists
- **Error Handling**: Displays validation and API errors
- **Responsive Grid**: 1 column (mobile), 2 (tablet), 3 (desktop)

## Acceptance Criteria
- [ ] Route created at `/playlist-builder/`
- [ ] Shows create playlist form at top
- [ ] Filters and displays only local manual playlists
- [ ] Click playlist navigates to builder route
- [ ] Create playlist navigates to builder after success
- [ ] Shows loading state while fetching
- [ ] Shows error messages for invalid input
- [ ] Shows "no playlists" message when empty

## Dependencies
- Task 04 (API client must have createPlaylist function)
- Task 05 (route structure must exist)
- `usePlaylists` hook must exist
