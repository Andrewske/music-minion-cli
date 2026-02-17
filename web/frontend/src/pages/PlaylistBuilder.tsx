import { useState, useEffect } from 'react';
import { usePlaylistBuilder } from '../hooks/usePlaylistBuilder';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { builderApi } from '../api/builder';
import type { Track } from '../api/builder';
import { TrackQueueTable } from '../components/builder/TrackQueueTable';
import { TrackDisplay } from '../components/builder/TrackDisplay';
import { WaveformSection } from '../components/builder/WaveformSection';
import { BuilderActions } from '../components/builder/BuilderActions';
import FilterPanel from '../components/builder/FilterPanel';
import { SkippedTracksDialog } from '../components/builder/SkippedTracksDialog';

interface PlaylistBuilderProps {
  playlistId: number;
  playlistName: string;
  playlistType: 'manual' | 'smart';
}

export function PlaylistBuilder({ playlistId, playlistName, playlistType }: PlaylistBuilderProps) {
  const [queueTrackId, setQueueTrackId] = useState<number | null>(null);
  const [nowPlayingTrack, setNowPlayingTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(true); // Auto-play by default
  const [loopEnabled, setLoopEnabled] = useState(true);
  const [isSkippedDialogOpen, setIsSkippedDialogOpen] = useState(false);

  const [localTrackOverrides, setLocalTrackOverrides] = useState<Record<number, { emojis?: string[] }>>({});

  // Unified hook for both playlist types
  const builder = usePlaylistBuilder(playlistId, playlistType);

  // Merge local overrides with tracks for display
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

  // Derive queue index from ID
  const queueIndex = queueTrackId
    ? builder.tracks.findIndex(t => t.id === queueTrackId)
    : 0;

  // If queueTrackId not found (filtered out), reset to first track
  useEffect(() => {
    if (builder.tracks.length > 0 && (queueTrackId === null || queueIndex === -1)) {
      setQueueTrackId(builder.tracks[0].id);
    }
  }, [builder.tracks, queueTrackId, queueIndex]);

  // Current track for display = nowPlayingTrack ?? tracks[queueIndex]
  const currentTrack = nowPlayingTrack ?? builder.tracks[queueIndex] ?? null;

  // Activate builder mode on mount, deactivate on unmount
  useEffect(() => {
    if (playlistId) {
      builderApi.activateBuilderMode(playlistId);

      return () => {
        builderApi.deactivateBuilderMode();
      };
    }
  }, [playlistId]);

  // Reset queue to first track when sorting changes
  useEffect(() => {
    if (builder.tracks.length > 0) {
      setQueueTrackId(builder.tracks[0].id);
      setNowPlayingTrack(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [builder.sorting]);

  // Handle keyboard shortcuts via WebSocket (useRef pattern)
  useIPCWebSocket({
    onBuilderAdd: () => {
      if (playlistType === 'manual' && currentTrack && !builder.isAddingTrack && !builder.isSkippingTrack) {
        handleAdd();
      }
    },
    onBuilderSkip: () => {
      if (currentTrack && !builder.isAddingTrack && !builder.isSkippingTrack) {
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

  // Handle add track (manual playlists only)
  const handleAdd = async () => {
    const trackToAdd = nowPlayingTrack ?? builder.tracks[queueIndex];
    if (!trackToAdd || builder.isAddingTrack || builder.isSkippingTrack) return;

    await builder.addTrack.mutateAsync(trackToAdd.id);

    // Advance queue to next track by ID
    const nextIndex = queueIndex + 1;
    if (nextIndex < builder.tracks.length) {
      setQueueTrackId(builder.tracks[nextIndex].id);
    }
    setNowPlayingTrack(null); // Clear preview state
  };

  // Handle skip track (both playlist types)
  const handleSkip = async () => {
    const trackToSkip = nowPlayingTrack ?? builder.tracks[queueIndex];
    if (!trackToSkip || builder.isAddingTrack || builder.isSkippingTrack) return;

    await builder.skipTrack.mutateAsync(trackToSkip.id);

    // Advance queue to next track by ID
    const nextIndex = queueIndex + 1;
    if (nextIndex < builder.tracks.length) {
      setQueueTrackId(builder.tracks[nextIndex].id);
    }
    setNowPlayingTrack(null); // Clear preview state
  };

  // Handle waveform finish (loop or skip)
  const handleWaveformFinish = () => {
    if (loopEnabled) {
      setIsPlaying(false);
      setTimeout(() => setIsPlaying(true), 100);
    } else {
      handleSkip();
    }
  };

  // Loading state
  if (builder.isLoading) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-white/40 text-sm">Loading...</div>
      </div>
    );
  }

  // Main content (track display, waveform, actions)
  const renderMainContent = () => (
    <>
      {currentTrack && queueIndex < builder.tracks.length ? (
        <div className="space-y-6 md:space-y-12">
          {/* Player section - sticky on mobile */}
          <div className="sticky top-10 md:static z-10 bg-black pb-4 md:pb-0">
            {/* Track Display */}
            <TrackDisplay
              track={getTrackWithOverrides(currentTrack)}
              onEmojiUpdate={handleTrackEmojiUpdate}
            />

            {/* Waveform */}
            <WaveformSection
              track={currentTrack}
              isPlaying={isPlaying}
              loopEnabled={loopEnabled}
              onTogglePlayPause={() => setIsPlaying(!isPlaying)}
              onLoopChange={setLoopEnabled}
              onFinish={handleWaveformFinish}
            />

            {/* Actions */}
            <BuilderActions
              playlistType={playlistType}
              onAdd={playlistType === 'manual' ? handleAdd : undefined}
              onSkip={handleSkip}
              isAddingTrack={builder.isAddingTrack}
              isSkippingTrack={builder.isSkippingTrack}
            />
          </div>

          {/* Track Queue */}
          <TrackQueueTable
            tracks={builder.tracks}
            queueIndex={queueIndex >= 0 ? queueIndex : 0}
            nowPlayingId={nowPlayingTrack?.id ?? null}
            onTrackClick={(track) => {
              if (track.id !== nowPlayingTrack?.id) setNowPlayingTrack(track);
            }}
            sorting={builder.sorting}
            onSortingChange={builder.setSorting}
            onLoadMore={() => builder.fetchNextPage()}
            hasMore={builder.hasNextPage ?? false}
            isLoadingMore={builder.isFetchingNextPage}
          />
        </div>
      ) : (
        <div className="py-20 text-center">
          <p className="text-white/40 text-sm">
            {queueIndex >= builder.tracks.length ? 'No more tracks' : 'Loading...'}
          </p>
        </div>
      )}
    </>
  );

  return (
    <div className="min-h-screen bg-black font-inter text-white">
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-4 md:py-8">
        {/* Header with playlist name and track count */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <p className="text-white/40 text-sm font-sf-mono mb-1">
              {playlistType === 'smart' ? '[Smart]' : '[Manual]'}
            </p>
            <h1 className="text-xl text-white/60">{playlistName}</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-white/40 text-sm">{builder.tracks.length} tracks</span>
            <button
              onClick={() => setIsSkippedDialogOpen(true)}
              className="px-4 py-2 text-white/40 hover:text-white/60 text-sm transition-colors"
            >
              Skipped ({builder.skippedTracks?.length ?? 0})
            </button>
          </div>
        </div>

        {playlistType === 'smart' ? (
          // Smart playlist: two-column layout with sidebar
          <div className="flex gap-8">
            {/* Sidebar */}
            <aside className="w-64 shrink-0">
              <div className="bg-black/50 border border-obsidian-border rounded-lg p-4">
                <FilterPanel
                  filters={builder.filters}
                  onUpdate={(newFilters) => builder.updateFilters.mutate(newFilters)}
                  isUpdating={builder.updateFilters.isPending}
                  playlistId={playlistId}
                />
              </div>
            </aside>
            {/* Main content */}
            <main className="flex-1">
              {renderMainContent()}
            </main>
          </div>
        ) : (
          // Manual playlist: full width
          <main>
            {renderMainContent()}
          </main>
        )}
      </div>

      {/* Skipped Tracks Dialog (both playlist types) */}
      <SkippedTracksDialog
        open={isSkippedDialogOpen}
        onClose={() => setIsSkippedDialogOpen(false)}
        tracks={builder.skippedTracks ?? []}
        onUnskip={(trackId) => builder.unskipTrack.mutate(trackId)}
        isUnskipping={builder.unskipTrack.isPending}
      />
    </div>
  );
}
