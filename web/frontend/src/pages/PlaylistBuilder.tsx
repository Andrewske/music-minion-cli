import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useBuilderSession } from '../hooks/useBuilderSession';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { builderApi } from '../api/builder';
import type { Track } from '../api/builder';
import { SortControl } from '../components/builder/SortControl';
import FilterPanel from '../components/builder/FilterPanel';
import { WaveformPlayer } from '../components/WaveformPlayer';
interface PlaylistBuilderProps {
  playlistId: number;
  playlistName: string;
}

export function PlaylistBuilder({ playlistId, playlistName }: PlaylistBuilderProps) {
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true); // Auto-play by default
  const [loopEnabled, setLoopEnabled] = useState(true);

  const {
    session,
    addTrack,
    skipTrack,
    filters,
    updateFilters,
    startSession,
    isAddingTrack,
    isSkippingTrack,
    sortField,
    sortDirection,
    setSortField,
    setSortDirection
  } = useBuilderSession(playlistId);

  // Fetch candidates with sorting
  const { data: candidatesData } = useQuery({
    queryKey: ['builder-candidates', playlistId, sortField, sortDirection],
    queryFn: () => playlistId ? builderApi.getCandidates(playlistId, 100, 0) : null,
    enabled: !!playlistId && !!session,
    select: (data) => {
      if (!data?.candidates) return data;
      const sorted = [...data.candidates].sort((a, b) => {
        const aVal = a[sortField] ?? '';
        const bVal = b[sortField] ?? '';
        const cmp = typeof aVal === 'number' ? aVal - (bVal as number) : String(aVal).localeCompare(String(bVal));
        return sortDirection === 'asc' ? cmp : -cmp;
      });
      return { ...data, candidates: sorted };
    },
  });

  // Current track from sorted candidates
  const currentTrack = candidatesData?.candidates?.[candidateIndex] ?? null;



  // Activate builder mode on mount, deactivate on unmount
  useEffect(() => {
    if (playlistId) {
      builderApi.activateBuilderMode(playlistId);

      return () => {
        builderApi.deactivateBuilderMode();
      };
    }
  }, [playlistId]);

  // Reset candidate index when session starts or sorting changes
  useEffect(() => {
    if (session) {
      setCandidateIndex(0);
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
    if (!currentTrack || isAddingTrack || isSkippingTrack) return;

    const trackId = currentTrack.id;
    await addTrack.mutateAsync(trackId);

    // Move to next candidate
    setCandidateIndex(prev => prev + 1);
  };

  // Handle skip track
  const handleSkip = async () => {
    if (!currentTrack || isAddingTrack || isSkippingTrack) return;

    const trackId = currentTrack.id;
    await skipTrack.mutateAsync(trackId);

    // Move to next candidate
    setCandidateIndex(prev => prev + 1);
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



      {/* Header with playlist name and sort controls */}
      <div className="flex justify-between items-center mb-4 px-6 pt-6">
        <h2 className="text-xl font-semibold">Building: {playlistName}</h2>
        <SortControl
          sortField={sortField}
          sortDirection={sortDirection}
          onSortFieldChange={setSortField}
          onSortDirectionChange={setSortDirection}
        />
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
          {currentTrack && candidateIndex < (candidatesData?.candidates?.length ?? 0) ? (
            <div className="bg-slate-900 rounded-lg p-8">
              <TrackDisplay track={currentTrack} />

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

              <StatsPanel stats={stats} />
            </div>
          ) : (
            <div className="bg-slate-900 rounded-lg p-8 text-center">
              <h3 className="text-2xl font-bold mb-2">
                {candidateIndex >= (candidatesData?.candidates?.length ?? 0) ? 'No more candidates' : 'Loading candidates...'}
              </h3>
              <p className="text-gray-400">
                {candidateIndex >= (candidatesData?.candidates?.length ?? 0)
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

function TrackDisplay({ track }: { track: Track }) {
  return (
    <div className="text-center">
      <h2 className="text-4xl font-bold mb-2">{track.title}</h2>
      <p className="text-2xl text-gray-300 mb-4">{track.artist}</p>
      {track.album && <p className="text-xl text-gray-400 mb-6">{track.album}</p>}
      <div className="flex gap-4 justify-center flex-wrap">
        {track.genre && <span className="px-3 py-1 bg-purple-600 rounded-full">{track.genre}</span>}
        {track.year && <span className="px-3 py-1 bg-blue-600 rounded-full">{track.year}</span>}
        {track.bpm && <span className="px-3 py-1 bg-orange-600 rounded-full">{track.bpm} BPM</span>}
        {track.key_signature && <span className="px-3 py-1 bg-green-600 rounded-full">{track.key_signature}</span>}
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


