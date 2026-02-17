import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { usePlaylists } from '../../hooks/usePlaylists'
import { createPlaylist, deletePlaylist } from '../../api/playlists'
import type { Playlist } from '../../types'

export const Route = createFileRoute('/playlist-builder/')({
  component: PlaylistSelection,
})

function PlaylistSelection() {
  const [newPlaylistName, setNewPlaylistName] = useState('')
  const [error, setError] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const navigate = useNavigate()

  const { data: playlistsData, isLoading, isError, refetch } = usePlaylists()
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (name: string) => createPlaylist(name),
    onSuccess: (playlist) => {
      queryClient.setQueryData<Playlist[]>(
        ['playlists'],
        (old) => [...(old || []), playlist]
      )
      navigate({
        to: '/playlist-builder/$playlistId',
        params: { playlistId: playlist.id.toString() },
      })
    },
    onError: (error: Error) => {
      setError(error.message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (playlistId: number) => deletePlaylist(playlistId),
    onSuccess: (_, deletedId) => {
      queryClient.setQueryData<Playlist[]>(
        ['playlists'],
        (old) => (old || []).filter((p) => p.id !== deletedId)
      )
      setConfirmDeleteId(null)
    },
    onError: (error: Error) => {
      setError(error.message)
      setConfirmDeleteId(null)
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

  // Filter local playlists (both manual and smart)
  const playlists = playlistsData?.filter(
    (p: Playlist) => p.library === 'local'
  ) || [];

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-white/40 text-sm font-sf-mono">Loading...</div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-6">
        <div className="text-white/60 text-sm">Failed to load playlists</div>
        <button
          onClick={() => refetch()}
          className="px-6 py-2 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black transition-colors text-sm tracking-wider"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black font-inter">
      <div className="max-w-lg mx-auto pt-24 px-6">
        <h1 className="text-sm font-medium text-obsidian-accent tracking-[0.2em] uppercase mb-12">
          Select Playlist
        </h1>

        {/* Playlist List */}
        <div className="space-y-px mb-12">
          {playlists.length === 0 ? (
            <p className="text-white/30 text-sm py-4">No playlists found</p>
          ) : (
            playlists.map((playlist: Playlist) => (
              <div
                key={playlist.id}
                className="group border-b border-obsidian-border hover:border-obsidian-accent/50 transition-colors"
              >
                {confirmDeleteId === playlist.id ? (
                  <div className="flex items-center justify-between py-4 px-2 bg-red-900/20">
                    <span className="text-white/70 text-sm">
                      Delete "{playlist.name}"?
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => deleteMutation.mutate(playlist.id)}
                        disabled={deleteMutation.isPending}
                        className="px-3 py-1 text-xs bg-red-600 text-white hover:bg-red-500
                          disabled:opacity-50 transition-colors"
                      >
                        {deleteMutation.isPending ? '...' : 'Delete'}
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="px-3 py-1 text-xs border border-obsidian-border text-white/50
                          hover:text-white transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between py-4">
                    <button
                      onClick={() => handleSelectPlaylist(playlist.id)}
                      className="flex-1 text-left flex items-center gap-3"
                    >
                      <span className="text-white/90 group-hover:text-obsidian-accent transition-colors">
                        {playlist.name}
                      </span>
                      {playlist.type === 'smart' && (
                        <span className="text-[10px] text-obsidian-accent/60 tracking-wider uppercase">
                          Smart
                        </span>
                      )}
                    </button>
                    <div className="flex items-center gap-4">
                      <span className="text-white/20 text-sm font-sf-mono">
                        {playlist.track_count}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setConfirmDeleteId(playlist.id)
                        }}
                        className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400
                          transition-all text-sm px-2"
                        title="Delete playlist"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Create New Playlist */}
        {showCreateForm ? (
          <div className="border-t border-obsidian-border pt-8">
            <h2 className="text-xs text-white/40 tracking-[0.2em] uppercase mb-6">New Playlist</h2>
            <div className="space-y-4">
              <input
                type="text"
                value={newPlaylistName}
                onChange={(e) => {
                  setNewPlaylistName(e.target.value)
                  setError('')
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                placeholder="Name"
                autoFocus
                className="w-full bg-black border border-obsidian-border px-4 py-3
                  text-white placeholder-white/20 text-sm
                  focus:border-obsidian-accent/50 focus:outline-none transition-colors"
                disabled={createMutation.isPending}
              />
              {error && (
                <p className="text-red-400/80 text-xs">{error}</p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={handleCreate}
                  disabled={createMutation.isPending || !newPlaylistName.trim()}
                  className="flex-1 py-2 border border-obsidian-accent text-obsidian-accent text-sm
                    hover:bg-obsidian-accent hover:text-black disabled:opacity-30
                    transition-all tracking-wider"
                >
                  {createMutation.isPending ? '...' : 'Create'}
                </button>
                <button
                  onClick={() => {
                    setShowCreateForm(false)
                    setNewPlaylistName('')
                    setError('')
                  }}
                  className="flex-1 py-2 border border-obsidian-border text-white/40 text-sm
                    hover:text-white transition-colors tracking-wider"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowCreateForm(true)}
            className="w-full py-3 border border-dashed border-obsidian-border
              text-white/30 hover:text-obsidian-accent hover:border-obsidian-accent/50
              transition-colors text-sm tracking-wider"
          >
            + New Playlist
          </button>
        )}
      </div>
    </div>
  );
}
