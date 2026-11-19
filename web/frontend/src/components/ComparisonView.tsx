import { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useComparisonStore } from '../stores/comparisonStore';
import { usePlayerStore } from '../stores/playerStore';
import { useStartComparison } from '../hooks/useComparison';
import { useComparisonDecks } from '../hooks/useComparisonDecks';
import { useComparisonShortcuts } from '../hooks/useComparisonShortcuts';
import { usePlaylists } from '../hooks/usePlaylists';
import { useIPCWebSocket } from '../hooks/useIPCWebSocket';
import { PlaylistPicker } from './PlaylistPicker';
import { activateComparisonMode, deactivateComparisonMode } from '../api/comparisons';
import { ErrorState } from './ErrorState';
import { ErrorBoundary } from './ErrorBoundary';
import { StatsModal } from './StatsModal';
import { ComparisonDeck } from './comparison/ComparisonDeck';
import { ComparisonHeader, PickHistory, ShortcutHints } from './comparison/ComparisonChrome';

interface ComparisonViewProps {
  /**
   * Playlist ID from the URL (/comparison/$playlistId).
   * When provided, the comparison session is (re)started for this playlist
   * so direct navigation and reloads load the correct playlist's comparison.
   */
  playlistId?: number;
}

export function ComparisonView({ playlistId }: ComparisonViewProps = {}): JSX.Element {
  const navigate = useNavigate();
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id);
  const isPlaying = usePlayerStore((s) => s.isPlaying);

  const {
    currentPair,
    comparisonsCompleted,
    selectedPlaylistId,
    isComparisonMode,
    updateTrackInPair,
    progress,
    history,
  } = useComparisonStore();
  const startComparison = useStartComparison();
  const decks = useComparisonDecks();

  // Connect to IPC WebSocket for remote control
  useIPCWebSocket();

  const playlistsQuery = usePlaylists();
  const playlists = playlistsQuery.data;
  const playlist = playlists?.find((p) => p.id === selectedPlaylistId);

  const [isStatsModalOpen, setIsStatsModalOpen] = useState(false);
  useComparisonShortcuts(
    { onPick: decks.pick, onFlip: decks.flip, onSkip: decks.skip, onUndo: decks.undo },
    currentPair !== null && !isStatsModalOpen,
  );

  // Start (or restore) the comparison session for the playlist in the URL.
  // Runs on direct navigation to /comparison/$playlistId and on reload, so the
  // selected playlist is preserved instead of resetting to the picker.
  const startMutate = startComparison.mutate;
  useEffect(() => {
    if (playlistId === undefined) return;
    if (selectedPlaylistId === playlistId && isComparisonMode) return;
    startMutate(playlistId);
  }, [playlistId, selectedPlaylistId, isComparisonMode, startMutate]);

  // Activate comparison mode on mount, deactivate on unmount
  // This tells the CLI backend that web-winner/web-archive should route to comparison
  useEffect(() => {
    if (isComparisonMode) {
      activateComparisonMode().catch(console.error);

      return () => {
        deactivateComparisonMode().catch(console.error);
      };
    }
  }, [isComparisonMode]);

  // Selecting a playlist updates the URL; the effect above starts the session.
  const handleSelectPlaylist = (id: number): void => {
    navigate({ to: '/comparison/$playlistId', params: { playlistId: String(id) } });
  };

  if (startComparison.isError) {
    return (
      <ErrorState
        title="Failed to Start Comparison"
        message="Unable to load tracks for comparison. Please select a playlist to try again."
      />
    );
  }

  // A playlist is in the URL but its session hasn't loaded yet (direct nav / reload).
  // Show a loading state instead of flashing the picker before startComparison resolves.
  if (playlistId !== undefined && !currentPair && !isComparisonMode) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="text-white/40 text-sm font-mono">Loading comparison...</div>
      </div>
    );
  }

  if (!currentPair && isComparisonMode) {
    // Ranking complete
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="text-center max-w-md w-full">
          <h1 className="text-2xl font-semibold text-white/90 mb-3">Ranking complete</h1>
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
            onClick={() => {
              useComparisonStore.getState().reset();
              navigate({ to: '/comparison' });
            }}
            className="w-full rounded-lg bg-obsidian-accent text-black px-6 py-3 font-semibold hover:bg-obsidian-accent/90 transition-colors"
          >
            Pick another playlist
          </button>
        </div>
      </div>
    );
  }

  if (!currentPair) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="text-center max-w-lg w-full">
          <h1 className="text-2xl font-semibold text-white/90 mb-3">Compare tracks</h1>
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

  const decksFor = [
    { track: currentPair.track_a, slot: 'a' as const, shortcut: '1' },
    { track: currentPair.track_b, slot: 'b' as const, shortcut: '2' },
  ];

  return (
    <div className="min-h-screen bg-black text-white/90 overflow-x-hidden">
      <div className="max-w-5xl mx-auto w-full px-4 py-4">
        <ComparisonHeader
          playlistName={playlist?.name}
          progress={progress}
          sessionCount={comparisonsCompleted}
          canUndo={history.length > 0 && !decks.isBusy}
          onUndo={decks.undo}
          onOpenStats={() => setIsStatsModalOpen(true)}
        />

        <div className={`flex flex-col gap-3 transition-opacity duration-150 ${decks.isBusy ? 'opacity-70' : ''}`}>
          {decksFor.map(({ track, slot, shortcut }) => (
            <ErrorBoundary key={track.id}>
              <ComparisonDeck
                track={track}
                playlistId={selectedPlaylistId ?? 0}
                shortcut={shortcut}
                isLive={currentTrackId === track.id}
                isPlaying={isPlaying && currentTrackId === track.id}
                isBusy={decks.isBusy}
                onTogglePlay={() => decks.togglePlay(track)}
                onFinish={() => decks.finish(track)}
                onPick={() => decks.pick(slot)}
                onSkip={decks.skip}
                // Smart playlists are rule-based; the DELETE route only serves manual ones
                onRemove={playlist?.type === 'manual' ? () => decks.remove(track) : undefined}
                onTrackUpdate={updateTrackInPair}
              />
            </ErrorBoundary>
          ))}
        </div>

        <PickHistory history={history} />
        <ShortcutHints />
      </div>

      {/* Spacer for expanded PlayerBar (h-36) */}
      <div className="h-36" />

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
