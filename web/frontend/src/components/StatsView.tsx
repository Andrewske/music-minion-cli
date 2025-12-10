import { useStats } from '../hooks/useStats';
import { StatCard } from './StatCard';
import { GenreChart } from './GenreChart';
import { Leaderboard } from './Leaderboard';
import { ErrorState } from './ErrorState';

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
    <div className="min-h-screen bg-slate-950 p-4">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-100 mb-2">Library Statistics</h1>
          <p className="text-slate-400">Track your music curation progress</p>
        </div>

        {/* Stat Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatCardSkeleton key={i} />
          ))}
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
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
    </div>
  );
}

export function StatsView() {
  const { data: stats, isLoading, isError, refetch } = useStats();

  const handleRetry = () => {
    refetch();
  };

  if (isError) {
    return (
      <ErrorState
        title="Failed to Load Statistics"
        message="Unable to fetch library statistics. Please check your connection and try again."
        onRetry={handleRetry}
      />
    );
  }

  if (isLoading || !stats) {
    return <StatsSkeleton />;
  }

  return (
    <div className="min-h-screen bg-slate-950 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-100 mb-2">Library Statistics</h1>
          <p className="text-slate-400">Track your music curation progress</p>
        </div>

        {/* Stat Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
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
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <GenreChart genres={stats.top_genres} />
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <Leaderboard entries={stats.leaderboard} />
          </div>
        </div>

        {/* Additional Stats */}
        {stats.estimated_days_to_coverage && (
          <div className="mt-8 text-center">
            <p className="text-slate-400">
              Estimated {stats.estimated_days_to_coverage} days to reach full coverage
              at current pace
            </p>
          </div>
        )}
      </div>
    </div>
  );
}