import { useEffect } from 'react';
import { useStats } from '../hooks/useStats';
import { StatCard } from './StatCard';
import { GenreChart } from './GenreChart';
import { Leaderboard } from './Leaderboard';
import { ErrorState } from './ErrorState';

interface StatsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

function StatCardSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 animate-pulse">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-8 h-8 bg-slate-800 rounded"></div>
        <div className="w-16 h-9 bg-slate-800 rounded"></div>
      </div>
      <div className="w-20 h-4 bg-slate-800 rounded mb-1"></div>
      <div className="w-16 h-3 bg-slate-800 rounded"></div>
    </div>
  );
}

function StatsSkeleton() {
  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-100 mb-2">Library Statistics</h2>
        <p className="text-slate-400">Track your music curation progress</p>
      </div>

      {/* Stat Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <div className="h-6 bg-slate-800 rounded w-48 mb-4 animate-pulse"></div>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-between">
                  <div className="w-24 h-4 bg-slate-800 rounded animate-pulse"></div>
                  <div className="w-16 h-4 bg-slate-800 rounded animate-pulse"></div>
                </div>
                <div className="w-full h-6 bg-slate-800 rounded-full animate-pulse"></div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <div className="h-6 bg-slate-800 rounded w-40 mb-4 animate-pulse"></div>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex justify-between items-center py-2 border-b border-slate-800/50">
                <div className="flex items-center gap-3">
                  <div className="w-6 h-4 bg-slate-800 rounded animate-pulse"></div>
                  <div className="space-y-1">
                    <div className="w-32 h-4 bg-slate-800 rounded animate-pulse"></div>
                    <div className="w-24 h-3 bg-slate-800 rounded animate-pulse"></div>
                  </div>
                </div>
                <div className="w-12 h-4 bg-slate-800 rounded animate-pulse"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function StatsModal({ isOpen, onClose }: StatsModalProps) {
  const { data: stats, isLoading, isError, refetch } = useStats();

  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  const handleRetry = () => {
    refetch();
  };

  const handleBackdropClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div className="relative max-w-6xl w-full mx-4 max-h-[90vh] bg-slate-950 border border-slate-800 rounded-xl shadow-2xl overflow-hidden">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 w-8 h-8 flex items-center justify-center bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 rounded-full transition-colors"
          aria-label="Close modal"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Scrollable content */}
        <div className="overflow-y-auto max-h-[90vh]">
          {isError ? (
            <div className="p-6">
              <ErrorState
                title="Failed to Load Statistics"
                message="Unable to fetch library statistics. Please check your connection and try again."
                onRetry={handleRetry}
              />
            </div>
          ) : isLoading || !stats ? (
            <StatsSkeleton />
          ) : (
            <div className="p-6">
              {/* Header */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-slate-100 mb-2">Library Statistics</h2>
                <p className="text-slate-400">Track your music curation progress</p>
              </div>

              {/* Stat Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                <StatCard
                  icon="🎵"
                  value={stats.total_tracks}
                  label="Total Tracks"
                  subtitle="In your library"
                />
                <StatCard
                  icon="⚖️"
                  value={stats.total_comparisons}
                  label="Comparisons"
                  subtitle="Total ratings made"
                />
                <StatCard
                  icon="📊"
                  value={`${stats.coverage_percent.toFixed(1)}%`}
                  label="Coverage"
                  subtitle={`${stats.compared_tracks} tracks rated`}
                />
                 <StatCard
                   icon="📈"
                   value={stats.average_comparisons_per_day.toFixed(1)}
                   label="Daily Average"
                   subtitle="Comparisons per day"
                 />
                 {stats.prioritized_tracks && (
                   <StatCard
                     icon="⭐"
                     value={`${stats.prioritized_coverage_percent?.toFixed(1)}%`}
                     label="Priority Coverage"
                     subtitle={`${stats.prioritized_tracks} tracks prioritized`}
                   />
                 )}
              </div>

              {/* Charts Section */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                  <GenreChart genres={stats.top_genres} />
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                  <Leaderboard entries={stats.leaderboard} />
                </div>
              </div>

               {/* Additional Stats */}
               <div className="mt-6 space-y-3">
                 {stats.estimated_days_to_coverage && (
                   <div className="text-center">
                     <p className="text-slate-400">
                       Estimated {stats.estimated_days_to_coverage} days to reach full coverage
                       at current pace
                     </p>
                   </div>
                 )}
                 {stats.prioritized_estimated_days && (
                   <div className="text-center">
                     <p className="text-slate-400">
                       Estimated {stats.prioritized_estimated_days} days to reach full priority coverage
                       at current pace
                     </p>
                   </div>
                 )}
               </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}