import { useCallback } from 'react';
import { useState, useEffect } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { useStartSession, useRecordComparison, useArchiveTrack } from '../hooks/useComparison';
import type { TrackInfo, FoldersResponse } from '../types';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { SwipeableTrack } from './SwipeableTrack';
import { SessionProgress } from './SessionProgress';
import { WaveformPlayer } from './WaveformPlayer';
import { QuickSeekBar } from './QuickSeekBar';
import { ErrorState } from './ErrorState';
import { TrackActions } from './TrackActions';
import { ErrorBoundary } from './ErrorBoundary';
import { getFolders } from '../api/tracks';

export function ComparisonView() {
  const { currentPair, playingTrack, comparisonsCompleted, priorityPathPrefix } = useComparisonStore();
  const startSession = useStartSession();
  const recordComparison = useRecordComparison();
  const archiveTrack = useArchiveTrack();
  const { playTrack, pauseTrack } = useAudioPlayer(playingTrack);

  // Folder selection state
  const [foldersData, setFoldersData] = useState<FoldersResponse | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<string>('');

  // Fetch folders on mount
  useEffect(() => {
    getFolders()
      .then(setFoldersData)
      .catch((err) => console.error('Failed to load folders:', err));
  }, []);

  // Track the active waveform track (persists when paused)
  const [waveformTrack, setWaveformTrack] = useState<TrackInfo | null>(null);

  // Update waveform track ONLY when a new track starts playing
  useEffect(() => {
    if (playingTrack !== null) {
      setWaveformTrack(playingTrack);
    }
  }, [playingTrack]);

  const handleStartSession = () => {
    const priorityPath = selectedFolder && foldersData
      ? `${foldersData.root}/${selectedFolder}`
      : undefined;
    startSession.mutate({
      priority_path_prefix: priorityPath,
    });
  };

  const handleTrackTap = (track: TrackInfo) => {
    if (playingTrack?.id === track.id) {
      // If this track is already playing, pause it
      pauseTrack();
    } else {
      // Otherwise, play this track
      playTrack(track);
    }
  };

  const handleSwipeRight = (trackId: number) => {
    if (!currentPair) return;
    recordComparison.mutate({
      session_id: currentPair.session_id,
      track_a_id: currentPair.track_a.id,
      track_b_id: currentPair.track_b.id,
      winner_id: trackId,
      priority_path_prefix: priorityPathPrefix ?? undefined,
    });
  };

  const handleSwipeLeft = (trackId: number) => {
    archiveTrack.mutate(trackId);
  };

  const handleWaveformSeek = useCallback(() => {
    // Handle seek if needed
  }, []);

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
            Curate your library with precision.
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

  // Only show loading for archive (which removes track from library)
  // Recording comparison uses optimistic UI - no loading state
  const isArchiving = archiveTrack.isPending;
  const isSubmitting = recordComparison.isPending;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 overflow-x-hidden">
      {/* Header */}
      <div className="bg-slate-900/50 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <SessionProgress
            completed={comparisonsCompleted}
          />
          {priorityPathPrefix && (
            <div className="mt-2 text-xs text-emerald-400 font-mono truncate">
              Prioritizing: {priorityPathPrefix}
            </div>
          )}
        </div>
      </div>

      {/* Main Comparison Area */}
      <div className="flex-1 max-w-7xl mx-auto w-full p-4 flex flex-col lg:flex-row items-center justify-center gap-6 lg:gap-12 relative">

        {/* Track A */}
        <div className="w-full lg:max-w-md flex flex-col gap-4">
          <ErrorBoundary>
            <div className={`relative group transition-opacity duration-150 ${isSubmitting ? 'opacity-70' : ''}`}>
              <SwipeableTrack
                track={currentPair.track_a}
                isPlaying={playingTrack?.id === currentPair.track_a.id}
                onSwipeRight={() => handleSwipeRight(currentPair.track_a.id)}
                onSwipeLeft={() => handleSwipeLeft(currentPair.track_a.id)}
                onTap={() => handleTrackTap(currentPair.track_a)}
              />
              <TrackActions
                trackId={currentPair.track_a.id}
                onArchive={handleSwipeLeft}
                onWinner={handleSwipeRight}
                isLoading={isArchiving || isSubmitting}
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
        <div className="w-full lg:max-w-md flex flex-col gap-4">
          <ErrorBoundary>
            <div className={`relative group transition-opacity duration-150 ${isSubmitting ? 'opacity-70' : ''}`}>
              <SwipeableTrack
                track={currentPair.track_b}
                isPlaying={playingTrack?.id === currentPair.track_b.id}
                onSwipeRight={() => handleSwipeRight(currentPair.track_b.id)}
                onSwipeLeft={() => handleSwipeLeft(currentPair.track_b.id)}
                onTap={() => handleTrackTap(currentPair.track_b)}
              />
              <TrackActions
                trackId={currentPair.track_b.id}
                onArchive={handleSwipeLeft}
                onWinner={handleSwipeRight}
                isLoading={isArchiving || isSubmitting}
              />
            </div>
          </ErrorBoundary>
        </div>
      </div>

      {/* Mobile Action Hints (Fixed Bottom) */}
      <div className="lg:hidden p-4 text-center">
        <p className="text-slate-500 text-sm font-medium animate-pulse">
          Swipe Card Right to Win • Left to Archive
        </p>
      </div>

      {/* Persistent Player Bar */}
      {currentPair && (
        <div className="fixed bottom-0 inset-x-0 bg-slate-900/90 backdrop-blur-xl border-t border-slate-800 p-4 pb-8 lg:pb-4 z-50">
          <div className="max-w-3xl mx-auto flex flex-col gap-2">
             <div className="flex items-center justify-between text-xs text-slate-400 px-1">
               <span className="font-mono">{playingTrack ? 'NOW PLAYING' : 'PAUSED'}</span>
               <span className="truncate max-w-[200px] text-slate-200">
                 {playingTrack ? `${playingTrack.artist} - ${playingTrack.title}` : ''}
               </span>
             </div>

             {/* Waveform - never unmount during loading to preserve playback */}
             <div className="h-16 w-full bg-slate-950/50 rounded-lg overflow-hidden relative border border-slate-800">
               {waveformTrack ? (
                 <WaveformPlayer
                   trackId={waveformTrack.id}
                   onSeek={handleWaveformSeek}
                   isActive={playingTrack?.id === waveformTrack.id}
                   onTogglePlayPause={() => handleTrackTap(waveformTrack)}
                 />
               ) : (
                 <div className="flex items-center justify-center h-full text-slate-500">
                   No track selected
                 </div>
               )}
             </div>
            
            {/* Simple Seek Bar as backup/control */}
             <QuickSeekBar
                onSeek={() => {}} // Hook up real seek later
                currentPercent={0} 
                className="h-1 bg-slate-800 rounded-full overflow-hidden"
              />
          </div>
        </div>
      )}
      
      {/* Spacer for bottom player */}
      <div className="h-32 lg:h-24" />
    </div>
  );
}
