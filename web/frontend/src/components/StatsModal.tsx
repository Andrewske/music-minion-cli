import { useEffect } from 'react';
import { usePlaylistStats } from '../hooks/usePlaylistStats';
import { usePlaylistTracks } from '../hooks/usePlaylistTracks';
import { StatCard } from './StatCard';
import { PlaylistTracksTable } from './PlaylistTracksTable';
import { ErrorState } from './ErrorState';

interface StatsModalProps {
  isOpen: boolean;
  onClose: () => void;
  playlistId: number;
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

export function StatsModal({ isOpen, onClose, playlistId }: StatsModalProps) {
  const { data: playlistStats, isLoading, isError, refetch } = usePlaylistStats(playlistId);
  const { data: playlistTracks, isLoading: isPlaylistTracksLoading, isError: isPlaylistTracksError } = usePlaylistTracks(playlistId);

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
          type="button"
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
          ) : isLoading || !playlistStats ? (
            <StatsSkeleton />
          ) : (
            <div className="p-6">
              {/* Header */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-slate-100 mb-2">
                  {playlistStats.playlist_name} Statistics
                </h2>
                <p className="text-slate-400">
                  Track your playlist curation progress
                </p>
              </div>

              {/* Stat Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                <StatCard
                  icon="🎵"
                  value={playlistStats.basic.total_tracks}
                  label="Total Tracks"
                  subtitle="In this playlist"
                />
                <StatCard
                  icon="📊"
                  value={`${playlistStats.elo.coverage_percentage.toFixed(1)}%`}
                  label="ELO Coverage"
                  subtitle={`${playlistStats.elo.rated_tracks} tracks rated`}
                />
                <StatCard
                  icon="⭐"
                  value={playlistStats.elo.avg_playlist_rating.toFixed(1)}
                  label="Avg Rating"
                  subtitle="Playlist ELO score"
                />
                <StatCard
                  icon="✅"
                  value={`${playlistStats.quality.completeness_score.toFixed(1)}%`}
                  label="Completeness"
                  subtitle="Metadata quality"
                />
                <StatCard
                  icon="⚖️"
                  value={playlistStats.elo.total_playlist_comparisons}
                  label="Comparisons"
                  subtitle="Within playlist"
                />
                <StatCard
                  icon="🎯"
                  value={playlistStats.elo.avg_playlist_comparisons.toFixed(1)}
                  label="Avg Comparisons"
                  subtitle="Per track"
                />
                <StatCard
                  icon="📈"
                  value={playlistStats.avg_comparisons_per_day.toFixed(1)}
                  label="Daily Pace"
                  subtitle="Comparisons per day"
                />
              </div>

              {/* Charts Section */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold text-slate-200 mb-4">Top Genres</h3>
                    <div className="space-y-2">
                      {playlistStats.top_genres.slice(0, 10).map((genre, index) => {
                        const isTopGenre = index < 3;
                        return (
                          <div key={genre.genre} className="flex items-center gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-slate-300 truncate">
                                  {genre.genre}
                                </span>
                                <div className="flex items-center gap-2 text-xs text-slate-500">
                                  <span>{genre.count} tracks</span>
                                  <span>•</span>
                                  <span>{genre.percentage.toFixed(1)}%</span>
                                </div>
                              </div>
                              <div className="relative h-6 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                  className={`
                                    absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out
                                    ${isTopGenre
                                      ? 'bg-gradient-to-r from-amber-500 to-amber-400'
                                      : 'bg-gradient-to-r from-slate-600 to-slate-500'
                                    }
                                  `}
                                  style={{ width: `${genre.percentage}%` }}
                                />
                                <div className="absolute inset-0 flex items-center justify-end px-3">
                                  <span className={`
                                    text-sm font-bold tabular-nums
                                    ${genre.percentage > 30 ? 'text-slate-900' : 'text-slate-200'}
                                  `}>
                                    {genre.percentage.toFixed(0)}%
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                      {playlistStats.top_genres.length === 0 && (
                        <div className="text-center py-8 text-slate-500">
                          No genre data available
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold text-slate-200">Top Artists</h3>
                    <div className="space-y-3">
                      {playlistStats.top_artists.slice(0, 10).map((artist, index) => (
                        <div key={artist.artist} className="flex justify-between items-center py-2 border-b border-slate-800/50">
                          <div className="flex items-center gap-3">
                            <span className="text-slate-400 text-sm w-6">#{index + 1}</span>
                            <div>
                              <div className="text-slate-200 font-medium">{artist.artist}</div>
                            </div>
                          </div>
                          <span className="text-slate-400 text-sm">{artist.track_count} tracks</span>
                        </div>
                      ))}
                      {playlistStats.top_artists.length === 0 && (
                        <div className="text-center py-8 text-slate-500">
                          No artist data available
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Estimated Days Section */}
              {playlistStats.estimated_days_to_full_coverage && (
                <div className="mt-6 text-center">
                  <p className="text-slate-400">
                    Estimated {Math.round(playlistStats.estimated_days_to_full_coverage)} days to full coverage at current pace
                  </p>
                </div>
              )}

              {/* Playlist Tracks Table */}
              {playlistTracks && (
                <div className="mt-6">
                  {isPlaylistTracksLoading ? (
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 animate-pulse">
                      <div className="h-6 bg-slate-800 rounded w-48 mb-4"></div>
                      <div className="space-y-3">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <div key={i} className="h-12 bg-slate-800 rounded"></div>
                        ))}
                      </div>
                    </div>
                  ) : isPlaylistTracksError ? (
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                      <div className="text-center text-slate-500">
                        Failed to load track data
                      </div>
                    </div>
                  ) : (
                    <PlaylistTracksTable tracks={playlistTracks.tracks} />
                  )}
                </div>
              )}
             </div>
           )}
         </div>
       </div>
     </div>
   );
 }
