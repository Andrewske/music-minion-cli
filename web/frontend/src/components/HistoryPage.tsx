import { useState, useEffect } from 'react';
import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { getHistory, getStats, getTopTracks } from '../api/history';
import { StatCard } from './StatCard';
import type { HistoryEntry, TopTrack } from '../api/history';

type DatePreset = 'last7' | 'last30' | 'all';

interface DateRange {
  startDate?: string;
  endDate?: string;
}

function getDateRange(preset: DatePreset): DateRange {
  const now = new Date();
  const today = now.toISOString().split('T')[0];

  switch (preset) {
    case 'last7': {
      const sevenDaysAgo = new Date(now);
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      return { startDate: sevenDaysAgo.toISOString().split('T')[0], endDate: today };
    }
    case 'last30': {
      const thirtyDaysAgo = new Date(now);
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      return { startDate: thirtyDaysAgo.toISOString().split('T')[0], endDate: today };
    }
    case 'all':
      return {};
  }
}

function getPresetDays(preset: DatePreset): number | undefined {
  switch (preset) {
    case 'last7': return 7;
    case 'last30': return 30;
    case 'all': return undefined;
  }
}

function formatDuration(durationMs: number): string {
  const totalSeconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function getEndReasonIcon(endReason: string | null): string {
  switch (endReason) {
    case 'skip':
      return '⏭️';
    case 'completed':
      return '✓';
    case 'new_play':
      return '▶️';
    default:
      return '';
  }
}

interface InlineErrorStateProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

function InlineErrorState({ title, message, onRetry }: InlineErrorStateProps) {
  return (
    <div className="bg-obsidian-surface border border-red-900/50 p-6">
      <div className="text-center">
        <div className="text-4xl mb-3">⚠️</div>
        <h3 className="text-lg font-semibold text-red-400 mb-2">{title}</h3>
        <p className="text-white/60 text-sm mb-4">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="bg-obsidian-border hover:bg-white/5 text-white px-4 py-2 text-sm font-medium transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="bg-obsidian-surface border border-obsidian-border p-8 text-center">
      <div className="text-4xl mb-3">📊</div>
      <p className="text-white/60">{message}</p>
    </div>
  );
}

export function HistoryPage(): JSX.Element {
  const [datePreset, setDatePreset] = useState<DatePreset>('last30');

  const dateRange = getDateRange(datePreset);
  const days = getPresetDays(datePreset);

  // Fetch history with infinite pagination
  const {
    data: historyData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
    error: historyError,
    refetch: refetchHistory,
  } = useInfiniteQuery({
    queryKey: ['history', dateRange.startDate, dateRange.endDate],
    queryFn: ({ pageParam }) =>
      getHistory({
        limit: 50,
        offset: pageParam,
        startDate: dateRange.startDate,
        endDate: dateRange.endDate,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      return lastPage.length === 50 ? allPages.length * 50 : undefined;
    },
  });

  // Fetch stats
  const {
    data: stats,
    isLoading: isStatsLoading,
    isError: isStatsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ['stats', days],
    queryFn: () => getStats(days ?? 30),
  });

  // Fetch top tracks
  const {
    data: topTracksData,
    isLoading: isTopTracksLoading,
    isError: isTopTracksError,
    refetch: refetchTopTracks,
  } = useQuery({
    queryKey: ['topTracks', days],
    queryFn: () => getTopTracks(10, days ?? 30),
  });

  // Local state for top tracks to handle emoji updates
  const [topTracks, setTopTracks] = useState<TopTrack[]>([]);

  // Local state for history entries to handle emoji updates
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);

  // Sync local state with query data
  useEffect(() => {
    if (topTracksData) {
      setTopTracks(topTracksData);
    }
  }, [topTracksData]);

  // Sync history entries with infinite query data
  useEffect(() => {
    if (historyData?.pages) {
      setHistoryEntries(historyData.pages.flat());
    }
  }, [historyData]);


  return (
    <div className="min-h-screen bg-black text-white p-6">
      <h1 className="text-2xl font-bold mb-6">Listening History</h1>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-4">
        {/* Date Preset Buttons */}
        <div>
          <label className="block text-sm text-white/60 mb-2">Time Period</label>
          <div className="flex gap-2">
            {(['last7', 'last30', 'all'] as DatePreset[]).map((preset) => {
              const labels: Record<DatePreset, string> = {
                last7: 'Last 7 Days',
                last30: 'Last 30 Days',
                all: 'All Time',
              };
              return (
                <button
                  key={preset}
                  onClick={() => setDatePreset(preset)}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    datePreset === preset
                      ? 'bg-obsidian-accent text-white'
                      : 'bg-obsidian-border text-white/60 hover:bg-white/5'
                  }`}
                >
                  {labels[preset]}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {isStatsError ? (
        <div className="mb-6">
          <InlineErrorState
            title="Failed to Load Stats"
            message="Unable to fetch station statistics. Please try again."
            onRetry={refetchStats}
          />
        </div>
      ) : isStatsLoading ? (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-obsidian-surface border border-obsidian-border p-6 animate-pulse">
              <div className="h-20"></div>
            </div>
          ))}
        </div>
      ) : stats ? (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard
            icon="🎵"
            value={stats.total_plays}
            label="Total Plays"
            subtitle="All listening sessions"
          />
          <StatCard
            icon="⏱️"
            value={`${(stats.total_minutes / 60).toFixed(1)}h`}
            label="Hours Listened"
            subtitle={`${stats.total_minutes.toFixed(0)} minutes`}
          />
          <StatCard
            icon="🎼"
            value={stats.unique_tracks}
            label="Unique Tracks"
            subtitle="Different tracks played"
          />
        </div>
      ) : null}

      {/* Top Tracks Section */}
      <div className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Top Tracks</h2>
          {isTopTracksError ? (
            <InlineErrorState
              title="Failed to Load Top Tracks"
              message="Unable to fetch top tracks. Please try again."
              onRetry={refetchTopTracks}
            />
          ) : isTopTracksLoading ? (
            <div className="bg-obsidian-surface border border-obsidian-border p-6 animate-pulse">
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-12"></div>
                ))}
              </div>
            </div>
          ) : topTracks && topTracks.length > 0 ? (
            <div className="bg-obsidian-surface border border-obsidian-border p-6">
              <div className="space-y-3">
                {topTracks.map((track, index) => (
                  <div
                    key={`${track.track_id}-${index}`}
                    className="flex justify-between items-center py-2 border-b border-obsidian-border/50 last:border-0"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <span className="text-white/60 text-sm w-6">#{index + 1}</span>
                      <div className="min-w-0 flex-1">
                        <div className="text-white/90 font-medium truncate">
                          {track.track_title || 'Unknown Track'}
                        </div>
                        <div className="text-white/60 text-sm truncate">
                          {track.track_artist || 'Unknown Artist'}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-2">
                      <span className="text-white/60 text-sm whitespace-nowrap">
                        {track.play_count} plays
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState message="No top tracks data available for this period" />
          )}
      </div>

      {/* History Timeline */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Timeline</h2>
        {isHistoryError ? (
          <InlineErrorState
            title="Failed to Load History"
            message={historyError instanceof Error ? historyError.message : 'Unable to fetch listening history. Please try again.'}
            onRetry={refetchHistory}
          />
        ) : isHistoryLoading ? (
          <div className="bg-obsidian-surface border border-obsidian-border p-6 animate-pulse">
            <div className="space-y-4">
              {[...Array(10)].map((_, i) => (
                <div key={i} className="h-16"></div>
              ))}
            </div>
          </div>
        ) : historyEntries.length > 0 ? (
          <>
            <div className="bg-obsidian-surface border border-obsidian-border p-6">
              <div className="space-y-4">
                {historyEntries.map((entry: HistoryEntry) => (
                  <div
                    key={entry.id}
                    className="flex justify-between items-start py-3 border-b border-obsidian-border/50 last:border-0"
                  >
                    <div className="flex-1 min-w-0 mr-4">
                      <div className="text-white/90 font-medium truncate">
                        {entry.track_title || 'Unknown Track'}
                      </div>
                      <div className="text-white/60 text-sm truncate">
                        {entry.track_artist || 'Unknown Artist'}
                      </div>
                      <div className="text-white/50 text-xs mt-1 flex items-center gap-2">
                        <span>{entry.source_type}</span>
                        <span>•</span>
                        <span>{formatDuration(entry.duration_ms)}</span>
                        {entry.end_reason && (
                          <>
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              {getEndReasonIcon(entry.end_reason)}
                              <span className="capitalize">{entry.end_reason}</span>
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-white/60 text-sm whitespace-nowrap">
                        {new Date(entry.started_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Load More Button */}
            {hasNextPage && (
              <div className="mt-4 text-center">
                <button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="bg-obsidian-border hover:bg-white/5 text-white px-6 py-3 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isFetchingNextPage ? 'Loading...' : 'Load More'}
                </button>
              </div>
            )}
          </>
        ) : (
          <EmptyState message="No listening history found for this period" />
        )}
      </div>
    </div>
  );
}
