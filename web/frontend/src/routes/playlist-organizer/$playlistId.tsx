import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { usePlaylists } from '../../hooks/usePlaylists';
import { PlaylistOrganizer } from '../../pages/PlaylistOrganizer';

export const Route = createFileRoute('/playlist-organizer/$playlistId')({
  component: PlaylistOrganizerRoute,
});

function PlaylistOrganizerRoute(): JSX.Element {
  const { playlistId } = Route.useParams();
  const navigate = useNavigate();
  const { data: playlistsData, isLoading } = usePlaylists();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-white/40 text-sm font-sf-mono">Loading...</div>
      </div>
    );
  }

  const numericId = parseInt(playlistId, 10);

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

  const playlist = playlistsData?.find((p) => p.id === numericId);

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
    />
  );
}
