 import { useState, useEffect, useRef, useCallback } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { useStartSession, useRecordComparison, useArchiveTrack } from '../hooks/useComparison';
import { usePlaylists } from '../hooks/usePlaylists';
import type { TrackInfo, FoldersResponse, RecordComparisonRequest, StartSessionRequest } from '../types';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { SwipeableTrack } from './SwipeableTrack';
import { SessionProgress } from './SessionProgress';
import { WaveformPlayer } from './WaveformPlayer';
import { AutoplayToggle } from './AutoplayToggle';

import { ErrorState } from './ErrorState';
import { ErrorBoundary } from './ErrorBoundary';
import { StatsModal } from './StatsModal';
import { getFolders } from '../api/tracks';
import { selectTrack } from '../api/comparisons';

export function ComparisonView() {
  const {
    currentTrack,
    isPlaying,
    currentPair,
    comparisonsCompleted,
    priorityPathPrefix,
    rankingMode: sessionRankingMode,
    selectedPlaylistId: sessionSelectedPlaylistId,
    setPriorityPath,
    selectAndPlay,
    setIsPlaying,
    isComparisonMode,
    updateTrackInPair,
  } = useComparisonStore();
  const startSession = useStartSession();
  const recordComparison = useRecordComparison();
  const archiveTrack = useArchiveTrack();
  const { playTrack } = useAudioPlayer(currentTrack);

  // Connect to IPC WebSocket for remote control
  useIPCWebSocket();

  // Handle priority folder change during active session
  const handlePriorityChange = (newPriorityPath: string | null) => {
    if (!currentPair) return;

    // Update priority path in store without restarting session
    setPriorityPath(newPriorityPath);
  };

  // Folder selection state
  // Playlist selection state
  const playlistsQuery = usePlaylists();
  const playlists = playlistsQuery.data;
  const [setupRankingMode, setSetupRankingMode] = useState<'global' | 'playlist'>('global');
  const [setupSelectedPlaylistId, setSetupSelectedPlaylistId] = useState<number | null>(null);
  const [foldersData, setFoldersData] = useState<FoldersResponse | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<string>('');

  // Stats modal state
  const [isStatsModalOpen, setIsStatsModalOpen] = useState(false);

  // Fetch folders on mount
  useEffect(() => {
    getFolders()
      .then(setFoldersData)
      .catch((err) => console.error('Failed to load folders:', err));
  }, []);

  // Ref for currentTrack to avoid dependency in handleTrackFinish
  const currentTrackRef = useRef(currentTrack);
  useEffect(() => {
    currentTrackRef.current = currentTrack;
  }, [currentTrack]);

  const handleStartSession = () => {
    const priorityPath = selectedFolder && foldersData
      ? `${foldersData.root}/${selectedFolder}`
      : undefined;

    if (setupRankingMode === 'playlist' && !setupSelectedPlaylistId) {
      alert('Please select a playlist for playlist ranking mode');
      return;
    }

    const sessionRequest: StartSessionRequest = {
      priority_path_prefix: priorityPath,
    };

    if (setupRankingMode === 'playlist' && setupSelectedPlaylistId) {
      sessionRequest.ranking_mode = 'playlist';
      sessionRequest.playlist_id = setupSelectedPlaylistId;
    }

    startSession.mutate(sessionRequest);
  }

  const handleTrackTap = (track: TrackInfo) => {
    if (currentTrack?.id === track.id) {
      setIsPlaying(!isPlaying);  // Toggle play/pause for same track
      selectTrack(track.id, !isPlaying); // Broadcast play/pause state
    } else {
      selectAndPlay(track);       // Switch track and play
      selectTrack(track.id, true); // Broadcast track selection
    }
  };

  const handleSwipeRight = useCallback((trackId: number) => {
    if (!currentPair) return;

    const request: RecordComparisonRequest = {
      session_id: currentPair.session_id,
      track_a_id: currentPair.track_a.id,
      track_b_id: currentPair.track_b.id,
      winner_id: trackId,
      priority_path_prefix: priorityPathPrefix ?? undefined,
    };

    // Include ranking mode info if in playlist mode
    if (sessionRankingMode === 'playlist' && sessionSelectedPlaylistId) {
      request.ranking_mode = 'playlist';
      request.playlist_id = sessionSelectedPlaylistId;
    }

    recordComparison.mutate(request);
  }, [currentPair, sessionRankingMode, sessionSelectedPlaylistId, priorityPathPrefix, recordComparison]);

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

  /**
   * Handles automatic track switching in comparison mode when one track finishes playing.
   * This creates a seamless looping experience where users can continuously compare
   * tracks without manual intervention - when track A finishes, track B starts automatically,
   * and vice versa, allowing for uninterrupted A/B comparison during ELO rating sessions.
   */
  const handleTrackFinish = useCallback(() => {
    if (!currentPair || !currentTrackRef.current || !isComparisonMode) return;

    // Determine which track just finished and play the other one
    const otherTrack = currentTrackRef.current.id === currentPair.track_a.id
      ? currentPair.track_b
      : currentPair.track_a;

    // Automatically play the other track
    playTrack(otherTrack);
  }, [currentPair, isComparisonMode, playTrack]); // currentTrack removed from deps

  if (startSession.isError) {
    return (
      <ErrorState
        title="Failed to Start Session"
        message="Unable to load tracks for comparison. Please check your music library."
        onRetry={handleStartSession}
      />
    );
  }

  if (!currentPair) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="text-center max-w-md w-full">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-indigo-500 mb-4">
            Music Minion
          </h1>
          <p className="text-slate-400 mb-8 text-lg">
          {/* Ranking mode selector */}
          <div className="mb-6">
            <label className="block text-slate-400 text-sm mb-3 text-left">
              Ranking Mode
            </label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  name="rankingMode"
                  value="global"
                  checked={setupRankingMode === 'global'}
                  onChange={(e) => setSetupRankingMode(e.target.value as 'global' | 'playlist')}
                  className="mr-2 text-indigo-500"
                />
                Global Ranking
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="rankingMode"
                  value="playlist"
                  checked={setupRankingMode === 'playlist'}
                  onChange={(e) => setSetupRankingMode(e.target.value as 'global' | 'playlist')}
                  className="mr-2 text-indigo-500"
                />
                Playlist Ranking
              </label>
            </div>
          </div>

          {/* Playlist selector */}
          {setupRankingMode === 'playlist' && playlists && playlists.length > 0 && (
            <div className="mb-6">
              <label className="block text-slate-400 text-sm mb-2 text-left">
                Select Playlist
              </label>
              <select
                value={setupSelectedPlaylistId ?? ''}
                onChange={(e) => setSetupSelectedPlaylistId(e.target.value ? Number(e.target.value) : null)}
                className="w-full bg-slate-800 border border-slate-700 text-slate-100 px-4 py-3 rounded-lg focus:outline-none focus:border-indigo-500 transition-colors"
              >
                <option value="">Choose a playlist...</option>
                {playlists.map((playlist) => (
                  <option key={playlist.id} value={playlist.id}>
                    {playlist.name}
                  </option>
                ))}
              </select>
              {setupSelectedPlaylistId && (
                <p className="text-emerald-400 text-xs mt-2 text-left font-mono">
                  Only tracks from this playlist will be ranked
                </p>
              )}
            </div>
          )}
          </p>

          {/* Priority folder selector */}
          {foldersData && foldersData.folders.length > 0 && (
            <div className="mb-6">
              <label className="block text-slate-400 text-sm mb-2 text-left">
                Priority Folder (optional)
              </label>
              <select
                value={selectedFolder}
                onChange={(e) => setSelectedFolder(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-slate-100 px-4 py-3 rounded-lg focus:outline-none focus:border-indigo-500 transition-colors"
              >
                <option value="">All folders (no priority)</option>
                {foldersData.folders.map((folder) => (
                  <option key={folder} value={folder}>
                    {folder}
                  </option>
                ))}
              </select>
              {selectedFolder && (
                <p className="text-emerald-400 text-xs mt-2 text-left font-mono">
                  Tracks from {selectedFolder} will appear in every comparison
                </p>
              )}
            </div>
          )}

          <button
            onClick={handleStartSession}
            disabled={startSession.isPending}
            className="w-full bg-indigo-600 text-white px-6 py-4 rounded-xl font-bold text-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-900/50"
          >
            {startSession.isPending ? 'Starting...' : 'Start Session'}
          </button>
        </div>
      </div>
    );
  }

  // Only show loading for archive (which removes track from playlist)
  // Recording comparison uses optimistic UI - no loading state
  const isArchiving = archiveTrack.isPending;
  const isSubmitting = recordComparison.isPending;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 overflow-x-hidden">
      {/* Header */}
      <div className="bg-slate-900/50 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="flex items-center justify-between">
              <SessionProgress
                completed={comparisonsCompleted}
                priorityPath={priorityPathPrefix ?? undefined}
                onPriorityChange={handlePriorityChange}
                folders={foldersData ?? undefined}
                rankingMode={sessionRankingMode ?? 'global'}
                playlists={playlists ?? []}
                selectedPlaylistId={sessionSelectedPlaylistId}
              />
              <div className="flex items-center gap-4">
                <AutoplayToggle />
                <button
                  onClick={() => setIsStatsModalOpen(true)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-100 rounded-lg transition-colors text-xs font-medium"
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
                rankingMode={sessionRankingMode ?? 'global'}
                onTrackUpdate={updateTrackInPair}
              />
            </div>
          </ErrorBoundary>
        </div>

        {/* VS Badge */}
        <div className="flex flex-col items-center justify-center z-10 shrink-0">
          <div className="w-12 h-12 lg:w-16 lg:h-16 rounded-full bg-slate-900 border-2 border-slate-700 flex items-center justify-center shadow-xl shadow-black/50">
            <span className="text-slate-500 font-black text-sm lg:text-lg tracking-widest italic">VS</span>
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
                rankingMode={sessionRankingMode ?? 'global'}
                onTrackUpdate={updateTrackInPair}
              />
            </div>
          </ErrorBoundary>
        </div>
      </div>

      {/* Persistent Player Bar */}
      {currentPair && (
        <div className="fixed bottom-0 inset-x-0 bg-slate-900/90 backdrop-blur-xl border-t border-slate-800 p-3 pb-6 lg:pb-3 z-50">
          <div className="max-w-3xl mx-auto flex flex-col gap-1">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span className="font-mono">{isPlaying ? 'NOW PLAYING' : 'PAUSED'}</span>
                <span className="truncate max-w-[200px] text-slate-200">
                  {currentTrack ? `${currentTrack.artist} - ${currentTrack.title}` : ''}
                </span>
              </div>

              {/* Waveform - never unmount during loading to preserve playback */}
              <div className="h-16 w-full bg-slate-950/50 rounded-lg overflow-hidden relative border border-slate-800">
                {currentTrack ? (
                   <WaveformPlayer
                     track={currentTrack}
                     isPlaying={isPlaying}
                     onTogglePlayPause={() => handleTrackTap(currentTrack)}
                     onFinish={handleTrackFinish}
                   />
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-500">
                    No track selected
                  </div>
                )}
              </div>

          </div>
        </div>
      )}
      
      {/* Spacer for bottom player */}
      <div className="h-24 lg:h-20" />

      {/* Stats Modal */}
      <StatsModal
        isOpen={isStatsModalOpen}
        onClose={() => setIsStatsModalOpen(false)}
        playlistId={sessionRankingMode === 'playlist' ? sessionSelectedPlaylistId : null}
      />
    </div>
  );
}
