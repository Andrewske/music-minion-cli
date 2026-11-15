import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { usePlaylists } from '../../hooks/usePlaylists';
import { setLastOrganizerPlaylistId } from '../../lib/lastOrganizerPlaylist';
import { PlaylistOrganizer } from '../../pages/PlaylistOrganizer';
import { useLibraryStore } from '../../stores/libraryStore';

export const Route = createFileRoute('/playlist-organizer/$playlistId')({
  component: PlaylistOrganizerRoute,
});

function PlaylistOrganizerRoute(): JSX.Element {
  const { playlistId } = Route.useParams();
  const navigate = useNavigate();
  const { activeLibrary } = useLibraryStore();
  const { data: playlistsData, isLoading } = usePlaylists(activeLibrary);
  const numericId = parseInt(playlistId, 10);
  const playlist = playlistsData?.find((p) => p.id === numericId);

  // Only remember playlists that actually resolved, so a stale or bad URL
  // never becomes the index route's redirect target.
  const resolvedId = playlist?.id;
  useEffect(() => {
    if (resolvedId !== undefined) setLastOrganizerPlaylistId(resolvedId);
  }, [resolvedId]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-white/40 text-sm font-sf-mono">Loading...</div>
      </div>
    );
  }

  if (isNaN(numericId)) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-6">
        <h1 className="text-white/60 text-sm">Invalid playlist ID</h1>
        <button
          type="button"
          onClick={() => navigate({ to: '/playlist-organizer' })}
          className="px-6 py-2 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black transition-colors text-sm tracking-wider"
        >
          Back
        </button>
      </div>
    );
  }

  if (!playlist) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-6">
        <h1 className="text-white/60 text-sm">Playlist not found</h1>
        <button
          type="button"
          onClick={() => navigate({ to: '/playlist-organizer' })}
          className="px-6 py-2 border border-obsidian-accent text-obsidian-accent
            hover:bg-obsidian-accent hover:text-black transition-colors text-sm tracking-wider"
        >
          Back
        </button>
      </div>
    );
  }

  return (
    <PlaylistOrganizer
      playlistId={playlist.id}
      playlistName={playlist.name}
      playlistType={playlist.type}
      playlistLibrary={playlist.library}
      discoverySource={playlist.discovery_source}
    />
  );
}
