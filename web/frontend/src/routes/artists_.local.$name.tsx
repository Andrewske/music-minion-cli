import type { ReactElement } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Music } from 'lucide-react';
import { getLocalArtistLibraryTracks } from '../api/artists';
import { ArtistTrackSections } from '../components/artists/ArtistTrackSections';

export const Route = createFileRoute('/artists_/local/$name')({
  component: LocalArtistPage,
});

function LocalArtistPage(): ReactElement {
  const { name } = Route.useParams();

  const { data: tracks, isPending, error } = useQuery({
    queryKey: ['artists', 'local-library-tracks', name],
    queryFn: () => getLocalArtistLibraryTracks(name),
    staleTime: 60 * 1000,
  });

  if (isPending) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <span className="font-sf-mono text-sm text-white/40">Loading artist…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center gap-4">
        <p className="font-sf-mono text-sm text-red-400">
          {error instanceof Error ? error.message : 'Failed to load artist'}
        </p>
        <Link to="/artists" className="font-sf-mono text-sm text-white/50 hover:text-white">
          ← Back to artists
        </Link>
      </div>
    );
  }

  const all = tracks ?? [];
  const likedCount = all.filter((t) => t.is_liked).length;
  const inPlaylistsCount = all.filter((t) => t.playlists.length > 0).length;

  return (
    <div className="min-h-screen bg-black px-4 md:px-6 py-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <Link
          to="/artists"
          className="inline-flex items-center gap-1.5 font-sf-mono text-xs text-white/40 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Artists
        </Link>

        {/* Header — local artist: no SoundCloud profile, counts derived from tracks */}
        <header className="flex items-center gap-4">
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-obsidian-accent/20 to-obsidian-surface flex items-center justify-center">
            <Music className="w-8 h-8 text-white/30" />
          </div>
          <div className="min-w-0">
            <h1 className="font-inter text-2xl font-semibold text-white tracking-tight truncate">
              {name}
            </h1>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 font-sf-mono text-xs text-white/50">
              <span>{all.length} in library</span>
              <span className="text-red-400/80">{likedCount} liked</span>
              <span>{inPlaylistsCount} in playlists</span>
              <span className="text-white/30">local only</span>
            </div>
          </div>
        </header>

        <ArtistTrackSections tracks={all} />
      </div>
    </div>
  );
}
