import type { LeaderboardEntry } from '../types';

interface LeaderboardProps {
  entries: LeaderboardEntry[];
  className?: string;
}

export function Leaderboard({ entries, className = '' }: LeaderboardProps) {
  if (!entries.length) {
    return (
      <div className={`text-center py-8 text-slate-500 ${className}`}>
        No leaderboard data available
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <h3 className="text-lg font-semibold text-slate-200">Top Rated Tracks</h3>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800">
              <th className="text-left py-3 px-2 text-slate-400 font-medium">#</th>
              <th className="text-left py-3 px-2 text-slate-400 font-medium">Track</th>
              <th className="text-right py-3 px-2 text-slate-400 font-medium">Rating</th>
              <th className="text-right py-3 px-2 text-slate-400 font-medium">W/L</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, index) => (
              <tr
                key={entry.track_id}
                className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
              >
                {/* Rank */}
                <td className="py-3 px-2 text-slate-300 font-mono text-center w-12">
                  {index + 1}
                </td>

                {/* Title/Artist */}
                <td className="py-3 px-2 min-w-0">
                  <div className="flex flex-col">
                    <span className="text-slate-200 font-medium truncate">
                      {entry.title}
                    </span>
                    <span className="text-slate-500 text-xs truncate">
                      {entry.artist}
                    </span>
                  </div>
                </td>

                {/* Rating */}
                <td className="py-3 px-2 text-right">
                  <span className="text-slate-200 font-mono font-bold tabular-nums">
                    {entry.rating.toFixed(0)}
                  </span>
                </td>

                {/* Wins/Losses */}
                <td className="py-3 px-2 text-right">
                  <div className="flex items-center justify-end gap-1 text-xs font-mono">
                    <span className="text-emerald-400 tabular-nums">
                      {entry.wins}
                    </span>
                    <span className="text-slate-600">/</span>
                    <span className="text-red-400 tabular-nums">
                      {entry.losses}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}