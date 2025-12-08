import type { TrackInfo } from '../types';

interface TrackCardProps {
  track: TrackInfo;
  isPlaying: boolean;
  onTap: () => void;
}

export function TrackCard({ track, isPlaying, onTap }: TrackCardProps) {
  const formatRating = (rating: number, comparisonCount: number) => {
    if (comparisonCount >= 10) {
      return `⭐ ${rating.toFixed(0)}`;
    }
    return `⚠️ ${comparisonCount}`;
  };

  return (
    <div
      className="bg-white rounded-lg shadow-md p-4 mx-2 min-h-[120px] cursor-pointer active:bg-gray-50 touch-manipulation"
      onClick={onTap}
    >
      {/* Playing indicator */}
      {isPlaying && (
        <div className="flex justify-center mb-2">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
        </div>
      )}

      {/* Track info */}
      <div className="text-center">
        <h3 className="font-bold text-lg text-gray-900 leading-tight">
          {track.artist} - {track.title}
        </h3>

        <div className="text-sm text-gray-600 mt-1">
          {track.album && <div>{track.album}</div>}
          <div className="flex justify-center items-center gap-2 mt-1">
            {track.year && <span>{track.year}</span>}
            {track.bpm && <span>{track.bpm} BPM</span>}
            {track.genre && <span>{track.genre}</span>}
          </div>
        </div>

        {/* Rating indicator */}
        <div className="mt-2 text-sm font-medium">
          {formatRating(track.rating, track.comparison_count)}
        </div>
      </div>
    </div>
  );
}