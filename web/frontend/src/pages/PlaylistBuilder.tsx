import { useState, useEffect } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import { useBuilderSession } from '../hooks/useBuilderSession';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { builderApi } from '../api/builder';
import type { Track } from '../api/builder';
import { TrackQueueTable } from '../components/builder/TrackQueueTable';
import { WaveformPlayer } from '../components/WaveformPlayer';
import { SmartPlaylistEditor } from './SmartPlaylistEditor';
import { EmojiTrackActions } from '../components/EmojiTrackActions';

interface PlaylistBuilderProps {
  playlistId: number;
  playlistName: string;
  playlistType: 'manual' | 'smart';
}

export function PlaylistBuilder({ playlistId, playlistName, playlistType }: PlaylistBuilderProps) {
  // Route to smart editor for smart playlists
  if (playlistType === 'smart') {
    return <SmartPlaylistEditor playlistId={playlistId} playlistName={playlistName} />;
  }

  // Existing manual builder code continues below...
  const [queueTrackId, setQueueTrackId] = useState<number | null>(null);
  const [nowPlayingTrack, setNowPlayingTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(true); // Auto-play by default
  const [loopEnabled, setLoopEnabled] = useState(true);

  const [localTrackOverrides, setLocalTrackOverrides] = useState<Record<number, { emojis?: string[] }>>({});

  // Merge local overrides with candidates for display
  const getTrackWithOverrides = (track: Track): Track => ({
    ...track,
    ...localTrackOverrides[track.id],
  });

  const handleTrackEmojiUpdate = (updatedTrack: { id: number; emojis?: string[] }): void => {
    setLocalTrackOverrides(prev => ({
      ...prev,
      [updatedTrack.id]: { emojis: updatedTrack.emojis },
    }));
  };

  // Sorting state - controls server-side sort via API params
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'artist', desc: false }
  ]);

  // Derive sort params from TanStack state
  const sortField = sorting[0]?.id ?? 'artist';
  const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';

  const {
    session,
    addTrack,
    skipTrack,
    startSession,
    isAddingTrack,
    isSkippingTrack,
  } = useBuilderSession(playlistId);

  const PAGE_SIZE = 100;

  // Fetch candidates with server-side sorting and pagination
  const {
    data: candidatesData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['builder-candidates', playlistId, sortField, sortDirection],
    queryFn: ({ pageParam = 0 }) =>
      builderApi.getCandidates(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.length * PAGE_SIZE : undefined,
    enabled: !!playlistId && !!session,
  });

  // Flatten pages into single array for table display
  const candidates = candidatesData?.pages.flatMap(p => p.candidates) ?? [];

  // Derive queue index from ID
  const queueIndex = queueTrackId
    ? candidates.findIndex(t => t.id === queueTrackId)
    : 0;

  // If queueTrackId not found (filtered out), reset to first track
  useEffect(() => {
    if (candidates.length > 0 && (queueTrackId === null || queueIndex === -1)) {
      setQueueTrackId(candidates[0].id);
    }
  }, [candidates, queueTrackId, queueIndex]);

  // Current track for display = nowPlayingTrack ?? candidates[queueIndex]
  const currentTrack = nowPlayingTrack ?? candidates[queueIndex] ?? null;



  // Activate builder mode on mount, deactivate on unmount
  useEffect(() => {
    if (playlistId) {
      builderApi.activateBuilderMode(playlistId);

      return () => {
        builderApi.deactivateBuilderMode();
      };
    }
  }, [playlistId]);

  // Reset queue to first track when session starts or sorting changes
  useEffect(() => {
    if (session && candidates.length > 0) {
      setQueueTrackId(candidates[0].id);
      setNowPlayingTrack(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, sortField, sortDirection]);

  // Handle keyboard shortcuts via WebSocket (useRef pattern)
  useIPCWebSocket({
    onBuilderAdd: () => {
      if (currentTrack && !isAddingTrack && !isSkippingTrack) {
        handleAdd();
      }
    },
    onBuilderSkip: () => {
      if (currentTrack && !isAddingTrack && !isSkippingTrack) {
        handleSkip();
      }
    }
  });

  // Auto-play new tracks
  useEffect(() => {
    if (currentTrack) {
      setIsPlaying(true);
    }
  }, [currentTrack]);

  // Keyboard shortcuts for waveform control
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key >= '0' && e.key <= '9') {
        const percent = parseInt(e.key) * 10;
        window.dispatchEvent(new CustomEvent('music-minion-seek-percent', { detail: percent }));
      }
      if (e.key === ' ') {
        e.preventDefault();
        setIsPlaying(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handle add track
  const handleAdd = async () => {
    const trackToAdd = nowPlayingTrack ?? candidates[queueIndex];
    if (!trackToAdd || isAddingTrack || isSkippingTrack) return;

    await addTrack.mutateAsync(trackToAdd.id);

    // Advance queue to next track by ID
    const nextIndex = queueIndex + 1;
    if (nextIndex < candidates.length) {
      setQueueTrackId(candidates[nextIndex].id);
    }
    setNowPlayingTrack(null); // Clear preview state
  };

  // Handle skip track
  const handleSkip = async () => {
    const trackToSkip = nowPlayingTrack ?? candidates[queueIndex];
    if (!trackToSkip || isAddingTrack || isSkippingTrack) return;

    await skipTrack.mutateAsync(trackToSkip.id);

    // Advance queue to next track by ID
    const nextIndex = queueIndex + 1;
    if (nextIndex < candidates.length) {
      setQueueTrackId(candidates[nextIndex].id);
    }
    setNowPlayingTrack(null); // Clear preview state
  };

  if (!session) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-center">
          <p className="text-white/40 text-sm mb-8 font-sf-mono">{playlistName}</p>
          <button
            onClick={() => startSession.mutate(playlistId)}
            className="px-8 py-3 text-obsidian-accent border border-obsidian-accent/30
              hover:bg-obsidian-accent/10 transition-colors text-sm tracking-wider"
          >
            Begin
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black font-inter text-white">
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-4 md:py-8">
        <main>
          {currentTrack && queueIndex < candidates.length ? (
            <div className="space-y-6 md:space-y-12">
              {/* Player section - sticky on mobile */}
              <div className="sticky top-10 md:static z-10 bg-black pb-4 md:pb-0">
                {/* Track Display */}
                <div className="py-4 md:py-8">
                  <p className="text-obsidian-accent text-sm font-sf-mono mb-2">{currentTrack.artist}</p>
                  <h2 className="text-2xl md:text-4xl font-light text-white mb-2 md:mb-4">{currentTrack.title}</h2>
                  {currentTrack.album && (
                    <p className="text-white/30 text-sm">{currentTrack.album}</p>
                  )}

                  {/* Metadata pills */}
                  <div className="flex flex-wrap items-center gap-2 md:gap-4 mt-4 md:mt-6">
                    {currentTrack.bpm && (
                      <span className="text-white/40 text-xs font-sf-mono">{Math.round(currentTrack.bpm)} BPM</span>
                    )}
                    {currentTrack.key_signature && (
                      <span className="text-white/40 text-xs font-sf-mono">{currentTrack.key_signature}</span>
                    )}
                    {currentTrack.genre && (
                      <span className="text-white/40 text-xs font-sf-mono">{currentTrack.genre}</span>
                    )}
                    {currentTrack.year && (
                      <span className="text-white/40 text-xs font-sf-mono">{currentTrack.year}</span>
                    )}
                    <EmojiTrackActions
                      track={{ id: currentTrack.id, emojis: getTrackWithOverrides(currentTrack).emojis }}
                      onUpdate={handleTrackEmojiUpdate}
                    />
                  </div>
                </div>

                {/* Waveform */}
                <div className="h-16 border-t border-b border-obsidian-border">
                  <WaveformPlayer
                    track={{
                      id: currentTrack.id,
                      title: currentTrack.title,
                      artist: currentTrack.artist,
                      rating: currentTrack.elo_rating || 0,
                      comparison_count: 0,
                      wins: 0,
                      losses: 0,
                      has_waveform: true,
                    }}
                    isPlaying={isPlaying}
                    onTogglePlayPause={() => setIsPlaying(!isPlaying)}
                    onFinish={() => {
                      if (loopEnabled) {
                        setIsPlaying(false);
                        setTimeout(() => setIsPlaying(true), 100);
                      } else {
                        handleSkip();
                      }
                    }}
                  />
                </div>

                {/* Loop toggle */}
                <div className="flex justify-center">
                  <label className="flex items-center gap-3 text-white/30 text-sm cursor-pointer hover:text-white/50 transition-colors">
                    <input
                      type="checkbox"
                      checked={loopEnabled}
                      onChange={(e) => setLoopEnabled(e.target.checked)}
                      className="w-3 h-3 accent-obsidian-accent"
                    />
                    Loop
                  </label>
                </div>

                {/* Actions */}
                <div className="flex gap-4 justify-center">
                  <button
                    onClick={handleAdd}
                    disabled={isAddingTrack || isSkippingTrack}
                    className="px-8 md:px-12 py-3 border border-obsidian-accent text-obsidian-accent
                      hover:bg-obsidian-accent hover:text-black disabled:opacity-30
                      transition-all text-sm tracking-wider"
                  >
                    {isAddingTrack ? '...' : 'Add'}
                  </button>
                  <button
                    onClick={handleSkip}
                    disabled={isAddingTrack || isSkippingTrack}
                    className="px-8 md:px-12 py-3 border border-white/20 text-white/60
                      hover:border-white/40 hover:text-white disabled:opacity-30
                      transition-all text-sm tracking-wider"
                  >
                    {isSkippingTrack ? '...' : 'Skip'}
                  </button>
                </div>
              </div>

              {/* Track Queue */}
              <TrackQueueTable
                tracks={candidates}
                queueIndex={queueIndex >= 0 ? queueIndex : 0}
                nowPlayingId={nowPlayingTrack?.id ?? null}
                onTrackClick={(track) => {
                  if (track.id !== nowPlayingTrack?.id) setNowPlayingTrack(track);
                }}
                sorting={sorting}
                onSortingChange={setSorting}
                onLoadMore={() => fetchNextPage()}
                hasMore={hasNextPage ?? false}
                isLoadingMore={isFetchingNextPage}
              />
            </div>
          ) : (
            <div className="py-20 text-center">
              <p className="text-white/40 text-sm">
                {queueIndex >= candidates.length ? 'No more tracks' : 'Loading...'}
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

