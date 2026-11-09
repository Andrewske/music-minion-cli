import { useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Title as DialogTitle } from '@radix-ui/react-dialog';
import { GalleryVerticalEnd, Loader2, PartyPopper, RefreshCw, Users } from 'lucide-react';
import { getStories, type StoriesArtist, type StoriesTrack } from '../../api/stories';
import { useStoriesVerdict } from '../../hooks/useStoriesVerdict';
import { usePlayerStore } from '../../stores/playerStore';
import { toast } from 'sonner';
import { useStoriesStore } from '../../stores/storiesStore';
import { Sheet, SheetContent } from '../ui/sheet';
import { FeedWaveform } from '../feed/FeedWaveform';
import { StoriesArtistList } from './StoriesArtistList';
import { StoriesControls } from './StoriesControls';
import { StoriesHero } from './StoriesHero';
import { StoriesTrackList } from './StoriesTrackList';
import {
  canGoPrevious,
  findArtist,
  focusTrack,
  isCaughtUp,
  playingStoryId,
  STORIES_QUERY_KEY,
  visibleArtists,
  type StoriesSession,
} from './storiesQueue';

function StatusView({ children, role }: { children: ReactNode; role: 'status' | 'alert' }): JSX.Element {
  return (
    <div role={role} className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-sm text-white/50">
      {children}
    </div>
  );
}

function CaughtUp({ onRefresh, isRefreshing }: { onRefresh: () => void; isRefreshing: boolean }): JSX.Element {
  return (
    <StatusView role="status">
      <PartyPopper className="h-8 w-8 text-obsidian-accent" aria-hidden="true" />
      <p className="text-base font-medium text-white">You're all caught up</p>
      <p>Nothing unheard from the artists you follow in the last 7 days.</p>
      <button type="button" onClick={onRefresh} disabled={isRefreshing} className="rounded-sm border border-obsidian-border px-3 py-1.5 text-white/70 hover:text-white disabled:opacity-50">
        Check again
      </button>
    </StatusView>
  );
}

interface PlayerControls {
  playerTrackId: number | null;
  isPlaying: boolean;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
}

/** Pause/resume when the player already holds this story; otherwise start it. */
function useTogglePlay(session: StoriesSession): (track: StoriesTrack) => void {
  const dispatch = useStoriesStore((state) => state.dispatch);
  const player: PlayerControls = {
    playerTrackId: usePlayerStore((state) => state.currentTrack?.id ?? null),
    isPlaying: usePlayerStore((state) => state.isPlaying),
    pause: usePlayerStore((state) => state.pause),
    resume: usePlayerStore((state) => state.resume),
  };
  return (track) => {
    const loaded = track.local_track_id !== null && track.local_track_id === player.playerTrackId;
    if (loaded) {
      void (player.isPlaying ? player.pause() : player.resume());
      return;
    }
    if (session.activeArtistId === null) return;
    dispatch({ type: 'play-track', artistId: session.activeArtistId, soundcloudId: track.soundcloud_id });
  };
}

interface StageProps {
  session: StoriesSession;
  artist: StoriesArtist;
  track: StoriesTrack;
}

/** Centre column: hero artwork, controls, waveform, and the artist's track list. */
function StoriesStage({ session, artist, track }: StageProps): JSX.Element {
  const dispatch = useStoriesStore((state) => state.dispatch);
  const playerTrackId = usePlayerStore((state) => state.currentTrack?.id ?? null);
  const playerIsPlaying = usePlayerStore((state) => state.isPlaying);
  const togglePlay = useTogglePlay(session);
  const { decide, pendingId } = useStoriesVerdict();
  const isPlaying = playerIsPlaying && track.local_track_id !== null && track.local_track_id === playerTrackId;

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-4 md:py-8">
      <StoriesHero artist={artist} track={track} isPlaying={isPlaying} onTogglePlay={() => togglePlay(track)} />
      <StoriesControls
        track={track}
        canGoPrevious={canGoPrevious(session)}
        isUpdating={pendingId !== null}
        onDecide={(decision) => decide(track, decision)}
        onPrevious={() => dispatch({ type: 'previous' })}
      />
      <FeedWaveform localTrackId={track.local_track_id} durationMs={track.duration_ms} onActivate={() => togglePlay(track)} />
      <StoriesTrackList tracks={artist.tracks} currentId={playingStoryId(session, playerTrackId)} onPlay={togglePlay} />
    </div>
  );
}

