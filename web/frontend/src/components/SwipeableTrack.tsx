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
}

export function SwipeableTrack({
  track,
  isPlaying,
  onSwipeRight,
  onSwipeLeft,
  onTap
}: SwipeableTrackProps) {
  const { bind, style, isDragging } = useSwipeGesture({
    onSwipeRight,
    onSwipeLeft,
    onTap,
  });

  return (
    <div className="relative">
      {/* Swipe indicators */}
      <div className="absolute inset-y-0 left-0 flex items-center justify-start pl-4 pointer-events-none">
        <div className={`text-2xl transition-opacity duration-200 ${isDragging ? 'opacity-100' : 'opacity-0'}`}>
          🗂️
        </div>
      </div>

      <div className="absolute inset-y-0 right-0 flex items-center justify-end pr-4 pointer-events-none">
        <div className={`text-2xl transition-opacity duration-200 ${isDragging ? 'opacity-100' : 'opacity-0'}`}>
          🏆
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
        className={`transition-shadow duration-200 ${isDragging ? 'shadow-2xl' : ''}`}
      >
        <TrackCard
          track={track}
          isPlaying={isPlaying}
          onTap={() => {}} // Handled by gesture hook
        />
      </animated.div>
    </div>
  );
}