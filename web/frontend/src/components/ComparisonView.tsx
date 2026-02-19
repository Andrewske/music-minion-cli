import { useState, useCallback } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { usePlayerStore } from '../stores/playerStore';
import { useStartComparison, useRecordComparison, useArchiveTrack } from '../hooks/useComparison';
import { usePlaylists } from '../hooks/usePlaylists';
import type { TrackInfo, RecordComparisonRequest } from '../types';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { SwipeableTrack } from './SwipeableTrack';
import { AutoplayToggle } from './AutoplayToggle';
import { PlaylistPicker } from './PlaylistPicker';

import { ErrorState } from './ErrorState';
import { ErrorBoundary } from './ErrorBoundary';
import { StatsModal } from './StatsModal';

export function ComparisonView() {
  // Player state from global playerStore
  const { currentTrack, isPlaying, play, pause, resume } = usePlayerStore();

  // Comparison session state from comparisonStore
  const {
    currentPair,
    comparisonsCompleted,
    selectedPlaylistId,
    isComparisonMode,
    updateTrackInPair,
    progress,
  } = useComparisonStore();
  const startComparison = useStartComparison();
  const recordComparison = useRecordComparison();
  const archiveTrack = useArchiveTrack();

  // Connect to IPC WebSocket for remote control
  useIPCWebSocket();

  // Playlist selection state
  const playlistsQuery = usePlaylists();
  const playlists = playlistsQuery.data;

  // Stats modal state
  const [isStatsModalOpen, setIsStatsModalOpen] = useState(false);

  const handleSelectPlaylist = (playlistId: number) => {
    startComparison.mutate(playlistId);
  };

  const handleTrackTap = (track: TrackInfo) => {
    if (currentTrack?.id === track.id) {
      // Toggle play/pause for same track
      if (isPlaying) {
        pause();
      } else {
        resume();
      }
      // Play/pause state synced via global playerStore broadcasts
    } else {
      // Switch track and play via global player
      // Include both track IDs for comparison queue context (no shuffle in comparison mode)
      const trackIds = currentPair ? [currentPair.track_a.id, currentPair.track_b.id] : [];
      play(track, { type: 'comparison', track_ids: trackIds, shuffle: false });
      // Track selection synced via global playerStore broadcasts
    }
  };

  const handleSwipeRight = useCallback((trackId: number) => {
    if (!currentPair || !selectedPlaylistId) return;

    const request: RecordComparisonRequest = {
      playlist_id: selectedPlaylistId,
      track_a_id: currentPair.track_a.id,
      track_b_id: currentPair.track_b.id,
      winner_id: trackId,
    };

    recordComparison.mutate(request);
  }, [currentPair, selectedPlaylistId, recordComparison]);

  const handleSwipeLeft = useCallback((trackId: number) => {
    archiveTrack.mutate(trackId);
  }, [archiveTrack]);

  // Stable callback references for SwipeableTrack to prevent gesture hook instability
  const swipeRightA = useCallback(() => {
    if (!currentPair) return;
    handleSwipeRight(currentPair.track_a.id);
  }, [handleSwipeRight, currentPair]);
  const swipeLeftA = useCallback(() => {
    if (!currentPair) return;
    handleSwipeLeft(currentPair.track_a.id);
  }, [handleSwipeLeft, currentPair]);
  const swipeRightB = useCallback(() => {
    if (!currentPair) return;
    handleSwipeRight(currentPair.track_b.id);
  }, [handleSwipeRight, currentPair]);
  const swipeLeftB = useCallback(() => {
    if (!currentPair) return;
    handleSwipeLeft(currentPair.track_b.id);
  }, [handleSwipeLeft, currentPair]);

  if (startComparison.isError) {
    return (
      <ErrorState
        title="Failed to Start Comparison"
        message="Unable to load tracks for comparison. Please select a playlist to try again."
      />
    );
  }

  if (!currentPair && isComparisonMode) {
    // Ranking complete
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="text-center max-w-md w-full">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-500 mb-4">
            Ranking Complete
          </h1>
          <p className="text-white/60 mb-8 text-lg">
            All tracks have been compared
          </p>
          {progress && (
            <div className="mb-6 text-white/80">
              <p className="text-lg font-mono">
                {progress.compared} / {progress.total} comparisons ({progress.percentage.toFixed(1)}%)
              </p>
            </div>
          )}
          <button
            onClick={() => useComparisonStore.getState().reset()}
            className="w-full bg-indigo-600 text-white px-6 py-4 font-bold text-lg hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-900/50"
          >
            Start New Comparison
          </button>
        </div>
      </div>
    );
  }

  if (!currentPair) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="text-center max-w-lg w-full">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-500 mb-4">
            Music Minion
          </h1>
          <p className="text-white/60 mb-8 text-lg">
            Select a playlist to rank
          </p>

          {/* Playlist selector */}
          {playlists && playlists.length > 0 ? (
            <div>
              <label className="block text-white/60 text-sm mb-4 text-left">
                Select Playlist
              </label>
              <PlaylistPicker
                playlists={playlists.filter((p) => p.library === 'local')}
                selectedPlaylistId={null}
                onSelect={handleSelectPlaylist}
                isLoading={startComparison.isPending}
              />
            </div>
          ) : (
            <p className="text-white/40 text-sm">No playlists found</p>
          )}
        </div>
      </div>
    );
  }

  // Only show loading for archive (which removes track from playlist)
  // Recording comparison uses optimistic UI - no loading state
  const isArchiving = archiveTrack.isPending;
  const isSubmitting = recordComparison.isPending;

  return (
    <div className="min-h-screen bg-black flex flex-col text-white/90 overflow-x-hidden">
      {/* Header */}
      <div className="bg-obsidian-surface/50 backdrop-blur-md border-b border-obsidian-border sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="text-white/90 font-mono text-sm">
                  {progress && (
                    <span>Progress: {progress.compared} / {progress.total} ({progress.percentage.toFixed(1)}%)</span>
                  )}
                </div>
                <div className="text-white/60 text-xs">
                  Session: {comparisonsCompleted} comparisons
                </div>
              </div>
              <div className="flex items-center gap-4">
                <AutoplayToggle />
                <button
                  onClick={() => setIsStatsModalOpen(true)}
                  className="px-3 py-1.5 bg-obsidian-border hover:bg-white/5 text-white/60 hover:text-white/90 transition-colors text-xs font-medium"
                >
                  Stats
                </button>
              </div>
          </div>
        </div>
      </div>

      {/* Main Comparison Area */}
      <div className="flex-1 max-w-7xl mx-auto w-full p-4 flex flex-col lg:flex-row items-center justify-center gap-6 lg:gap-12 relative">

        {/* Track A */}
        <div className="w-full lg:max-w-md">
          <ErrorBoundary>
            <div className={`relative group transition-opacity duration-150 ${isSubmitting ? 'opacity-70' : ''}`}>
              <SwipeableTrack
                track={currentPair.track_a}
                isPlaying={isPlaying && currentTrack?.id === currentPair.track_a.id}
                onSwipeRight={swipeRightA}
                onSwipeLeft={swipeLeftA}
                onTap={() => handleTrackTap(currentPair.track_a)}
                onArchive={swipeLeftA}
                onWinner={swipeRightA}
                isLoading={isArchiving || isSubmitting}
                rankingMode="playlist"
                onTrackUpdate={updateTrackInPair}
              />
            </div>
          </ErrorBoundary>
        </div>

        {/* VS Badge */}
        <div className="flex flex-col items-center justify-center z-10 shrink-0">
          <div className="w-12 h-12 lg:w-16 lg:h-16 bg-obsidian-surface border-2 border-obsidian-border flex items-center justify-center shadow-xl shadow-black/50">
            <span className="text-white/50 font-black text-sm lg:text-lg tracking-widest italic">VS</span>
          </div>
        </div>

        {/* Track B */}
        <div className="w-full lg:max-w-md">
          <ErrorBoundary>
            <div className={`relative group transition-opacity duration-150 ${isSubmitting ? 'opacity-70' : ''}`}>
              <SwipeableTrack
                track={currentPair.track_b}
                isPlaying={isPlaying && currentTrack?.id === currentPair.track_b.id}
                onSwipeRight={swipeRightB}
                onSwipeLeft={swipeLeftB}
                onTap={() => handleTrackTap(currentPair.track_b)}
                onArchive={swipeLeftB}
                onWinner={swipeRightB}
                isLoading={isArchiving || isSubmitting}
                rankingMode="playlist"
                onTrackUpdate={updateTrackInPair}
              />
            </div>
          </ErrorBoundary>
        </div>
      </div>

      {/* Spacer for expanded PlayerBar (h-36) */}
      <div className="h-36" />

      {/* Stats Modal - only render when playlist selected */}
      {selectedPlaylistId !== null && (
        <StatsModal
          isOpen={isStatsModalOpen}
          onClose={() => setIsStatsModalOpen(false)}
          playlistId={selectedPlaylistId}
        />
      )}
    </div>
  );
}
