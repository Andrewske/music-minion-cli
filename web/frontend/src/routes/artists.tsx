import type { ReactElement } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { useArtists, useFollowingsSync } from '../hooks/useArtists';
import { ArtistCard } from '../components/artists/ArtistCard';
import { Button } from '../components/ui/button';

export const Route = createFileRoute('/artists')({
  component: ArtistsPage,
});

const DISPLAY_CAP = 500;

// ---------------------------------------------------------------------------
// Loading / Error / Empty states
// ---------------------------------------------------------------------------

function LoadingState(): ReactElement {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <span className="font-sf-mono text-sm text-white/40">Loading artists…</span>
    </div>
  );
}

interface ErrorStateProps {
  error: Error;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps): ReactElement {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-6">
      <div className="max-w-md w-full bg-red-500/5 border border-red-500/20 px-5 py-4 space-y-3">
        <p className="font-sf-mono text-sm text-red-400">{error.message}</p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </div>
  );
}

function EmptyState(): ReactElement {
  const sync = useFollowingsSync();

  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center space-y-4">
        <p className="font-sf-mono text-sm text-white/40">
          No artists found. Run a followings sync or feed sync to populate.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
        >
          {sync.isPending ? 'Syncing…' : 'Sync followings'}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ArtistsPage(): ReactElement {
  const { data: artists, isLoading, error, refetch } = useArtists({});

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (!artists || artists.length === 0) return <EmptyState />;

  const visible = artists.slice(0, DISPLAY_CAP);
  const overflow = artists.length - visible.length;

  return (
    <div className="min-h-screen bg-black px-6 py-8">
      <header className="max-w-7xl mx-auto mb-8">
        <h1 className="font-inter text-3xl font-semibold text-white tracking-tight">Artists</h1>
        <p className="font-sf-mono text-sm text-white/50 mt-1">
          {artists.length} artists · SoundCloud + local library
        </p>
      </header>

      {/* TODO: virtualize if >2000 visible cards */}
      <main className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {visible.map((a) => (
          <ArtistCard key={`${a.id ?? 'local'}-${a.display_name}`} artist={a} />
        ))}
      </main>

      {overflow > 0 && (
        <p className="max-w-7xl mx-auto mt-6 font-sf-mono text-xs text-white/30 text-center">
          …+{overflow} more (use filters to narrow)
        </p>
      )}
    </div>
  );
}
