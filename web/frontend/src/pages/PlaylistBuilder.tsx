import { useState, useEffect } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import { useBuilderSession } from '../hooks/useBuilderSession';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { builderApi } from '../api/builder';
import type { Track } from '../api/builder';
import { TrackQueueTable } from '../components/builder/TrackQueueTable';
import FilterPanel from '../components/builder/FilterPanel';
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
    filters,
    updateFilters,
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
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Start Building Playlist</h2>
          <button
            onClick={() => startSession.mutate(playlistId)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Start Session
          </button>
        </div>
      </div>
    );
  }

  const stats = session ? {
    startedAt: session.started_at,
    updatedAt: session.updated_at
  } : null;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header with playlist name */}
      <div className="flex justify-between items-center mb-4 px-6 pt-6">
        <h2 className="text-xl font-semibold">Building: {playlistName}</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 px-6 pb-6">
        {/* Left Panel: Filters */}
        <aside className="md:col-span-1 bg-slate-900 rounded-lg p-4">
          <FilterPanel
            filters={filters || []}
            onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
            isUpdating={updateFilters.isPending}
            playlistId={playlistId}
          />
        </aside>

        {/* Center: Track Player */}
        <main className="md:col-span-3">
          {currentTrack && queueIndex < candidates.length ? (
            <div className="bg-slate-900 rounded-lg p-8">
              <TrackDisplay
                track={getTrackWithOverrides(currentTrack)}
                onEmojiUpdate={handleTrackEmojiUpdate}
              />

              {currentTrack && (
                <div className="h-20 mb-6">
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
               )}

               <div className="flex justify-center mb-4">
                 <label className="flex items-center gap-2 text-sm text-slate-400">
                   <input
                     type="checkbox"
                     checked={loopEnabled}
                     onChange={(e) => setLoopEnabled(e.target.checked)}
                     className="rounded"
                   />
                   Loop track
                 </label>
               </div>

               <div className="flex gap-4 mt-8 justify-center">
                <button
                  onClick={handleAdd}
                  disabled={isAddingTrack || isSkippingTrack}
                  className="px-8 py-4 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-lg font-semibold"
                >
                  {isAddingTrack ? 'Adding...' : 'Add to Playlist'}
                </button>
                <button
                  onClick={handleSkip}
                  disabled={isAddingTrack || isSkippingTrack}
                  className="px-8 py-4 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-lg font-semibold"
                >
                  {isSkippingTrack ? 'Skipping...' : 'Skip'}
                </button>
              </div>

              {/* Track Queue Table */}
              <div className="mt-8">
                <TrackQueueTable
                  tracks={candidates}
                  queueIndex={queueIndex >= 0 ? queueIndex : 0}
                  nowPlayingId={nowPlayingTrack?.id ?? null}
                  onTrackClick={(track) => {
                    // No-op if clicking already-playing track
                    if (track.id === nowPlayingTrack?.id) return;
                    setNowPlayingTrack(track);
                  }}
                  sorting={sorting}
                  onSortingChange={setSorting}
                  onLoadMore={() => fetchNextPage()}
                  hasMore={hasNextPage ?? false}
                  isLoadingMore={isFetchingNextPage}
                />
              </div>

              <StatsPanel stats={stats} />
            </div>
          ) : (
            <div className="bg-slate-900 rounded-lg p-8 text-center">
              <h3 className="text-2xl font-bold mb-2">
                {queueIndex >= candidates.length ? 'No more candidates' : 'Loading candidates...'}
              </h3>
              <p className="text-gray-400">
                {queueIndex >= candidates.length
                  ? 'Adjust your filters or review skipped tracks'
                  : 'Fetching tracks that match your criteria'
                }
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// Supporting Components

function TrackDisplay({ track, onEmojiUpdate }: { track: Track; onEmojiUpdate: (t: { id: number; emojis?: string[] }) => void }) {
  return (
    <div className="text-center">
      <h2 className="text-4xl font-bold mb-2">{track.title}</h2>
      <p className="text-2xl text-gray-300 mb-4">{track.artist}</p>
      {track.album && <p className="text-xl text-gray-400 mb-6">{track.album}</p>}
      <div className="flex gap-4 justify-center flex-wrap items-center">
        {track.genre && <span className="px-3 py-1 bg-purple-600 rounded-full">{track.genre}</span>}
        {track.year && <span className="px-3 py-1 bg-blue-600 rounded-full">{track.year}</span>}
        {track.bpm && <span className="px-3 py-1 bg-orange-600 rounded-full">{track.bpm} BPM</span>}
        {track.key_signature && <span className="px-3 py-1 bg-green-600 rounded-full">{track.key_signature}</span>}
        <EmojiTrackActions
          track={{ id: track.id, emojis: track.emojis }}
          onUpdate={onEmojiUpdate}
        />
      </div>
    </div>
  );
}

function StatsPanel({ stats }: { stats: { startedAt: string; updatedAt: string } | null }) {
  if (!stats) return null;

  return (
    <div className="mt-8 p-4 bg-slate-800 rounded-lg">
      <h4 className="text-lg font-semibold mb-2">Session Stats</h4>
      <ul className="text-gray-300 space-y-1">
        <li>Started: {new Date(stats.startedAt).toLocaleString()}</li>
        <li>Last updated: {new Date(stats.updatedAt).toLocaleString()}</li>
      </ul>
    </div>
  );
}


