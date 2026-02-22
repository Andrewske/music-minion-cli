import { createFileRoute } from '@tanstack/react-router';
import { usePlaylists } from '../../hooks/usePlaylists';

export const Route = createFileRoute('/playlist-organizer/')({
  component: PlaylistOrganizerIndex,
});

function PlaylistOrganizerIndex(): JSX.Element {
  const { data: playlists, isLoading } = usePlaylists();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-white/40 text-sm font-sf-mono">Loading playlists...</div>
      </div>
    );
  }

  if (!playlists?.length) {
    return (
      <div className="min-h-screen bg-black font-inter flex flex-col items-center justify-center gap-4">
        <div className="text-white/60 text-sm">No playlists found.</div>
        <div className="text-white/40 text-xs">Create a playlist first.</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black font-inter">
      <div className="max-w-lg mx-auto pt-24 px-6">
        <h1 className="text-sm font-medium text-obsidian-accent tracking-[0.2em] uppercase mb-12">
          Playlist Organizer
        </h1>
        <p className="text-white/40 text-sm">
          Select a playlist from the sidebar to start organizing.
        </p>
      </div>
    </div>
  );
}
