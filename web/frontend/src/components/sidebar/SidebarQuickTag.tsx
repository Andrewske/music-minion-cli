import { useEffect } from 'react';
import { ChevronLeft, ChevronRight, Minus } from 'lucide-react';
import { SidebarSection } from './SidebarSection';
import { usePlayerStore } from '../../stores/playerStore';
import { useQuickTagStore } from '../../stores/quickTagStore';

interface SidebarQuickTagProps {
  sidebarExpanded: boolean;
}

export function SidebarQuickTag({ sidebarExpanded }: SidebarQuickTagProps): JSX.Element {
  const { currentTrack } = usePlayerStore();
  const {
    dimensions,
    currentDimensionIndex,
    isLoading,
    error,
    loadDimensions,
    vote,
    nextDimension,
    prevDimension,
  } = useQuickTagStore();

  // Derive currentDimension via selector
  const currentDimension = useQuickTagStore(
    (s) => s.dimensions[s.currentDimensionIndex] ?? null
  );

  // Initialize dimensions on mount
  useEffect(() => {
    if (dimensions.length === 0 && !isLoading) {
      loadDimensions();
    }
  }, [dimensions.length, isLoading, loadDimensions]);

  const handleVote = (voteValue: -1 | 0 | 1): void => {
    if (!currentTrack) return;
    vote(currentTrack.id, voteValue);
  };

  return (
    <SidebarSection title="Quick Tag" sidebarExpanded={sidebarExpanded}>
      <div className="flex flex-col items-center gap-3 py-2">
        {/* Empty state: no track playing */}
        {!currentTrack && (
          <p className="text-sm text-white/40 text-center px-4">
            Play a track to start tagging
          </p>
        )}

        {/* Loading state */}
        {currentTrack && isLoading && (
          <p className="text-sm text-white/40 text-center">Loading dimensions...</p>
        )}

        {/* Error state */}
        {currentTrack && error && (
          <p className="text-sm text-red-400 text-center px-4">{error}</p>
        )}

        {/* Main voting UI */}
        {currentTrack && !isLoading && !error && currentDimension && (
          <>
            {/* Dimension navigation */}
            <div className="flex items-center gap-2">
              <button
                onClick={prevDimension}
                className="p-1 text-white/60 hover:text-white transition-colors"
                aria-label="Previous dimension"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-white/60">
                {currentDimensionIndex + 1}/{dimensions.length}
              </span>
              <button
                onClick={nextDimension}
                className="p-1 text-white/60 hover:text-white transition-colors"
                aria-label="Next dimension"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Dimension label */}
            <p className="text-xs text-white/50 text-center">
              {currentDimension.label}
            </p>

            {/* Vote buttons */}
            <div className="flex items-center justify-center gap-6">
              <button
                onClick={() => handleVote(-1)}
                className="text-2xl hover:scale-125 transition-transform"
                aria-label={`Vote ${currentDimension.label.split(' vs ')[0]}`}
              >
                {currentDimension.leftEmoji}
              </button>
              <button
                onClick={() => handleVote(0)}
                className="p-2 text-white/40 hover:text-white/60 hover:scale-125 transition-all"
                aria-label="Skip this dimension"
              >
                <Minus className="w-5 h-5" />
              </button>
              <button
                onClick={() => handleVote(1)}
                className="text-2xl hover:scale-125 transition-transform"
                aria-label={`Vote ${currentDimension.label.split(' vs ')[1]}`}
              >
                {currentDimension.rightEmoji}
              </button>
            </div>

            {/* Progress dots */}
            <div className="flex items-center gap-1">
              {dimensions.map((_, idx) => (
                <div
                  key={idx}
                  className={`w-1.5 h-1.5 rounded-full ${
                    idx === currentDimensionIndex
                      ? 'bg-obsidian-accent'
                      : 'bg-white/20'
                  }`}
                />
              ))}
            </div>
          </>
        )}

        {/* No dimensions loaded after loading complete */}
        {currentTrack && !isLoading && !error && dimensions.length === 0 && (
          <p className="text-sm text-white/40 text-center px-4">
            No dimensions available
          </p>
        )}
      </div>
    </SidebarSection>
  );
}
