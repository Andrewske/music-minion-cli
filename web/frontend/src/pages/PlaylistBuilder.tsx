import { useState, useEffect, useRef } from 'react';
import { useBuilderSession } from '../hooks/useBuilderSession';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { builderApi } from '../api/builder';
import type { Track } from '../api/builder';

interface PlaylistBuilderProps {
  playlistId: number;
}

export function PlaylistBuilder({ playlistId }: PlaylistBuilderProps) {
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const {
    session,
    addTrack,
    skipTrack,
    filters,
    updateFilters,
    startSession,
    isAddingTrack,
    isSkippingTrack
  } = useBuilderSession(playlistId);

  // Activate builder mode on mount, deactivate on unmount
  useEffect(() => {
    if (playlistId) {
      builderApi.activateBuilderMode(playlistId);

      return () => {
        builderApi.deactivateBuilderMode();
      };
    }
  }, [playlistId]);

  // Fetch initial candidate after session starts
  useEffect(() => {
    if (session && !currentTrack) {
      builderApi.getNextCandidate(playlistId!).then(setCurrentTrack);
    }
  }, [session, currentTrack, playlistId]);

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

  // Auto-play current track on loop
  useEffect(() => {
    if (currentTrack && audioRef.current) {
      const audio = audioRef.current;
      audio.src = `/api/tracks/${currentTrack.id}/stream`;
      audio.loop = true;
      audio.play().catch(err => {
        console.error('Failed to play audio:', err);
        // Auto-skip on playback error
        setTimeout(() => {
          if (currentTrack) {
            skipTrack.mutate(currentTrack.id);
          }
        }, 3000);
      });

      return () => {
        audio.pause();
        audio.src = '';
      };
    }
  }, [currentTrack?.id]);

  // Handle add track
  const handleAdd = async () => {
    if (!currentTrack || isAddingTrack || isSkippingTrack) return;

    const trackId = currentTrack.id;
    await addTrack.mutateAsync(trackId);

    // Fetch next candidate
    const nextTrack = await builderApi.getNextCandidate(playlistId!, trackId);
    setCurrentTrack(nextTrack);
  };

  // Handle skip track
  const handleSkip = async () => {
    if (!currentTrack || isAddingTrack || isSkippingTrack) return;

    const trackId = currentTrack.id;
    await skipTrack.mutateAsync(trackId);

    // Fetch next candidate
    const nextTrack = await builderApi.getNextCandidate(playlistId!, trackId);
    setCurrentTrack(nextTrack);
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
      <audio ref={audioRef} />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-6">
        {/* Left Panel: Filters */}
        <aside className="md:col-span-1 bg-slate-900 rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Filters</h3>
          <FilterPanel
            filters={filters || []}
            onUpdate={(newFilters) => updateFilters.mutate(newFilters)}
          />
        </aside>

        {/* Center: Track Player */}
        <main className="md:col-span-3">
          {currentTrack ? (
            <div className="bg-slate-900 rounded-lg p-8">
              <TrackDisplay track={currentTrack} />

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
              <h3 className="text-2xl font-bold mb-2">No more candidates</h3>
              <p className="text-gray-400">Adjust your filters or review skipped tracks</p>
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

function FilterPanel(_props: { filters: any[]; onUpdate: (filters: any[]) => void }) {
  return (
    <div className="text-gray-400">
      <p className="text-sm">Filter UI coming soon</p>
      <p className="text-xs mt-2">Genre, BPM, Year, Key</p>
    </div>
  );
}
