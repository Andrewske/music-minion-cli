import { animated } from '@react-spring/web';
import { useSwipeGesture } from '../hooks/useSwipeGesture';
import { TrackCard } from './TrackCard';
import type { TrackInfo } from '../types';

interface SwipeableTrackProps {
  track: TrackInfo;
  isPlaying: boolean;
  onSwipeRight: () => void; // Mark as winner
  onSwipeLeft: () => void;  // Archive track
  onTap: () => void;        // Play track
  onArchive?: () => void;
  onWinner?: () => void;
  isLoading?: boolean;
}

export function SwipeableTrack({
  track,
  isPlaying,
  onSwipeRight,
  onSwipeLeft,
  onTap,
  onArchive,
  onWinner,
  isLoading
}: SwipeableTrackProps) {
  const { bind, style, isDragging } = useSwipeGesture({
    onSwipeRight,
    onSwipeLeft,
  });

  return (
    <div className="relative w-full">
      {/* Swipe indicators (Behind the card) */}
      <div className="absolute inset-0 flex items-center justify-between px-8 pointer-events-none">
        {/* Archive Indicator (Left) */}
        <div className={`flex flex-col items-center justify-center transition-all duration-200 ${isDragging ? 'opacity-100 scale-100' : 'opacity-0 scale-75'}`}>
          <div className="w-16 h-16 rounded-full bg-rose-500/20 flex items-center justify-center border-2 border-rose-500 shadow-[0_0_20px_rgba(244,63,94,0.3)]">
            <span className="text-3xl">🗂️</span>
          </div>
          <span className="text-rose-500 font-bold mt-2 uppercase tracking-wider text-sm">Archive</span>
        </div>

        {/* Winner Indicator (Right) */}
        <div className={`flex flex-col items-center justify-center transition-all duration-200 ${isDragging ? 'opacity-100 scale-100' : 'opacity-0 scale-75'}`}>
          <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center border-2 border-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.3)]">
            <span className="text-3xl">🏆</span>
          </div>
          <span className="text-emerald-500 font-bold mt-2 uppercase tracking-wider text-sm">Winner</span>
        </div>
      </div>

      {/* Swipeable card */}
      <animated.div
        {...bind()}
        style={{
          x: style.x,
          rotate: style.rotate,
          touchAction: style.touchAction,
        }}
        className={`relative z-10 transition-shadow duration-200 ${isDragging ? 'shadow-2xl shadow-black/50 cursor-grabbing' : 'cursor-grab'}`}
      >
        <TrackCard
          track={track}
          isPlaying={isPlaying}
          onArchive={onArchive}
          onWinner={onWinner}
          onClick={onTap}
          isLoading={isLoading}
        />
      </animated.div>
    </div>
  );
}
