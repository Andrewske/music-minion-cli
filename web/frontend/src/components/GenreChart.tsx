import type { GenreStat } from '../types';

interface GenreChartProps {
  genres: GenreStat[];
  className?: string;
}

export function GenreChart({ genres, className = '' }: GenreChartProps) {
  if (!genres.length) {
    return (
      <div className={`text-center py-8 text-slate-500 ${className}`}>
        No genre data available
      </div>
    );
  }

  // Find the max rating for scaling the bars
  const maxRating = Math.max(...genres.map(g => g.average_rating));

  return (
    <div className={`space-y-3 ${className}`}>
      <h3 className="text-lg font-semibold text-slate-200 mb-4">Top Genres by Rating</h3>

      <div className="space-y-2">
        {genres.map((genre, index) => {
          const percentage = (genre.average_rating / maxRating) * 100;
          const isTopGenre = index < 3;

          return (
            <div key={genre.genre} className="flex items-center gap-3">
              {/* Genre name and stats */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-slate-300 truncate">
                    {genre.genre}
                  </span>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>{genre.track_count} tracks</span>
                    <span>•</span>
                    <span>{genre.total_comparisons} comparisons</span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="relative h-6 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`
                      absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out
                      ${isTopGenre
                        ? 'bg-gradient-to-r from-amber-500 to-amber-400'
                        : 'bg-gradient-to-r from-slate-600 to-slate-500'
                      }
                    `}
                    style={{ width: `${percentage}%` }}
                  />

                  {/* Rating value overlay */}
                  <div className="absolute inset-0 flex items-center justify-end px-3">
                    <span className={`
                      text-sm font-bold tabular-nums
                      ${percentage > 30 ? 'text-slate-900' : 'text-slate-200'}
                    `}>
                      {genre.average_rating.toFixed(0)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}