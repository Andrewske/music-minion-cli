import { useState } from 'react';

export interface FailureInfo {
  video_id: string;
  title: string;
  error: string;
}

interface ProgressBarProps {
  progress: number;
  currentStep?: 'downloading' | 'processing' | null;
  currentItem?: number | null;
  totalItems?: number | null;
  failures?: FailureInfo[];
}

export function ProgressBar({
  progress,
  currentStep,
  currentItem,
  totalItems,
  failures = [],
}: ProgressBarProps) {
  const [showAllFailures, setShowAllFailures] = useState(false);

  // Build status text based on context
  const getStatusText = (): string => {
    if (totalItems && currentItem) {
      // Playlist mode
      const stepText = currentStep === 'downloading' ? 'Downloading' : 'Processing';
      return `${stepText} video ${currentItem} of ${totalItems}...`;
    }
    // Single video mode
    if (currentStep === 'downloading') {
      return 'Downloading video...';
    }
    if (currentStep === 'processing') {
      return 'Processing metadata...';
    }
    return 'Starting...';
  };

  const visibleFailures = showAllFailures ? failures : failures.slice(0, 3);
  const hiddenCount = failures.length - 3;

  return (
    <div className="space-y-3">
      {/* Progress bar container */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-sm">
          <span className="text-slate-300">{getStatusText()}</span>
          <span className="text-slate-400 font-mono">{progress}%</span>
        </div>

        {/* Bar */}
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Live failures */}
      {failures.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm text-red-400 font-medium">
            {failures.length} failed
          </div>
          <div className="space-y-1">
            {visibleFailures.map((failure) => (
              <div
                key={failure.video_id}
                className="text-sm text-red-400/80 bg-red-900/10 border border-red-500/10 rounded px-3 py-2"
              >
                <span className="mr-2">❌</span>
                <span className="font-medium">{failure.title}</span>
                <span className="text-red-400/60"> — {failure.error}</span>
              </div>
            ))}
          </div>

          {/* Show more/less toggle */}
          {failures.length > 3 && (
            <button
              type="button"
              onClick={() => setShowAllFailures(!showAllFailures)}
              className="text-sm text-slate-400 hover:text-slate-300 underline"
            >
              {showAllFailures ? 'Show less' : `Show ${hiddenCount} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
