import { useState } from 'react';
import type { ReactElement } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { ArrowLeft, HardDrive, Music, UserMinus, Users } from 'lucide-react';
import { toast } from 'sonner';
import { useArtist, useArtistLibraryTracks, useUnfollowArtist } from '../hooks/useArtists';
import { usePlayerStore } from '../stores/playerStore';
import { ArtistTrackSections } from '../components/artists/ArtistTrackSections';
import { ArtistConnections } from '../components/artists/ArtistConnections';
import { ConfirmUnfollowDialog } from '../components/artists/ConfirmUnfollowDialog';

type ArtistTab = 'tracks' | 'connections';

export const Route = createFileRoute('/artists_/$artistId')({
  component: ArtistPage,
});

function formatFollowers(n: number | null): string {
  if (n == null) return '';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}): ReactElement {
  return (
    <button
      onClick={onClick}
      className={`font-sf-mono text-xs uppercase tracking-widest pb-2 border-b-2 transition-colors ${
        active
          ? 'text-obsidian-accent border-obsidian-accent'
          : 'text-white/40 border-transparent hover:text-white'
      }`}
    >
      {label}
    </button>
  );
}

function ArtistPage(): ReactElement {
  const { artistId } = Route.useParams();
  const id = Number(artistId);
  const [tab, setTab] = useState<ArtistTab>('tracks');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const unfollowMutation = useUnfollowArtist();
  const { data: detail, isPending: detailPending, error: detailError } = useArtist(
    Number.isFinite(id) ? id : null,
  );
  const { data: tracks, isPending: tracksPending } = useArtistLibraryTracks(
    Number.isFinite(id) ? id : null,
  );
  // Subscribe so the header stays mounted above sections during playback updates.
  usePlayerStore((s) => s.currentTrack?.id);

  if (detailPending || tracksPending) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <span className="font-sf-mono text-sm text-white/40">Loading artist…</span>
      </div>
    );
  }

  if (detailError || !detail) {
    return (
      <div className="min-h-screen bg-black flex flex-col items-center justify-center gap-4">
        <p className="font-sf-mono text-sm text-red-400">
          {detailError instanceof Error ? detailError.message : 'Artist not found'}
        </p>
        <Link to="/artists" className="font-sf-mono text-sm text-white/50 hover:text-white">
          ← Back to artists
        </Link>
      </div>
    );
  }

  const artist = detail.artist;

  const handleUnfollow = (): void => {
    unfollowMutation.mutate(id, {
      onSuccess: () => {
        setConfirmOpen(false);
        toast.success(`Unfollowed ${artist.display_name}`);
      },
      onError: (err) => toast.error(`Unfollow failed: ${err.message}`),
    });
  };

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

        {/* Header */}
        <header className="flex items-center gap-4">
          {artist.avatar_url ? (
            <img
              src={artist.avatar_url}
              alt=""
              className="w-20 h-20 rounded-full object-cover border border-obsidian-border"
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-obsidian-accent/20 to-obsidian-surface flex items-center justify-center">
              <Music className="w-8 h-8 text-white/30" />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="font-inter text-2xl font-semibold text-white tracking-tight truncate">
              {artist.display_name}
            </h1>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 font-sf-mono text-xs text-white/50">
              {artist.follower_count != null && (
                <span className="flex items-center gap-1">
                  <Users className="w-3 h-3" />
                  {formatFollowers(artist.follower_count)}
                </span>
              )}
              <span>{artist.library_track_count} in library</span>
              <span className="text-red-400/80">{artist.sc_liked_count} liked</span>
              <span>{artist.playlist_track_count} in playlists</span>
            </div>
          </div>
          {artist.is_following && (
            <button
              onClick={() => setConfirmOpen(true)}
              disabled={unfollowMutation.isPending}
              className="ml-auto shrink-0 inline-flex items-center gap-1.5 font-sf-mono text-xs uppercase tracking-widest px-3 py-1.5 border border-obsidian-border text-white/50 hover:text-red-400 hover:border-red-400/50 transition-colors disabled:opacity-50"
            >
              <UserMinus className="w-3.5 h-3.5" />
              Unfollow
            </button>
          )}
        </header>

        {/* Tabs */}
        <nav className="flex items-center gap-6 border-b border-obsidian-border">
          <TabButton label="Tracks" active={tab === 'tracks'} onClick={() => setTab('tracks')} />
          <TabButton
            label="Connections"
            active={tab === 'connections'}
            onClick={() => setTab('connections')}
          />
        </nav>

        {tab === 'tracks' ? (
          <>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-sf-mono text-[10px] text-white/40">
              <span className="flex items-center gap-1">
                <HardDrive className="w-3 h-3 text-emerald-400" /> local file
              </span>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> local playlist
              </span>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-400" /> soundcloud playlist
              </span>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" /> spotify playlist
              </span>
            </div>
            <ArtistTrackSections tracks={tracks ?? []} />
          </>
        ) : (
          <ArtistConnections artistId={id} />
        )}
      </div>

      <ConfirmUnfollowDialog
        artist={artist}
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        onConfirm={handleUnfollow}
        isPending={unfollowMutation.isPending}
      />
    </div>
  );
}
