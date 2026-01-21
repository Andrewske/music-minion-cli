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
  const playlist = playlistsData?.find(p => p.id === id)

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
