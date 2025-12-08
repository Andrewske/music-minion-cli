import { useComparisonStore } from '../stores/comparisonStore';
import { useStartSession } from '../hooks/useComparison';
import { TrackCard } from './TrackCard';
import { SessionProgress } from './SessionProgress';

export function ComparisonView() {
  const { currentPair, playingTrackId, comparisonsCompleted, targetComparisons, setPlaying } = useComparisonStore();
  const startSession = useStartSession();

  const handleStartSession = () => {
    startSession.mutate({});
  };

  const handleTrackTap = (trackId: number) => {
    setPlaying(trackId === playingTrackId ? null : trackId);
  };



  if (!currentPair) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            Music Minion
          </h1>
          <p className="text-gray-600 mb-6">
            Rate your music collection by comparing tracks
          </p>
          <button
            onClick={handleStartSession}
            disabled={startSession.isPending}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation"
          >
            {startSession.isPending ? 'Starting...' : 'Start Comparison Session'}
          </button>
          {startSession.isError && (
            <p className="text-red-600 mt-2">
              Failed to start session. Please try again.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with progress */}
      <div className="bg-white shadow-sm">
        <SessionProgress
          completed={comparisonsCompleted}
          target={targetComparisons}
        />
      </div>

      {/* Comparison cards */}
      <div className="flex flex-col p-4 space-y-4">
        <TrackCard
          track={currentPair.track_a}
          isPlaying={playingTrackId === currentPair.track_a.id}
          onTap={() => handleTrackTap(currentPair.track_a.id)}
        />

        <div className="text-center py-2">
          <span className="text-gray-500 text-sm font-medium">VS</span>
        </div>

        <TrackCard
          track={currentPair.track_b}
          isPlaying={playingTrackId === currentPair.track_b.id}
          onTap={() => handleTrackTap(currentPair.track_b.id)}
        />
      </div>

      {/* Instructions */}
      <div className="px-4 pb-4">
        <div className="bg-blue-50 rounded-lg p-4 text-center">
          <p className="text-sm text-blue-800">
            Tap to play • Swipe right to choose winner • Swipe left to archive
          </p>
        </div>
      </div>
    </div>
  );
}