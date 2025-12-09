import type { TrackInfo } from '../types';

interface TrackCardProps {
  track: TrackInfo;
  isPlaying: boolean;
  className?: string;
}

export function TrackCard({ track, isPlaying, className = '' }: TrackCardProps) {
  const renderRatingBadge = (rating: number, wins: number, losses: number, comparisonCount: number) => {
    const isBootstrap = comparisonCount < 10;
    
    return (
      <div className={`
        flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border backdrop-blur-sm shadow-sm
        transition-colors duration-300
        ${isBootstrap 
          ? 'bg-slate-900/50 border-slate-800 text-slate-400' 
          : 'bg-amber-950/20 border-amber-500/20 text-amber-400'}
      `}>
        {/* Icon & Score */}
        <div className="flex items-center gap-1.5">
          <span className={isBootstrap ? 'opacity-70' : ''}>
            {isBootstrap ? '🎵' : '⭐'}
          </span>
          <span className="font-bold tabular-nums tracking-tight">
            {rating.toFixed(0)}
          </span>
        </div>

        {/* Divider */}
        <div className={`w-px h-3 ${isBootstrap ? 'bg-slate-700' : 'bg-amber-500/20'}`} />

        {/* Win/Loss Record */}
        <div className="flex items-center gap-1 text-xs font-medium tabular-nums">
           <span className="text-emerald-500">{wins}</span>
           <span className={`${isBootstrap ? 'text-slate-600' : 'text-amber-500/40'}`}>/</span>
           <span className="text-rose-500">{losses}</span>
        </div>
      </div>
    );
  };

  return (
    <div
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
          {renderRatingBadge(track.rating, track.wins, track.losses, track.comparison_count)}
        </div>
      </div>
    </div>
  );
}
