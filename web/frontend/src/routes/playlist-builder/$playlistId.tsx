import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { usePlaylists } from '../../hooks/usePlaylists'
import { ObsidianBuilderMain } from '../../components/designs/ObsidianMinimalBuilder'
import { SmartPlaylistEditor } from '../../pages/SmartPlaylistEditor'

export const Route = createFileRoute('/playlist-builder/$playlistId')({
  component: PlaylistBuilder,
})

function PlaylistBuilder() {
  const { playlistId } = Route.useParams()
  const navigate = useNavigate()
  const { data: playlistsData, isLoading } = usePlaylists()

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-white/40 text-sm font-sf-mono">Loading...</div>
      </div>
    )
  }

  // Parse playlistId to number
  const id = parseInt(playlistId, 10)

  // Handle invalid playlist ID
  if (isNaN(id)) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-6">
        <h1 className="text-white/60 text-sm">Invalid playlist ID</h1>
        <button
          onClick={() => navigate({ to: '/playlist-builder' })}
          className="px-6 py-2 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black transition-colors text-sm tracking-wider"
        >
          Back
        </button>
      </div>
    )
  }

  // Look up playlist by ID
  const playlist = playlistsData?.find(p => p.id === id)

  // Handle playlist not found
  if (!playlist) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-6">
        <h1 className="text-white/60 text-sm">Playlist not found</h1>
        <button
          onClick={() => navigate({ to: '/playlist-builder' })}
          className="px-6 py-2 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black transition-colors text-sm tracking-wider"
        >
          Back
        </button>
      </div>
    )
  }

  // Route smart playlists to their editor
  if (playlist.type === 'smart') {
    return (
      <div className="min-h-screen bg-black font-inter">
        <header className="border-b border-obsidian-border px-8 py-4">
          <div className="flex items-center justify-between max-w-6xl mx-auto">
            <button
              onClick={() => navigate({ to: '/playlist-builder' })}
              className="text-white/40 hover:text-obsidian-accent transition-colors text-sm"
            >
              &larr; Back
            </button>
            <span className="text-white/60 text-sm font-sf-mono">{playlist.name}</span>
            <div className="w-12" />
          </div>
        </header>
        <SmartPlaylistEditor playlistId={playlist.id} playlistName={playlist.name} />
      </div>
    )
  }

  // Render the Obsidian builder for manual playlists
  return (
    <ObsidianBuilderMain
      playlistId={playlist.id}
      playlistName={playlist.name}
      onBack={() => navigate({ to: '/playlist-builder' })}
    />
  )
}
