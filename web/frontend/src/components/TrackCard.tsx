import { TrackInfo } from '../types';

interface TrackCardProps {
  track: TrackInfo;
  isPlaying: boolean;
  onTap: () => void;
  className?: string;
}

export function TrackCard({ track, isPlaying, onTap, className = '' }: TrackCardProps) {
  const formatRating = (rating: number, comparisonCount: number) => {
    if (comparisonCount >= 10) {
      return (
        <span className="flex items-center gap-1 text-yellow-400">
          ⭐ {rating.toFixed(0)}
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-amber-500/80">
        ⚠️ {comparisonCount}
      </span>
    );
  };

  return (
    <div
      onClick={onTap}
      className={`
        relative overflow-hidden rounded-2xl
        bg-slate-900 border border-slate-800
        transition-all duration-300
        hover:border-slate-700 hover:bg-slate-800/80
        active:scale-[0.98]
        cursor-pointer
        group
        ${isPlaying ? 'ring-2 ring-emerald-500/50 shadow-lg shadow-emerald-900/20' : 'shadow-md shadow-black/40'}
        ${className}
      `}
    >
      {/* Background Glow Effect for playing state */}
      {isPlaying && (
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/5 to-transparent pointer-events-none" />
      )}

      <div className="p-6 flex flex-col items-center justify-center text-center h-full relative z-10">
        
        {/* Play Icon / Indicator */}
        <div className={`
          mb-4 w-12 h-12 rounded-full flex items-center justify-center
          transition-colors duration-300
          ${isPlaying ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-500 group-hover:bg-slate-700 group-hover:text-slate-300'}
        `}>
          {isPlaying ? (
            <div className="flex gap-1 h-4 items-end">
              <div className="w-1 bg-current animate-[bounce_1s_infinite] rounded-full" />
              <div className="w-1 bg-current animate-[bounce_1.2s_infinite] rounded-full" style={{ animationDelay: '0.1s' }} />
              <div className="w-1 bg-current animate-[bounce_0.8s_infinite] rounded-full" style={{ animationDelay: '0.2s' }} />
            </div>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 ml-0.5">
              <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
            </svg>
          )}
        </div>

        {/* Title & Artist */}
        <h3 className="font-bold text-xl text-slate-100 leading-tight mb-2 line-clamp-2">
          {track.title}
        </h3>
        <p className="text-lg text-emerald-400 font-medium mb-4 line-clamp-1">
          {track.artist}
        </p>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-slate-400 mb-4">
          {track.year && <span>{track.year}</span>}
          {track.bpm && <span>{track.bpm} BPM</span>}
          {track.genre && <span className="col-span-2">{track.genre}</span>}
        </div>

        {/* Stats / Badges */}
        <div className="mt-auto pt-4 border-t border-slate-800 w-full flex justify-center">
          <div className="bg-slate-950/50 px-3 py-1 rounded-full text-sm font-medium border border-slate-800">
            {formatRating(track.rating, track.comparison_count)}
          </div>
        </div>
      </div>
    </div>
  );
}
