import { createFileRoute, Link, Navigate } from '@tanstack/react-router';
import { usePlaylists } from '../../hooks/usePlaylists';
import { getLastOrganizerPlaylistId } from '../../lib/lastOrganizerPlaylist';
import { useLibraryStore } from '../../stores/libraryStore';
import type { Playlist } from '../../types';

export const Route = createFileRoute('/playlist-organizer/')({
  component: PlaylistOrganizerIndex,
});

function PlaylistOrganizerIndex(): JSX.Element {
  const { activeLibrary } = useLibraryStore();
  const { data: playlists, isLoading } = usePlaylists(activeLibrary);

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

  // Resume the last organized playlist if it still exists in this library.
  const lastId = getLastOrganizerPlaylistId();
  if (lastId !== null && playlists.some((p) => p.id === lastId)) {
    return (
      <Navigate to="/playlist-organizer/$playlistId" params={{ playlistId: String(lastId) }} replace />
    );
  }

  return <PlaylistPicker playlists={playlists} />;
}

function PlaylistPicker({ playlists }: { playlists: Playlist[] }): JSX.Element {
  // Pinned first in pin order, the rest keep the API's order.
  const pinned = playlists
    .filter((p) => p.pin_order !== null)
    .sort((a, b) => (a.pin_order ?? 0) - (b.pin_order ?? 0));
  const rest = playlists.filter((p) => p.pin_order === null);

  return (
    <div className="min-h-screen bg-black font-inter">
      <div className="max-w-lg mx-auto pt-24 pb-12 px-6">
        <h1 className="text-sm font-medium text-obsidian-accent tracking-[0.2em] uppercase mb-8">
          Playlist Organizer
        </h1>
        <p className="text-white/40 text-sm mb-6">Pick a playlist to organize.</p>
        <ul className="flex flex-col divide-y divide-white/5 border-y border-white/5">
          {[...pinned, ...rest].map((p) => (
            <li key={p.id}>
              <Link
                to="/playlist-organizer/$playlistId"
                params={{ playlistId: String(p.id) }}
                className="flex items-center justify-between gap-4 py-3 text-sm text-white/80
                  hover:text-obsidian-accent transition-colors"
              >
                <span className="truncate">{p.name}</span>
                <span className="shrink-0 text-xs text-white/30 font-sf-mono">{p.track_count}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