interface ArtistDrawerProps {
  artists: readonly StoriesArtist[];
  activeArtistId: number | null;
  onSelect: (artistId: number) => void;
}

/** Phone: the artist list lives in a left slide-out sheet. */
function ArtistDrawer({ artists, activeArtistId, onSelect }: ArtistDrawerProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-1.5 rounded-full border border-obsidian-border px-3 py-1.5 text-xs text-white/70 hover:text-white md:hidden"
      >
        <Users className="h-4 w-4" /> Artists ({artists.length})
      </button>
      <SheetContent side="left" aria-describedby={undefined} className="w-[280px] overflow-y-auto px-3 pb-6 pt-[calc(1rem+env(safe-area-inset-top,0px))]">
        <DialogTitle className="px-2 pb-3 text-sm font-semibold text-white">Latest from people you follow</DialogTitle>
        <StoriesArtistList
          artists={artists}
          activeArtistId={activeArtistId}
          onSelect={(artistId) => {
            setIsOpen(false);
            onSelect(artistId);
          }}
        />
      </SheetContent>
    </Sheet>
  );
}

function StoriesLayout({ session, onRefresh, isRefreshing }: { session: StoriesSession; onRefresh: () => void; isRefreshing: boolean }): JSX.Element {
  const dispatch = useStoriesStore((state) => state.dispatch);
  const artists = visibleArtists(session);
  const artist = findArtist(session, session.activeArtistId);
  const track = focusTrack(session);
  const select = (artistId: number): void => dispatch({ type: 'select-artist', artistId });

  return (
    <div className="flex h-full min-h-0">
      <aside className="hidden w-72 shrink-0 overflow-y-auto px-4 py-6 md:block">
        <h2 className="px-2 pb-4 text-base font-semibold text-white">Latest from people you follow</h2>
        <StoriesArtistList artists={artists} activeArtistId={session.activeArtistId} onSelect={select} />
      </aside>
      <div className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
        <header className="mx-auto flex w-full max-w-xl items-center gap-3 px-4 pt-4">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-white">
            <GalleryVerticalEnd className="h-5 w-5 text-obsidian-accent" /> Stories
          </h1>
          <ArtistDrawer artists={artists} activeArtistId={session.activeArtistId} onSelect={select} />
          <button type="button" onClick={onRefresh} disabled={isRefreshing} aria-label="Reload stories" className="ml-auto rounded-sm p-2 text-white/60 hover:bg-white/5 hover:text-white disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </header>
        {artist && track && <StoriesStage session={session} artist={artist} track={track} />}
      </div>
    </div>
  );
}

export function StoriesPage(): JSX.Element {
  const query = useQuery({
    queryKey: STORIES_QUERY_KEY,
    queryFn: () => getStories(),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const session = useStoriesStore((state) => state.session);
  const start = useStoriesStore((state) => state.start);

  // Snapshot the first response; later refetches only replace it via Reload.
  useEffect(() => {
    if (query.data && !session) start(query.data, usePlayerStore.getState().currentTrack?.id ?? null);
  }, [query.data, session, start]);

  // A failed refetch still carries the old cached data; never rebuild from it.
  const refresh = (): void => {
    void query.refetch().then((result) => {
      if (result.isSuccess) start(result.data, usePlayerStore.getState().currentTrack?.id ?? null);
      else toast.error('Could not reload stories');
    });
  };

  if (query.isError && !session) {
    return (
      <StatusView role="alert">
        <span>Failed to load stories</span>
        <button type="button" onClick={refresh} className="rounded-sm border border-obsidian-border px-3 py-1.5 text-white/70">Try again</button>
      </StatusView>
    );
  }
  if (!session) {
    return <StatusView role="status"><Loader2 className="h-6 w-6 animate-spin" aria-label="Loading stories" /></StatusView>;
  }
  if (isCaughtUp(session)) return <CaughtUp onRefresh={refresh} isRefreshing={query.isFetching} />;
  return <StoriesLayout session={session} onRefresh={refresh} isRefreshing={query.isFetching} />;
}
