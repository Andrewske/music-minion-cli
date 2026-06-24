import { animated } from '@react-spring/web';
import type { ComponentPropsWithoutRef } from 'react';
import { useSwipeGesture } from '../hooks/useSwipeGesture';
import { TrackCard } from './TrackCard';
import type { TrackInfo } from '../types';

// react-spring 9.7.5's `animated.div` props type is broken under React 19's
// @types/react: it derives from ComponentPropsWithRef, which no longer surfaces
// `children`/`className` for these primitives, producing a props type that
// rejects standard div attributes. The component accepts all div props plus
// the animated `style` from useSwipeGesture at runtime, so describe that shape
// explicitly here using the hook's own style type. Type-safe, no `any`.
type SwipeStyle = ReturnType<typeof useSwipeGesture>['style'];
type AnimatedDivProps = Omit<ComponentPropsWithoutRef<'div'>, 'style'> & {
  style?: SwipeStyle;
};
const AnimatedDiv = animated.div as (props: AnimatedDivProps) => JSX.Element;

interface SwipeableTrackProps {
  track: TrackInfo;
  isPlaying: boolean;
  onSwipeRight: () => void; // Mark as winner
  onSwipeLeft: () => void;  // Archive track
  onTap: () => void;        // Play track
  onArchive?: () => void;
  onWinner?: () => void;
  isLoading?: boolean;
  rankingMode?: 'global' | 'playlist';
  onTrackUpdate?: (track: TrackInfo) => void;
}

export function SwipeableTrack({
  track,
  isPlaying,
  onSwipeRight,
  onSwipeLeft,
  onTap,
  onArchive,
  onWinner,
  isLoading,
  rankingMode = 'global',
  onTrackUpdate
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
           <span className="text-rose-500 font-bold mt-2 uppercase tracking-wider text-sm">{rankingMode === 'playlist' ? 'Remove from playlist' : 'Archive'}</span>
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
      <AnimatedDiv
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
          rankingMode={rankingMode}
          onTrackUpdate={onTrackUpdate}
        />
      </AnimatedDiv>
    </div>
  );
}
