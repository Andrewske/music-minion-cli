import type { ReactElement } from 'react';
import { useState, useMemo } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { toast } from 'react-toastify';
import { useArtists, useFollowingsSync, useUnfollowArtist } from '../hooks/useArtists';
import type { ArtistStats } from '../api/artists';
import { ArtistCard } from '../components/artists/ArtistCard';
import { ArtistDetailDialog } from '../components/artists/ArtistDetailDialog';
import { ConfirmUnfollowDialog } from '../components/artists/ConfirmUnfollowDialog';
import { ParetoBanner } from '../components/artists/ParetoBanner';
import { ArtistFiltersBar } from '../components/artists/ArtistFiltersBar';
import { ChipVisibilityMenu } from '../components/artists/ChipVisibilityMenu';
import { SyncStatusHeader } from '../components/artists/SyncStatusHeader';
import { Button } from '../components/ui/button';
import { SuggestionsView } from '../components/follow-suggestions/SuggestionsView';
import { UnfollowView } from '../components/unfollow-suggestions/UnfollowView';
import { useArtistViewStore, useVisibleChips } from '../stores/artistViewStore';

export type ArtistsTab = 'following' | 'suggestions' | 'unfollow';

export type ArtistsSearch = {
  /** Omitted for the default following tab. */
  tab?: ArtistsTab;
};

export const Route = createFileRoute('/artists')({
  component: ArtistsPage,
  validateSearch: (search: Record<string, unknown>): ArtistsSearch => ({
    tab: search.tab === 'suggestions' || search.tab === 'unfollow' ? search.tab : undefined,
  }),
});

const DISPLAY_CAP = 500;

// ---------------------------------------------------------------------------
// Loading / Error / Empty states
// ---------------------------------------------------------------------------

function LoadingState(): ReactElement {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
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
    <div className="min-h-[60vh] flex items-center justify-center px-6">
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
    <div className="min-h-[60vh] flex items-center justify-center px-6">
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
// Tabs
// ---------------------------------------------------------------------------

function ArtistsTabs({ tab, onChange }: { tab: ArtistsTab; onChange: (tab: ArtistsTab) => void }): ReactElement {
  return (
    <div role="tablist" aria-label="Artists view" className="inline-flex items-center rounded-full border border-obsidian-border p-0.5">
      {([
        ['following', 'Following'],
        ['suggestions', 'Suggestions'],
        ['unfollow', 'Unfollow'],
      ] as const).map(([value, label]) => (
        <button
          key={value}
          type="button"
          role="tab"
          aria-selected={tab === value}
          onClick={() => onChange(value)}
          className={`rounded-full px-3 py-1 text-xs focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-obsidian-accent ${
            tab === value ? 'bg-obsidian-accent/20 text-obsidian-accent' : 'text-white/60 hover:text-white'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ArtistsPage(): ReactElement {
  const { tab = 'following' } = Route.useSearch();
  const navigate = useNavigate({ from: '/artists' });
  const setTab = (next: ArtistsTab): void => {
    void navigate({ search: { tab: next === 'following' ? undefined : next } });
  };

  return (
    <div className="min-h-screen bg-black">
      <div className="max-w-7xl mx-auto px-6 pt-6">
        <ArtistsTabs tab={tab} onChange={setTab} />
      </div>
      {tab === 'following' ? (
        <FollowingView />
      ) : (
        <div className="px-6 py-6">
          {tab === 'suggestions' ? <SuggestionsView /> : <UnfollowView />}
        </div>
      )}
    </div>
  );
}

function FollowingView(): ReactElement {
  // Filters/sort live in the artist view store so they survive navigating
  // to an artist page and back.
  const { search, setSearch, source, setSource, sort, setSort } = useArtistViewStore();
  const [paretoIds, setParetoIds] = useState<Set<number> | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [confirmArtist, setConfirmArtist] = useState<ArtistStats | null>(null);
  const unfollowMut = useUnfollowArtist();
  const visibleChips = useVisibleChips();

  const { data: artists, isPending, isPlaceholderData, error, refetch } = useArtists({ source, sort });

  const visibleArtists = useMemo(() => {
    let list = artists ?? [];
    if (paretoIds !== null) list = list.filter((a) => a.id != null && paretoIds.has(a.id));
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (a) =>
          a.display_name.toLowerCase().includes(q) ||
          (a.slug ?? '').toLowerCase().includes(q),
      );
    }
    return list.slice(0, DISPLAY_CAP);
  }, [artists, paretoIds, search]);

  if (isPending && !artists) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (!artists || artists.length === 0) return <EmptyState />;

  const overflow = (artists.length > DISPLAY_CAP && paretoIds === null && !search.trim())
    ? artists.length - DISPLAY_CAP
    : 0;

  return (
    <div className="px-6 pt-4 pb-8">
      <header className="max-w-7xl mx-auto mb-8">
        <h1 className="font-inter text-3xl font-semibold text-white tracking-tight">Artists</h1>
        <p className="font-sf-mono text-sm text-white/50 mt-1">
          {artists.length} artists · SoundCloud + local library
        </p>
      </header>

      <div className="max-w-7xl mx-auto">
        <SyncStatusHeader />
        <ParetoBanner onReview={(ids) => setParetoIds(new Set(ids))} />

        <ArtistFiltersBar
          search={search}
          onSearchChange={setSearch}
          source={source}
          onSourceChange={setSource}
          sort={sort}
          onSortChange={setSort}
          paretoActive={paretoIds !== null}
          onParetoClear={() => setParetoIds(null)}
          paretoCount={paretoIds?.size ?? 0}
          resultCount={visibleArtists.length}
          trailingSlot={<ChipVisibilityMenu />}
        />
      </div>

      {/* TODO: virtualize if >2000 visible cards */}
      <main className={`max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4 transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
        {visibleArtists.map((a) => (
          <ArtistCard
            key={`${a.id ?? 'local'}-${a.display_name}`}
            artist={a}
            visibleChips={visibleChips}
            onDetails={(id) => setDetailId(id)}
            onUnfollow={(id) => {
              const found = artists?.find((x) => x.id === id);
              if (found !== undefined) setConfirmArtist(found);
            }}
            isUnfollowing={unfollowMut.isPending && unfollowMut.variables === a.id}
          />
        ))}
      </main>

      <ArtistDetailDialog
        artistId={detailId}
        open={detailId !== null}
        onOpenChange={(o) => { if (!o) setDetailId(null); }}
        onUnfollowRequest={(a) => {
          setDetailId(null);
          setConfirmArtist(a);
        }}
      />

      <ConfirmUnfollowDialog
        artist={confirmArtist}
        open={confirmArtist !== null}
        onOpenChange={(o) => { if (!o) setConfirmArtist(null); }}
        isPending={unfollowMut.isPending}
        onConfirm={() => {
          if (confirmArtist?.id == null) return;
          const id = confirmArtist.id;
          const name = confirmArtist.display_name;
          unfollowMut.mutate(id, {
            onSuccess: () => {
              setConfirmArtist(null);
              toast.success(`Unfollowed ${name}`);
            },
            onError: (err) => {
              toast.error(err instanceof Error ? err.message : 'Unfollow failed');
            },
          });
        }}
      />

      {overflow > 0 && (
        <p className="max-w-7xl mx-auto mt-6 font-sf-mono text-xs text-white/30 text-center">
          …+{overflow} more (use filters to narrow)
        </p>
      )}
    </div>
  );
}
