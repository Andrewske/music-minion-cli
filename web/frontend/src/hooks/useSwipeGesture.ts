import { useDrag } from '@use-gesture/react';
import { useSpring } from '@react-spring/web';
import { useState } from 'react';

interface UseSwipeGestureOptions {
  onSwipeRight: () => void;
  onSwipeLeft: () => void;
}

// Swipe gesture thresholds
const SWIPE_DISTANCE_THRESHOLD = 100; // px - minimum drag distance to register swipe
const SWIPE_VELOCITY_THRESHOLD = 2.0; // px/ms - minimum velocity for quick flicks
const ROTATION_FACTOR = 0.1; // degrees per pixel - visual rotation during drag

export function useSwipeGesture({ onSwipeRight, onSwipeLeft }: UseSwipeGestureOptions) {
  const [isDragging, setIsDragging] = useState(false);

  const [{ x, rotate }, api] = useSpring(() => ({
    x: 0,
    rotate: 0,
    config: { tension: 300, friction: 30 },
  }));

  const bind = useDrag(
    ({ active, movement: [mx], velocity: [vx] }) => {
      setIsDragging(active);

      if (!active) {
        // Accept swipes that meet EITHER distance OR velocity threshold
        // This supports both mobile (fast flicks) and desktop (slow drags)
        if (Math.abs(mx) > SWIPE_DISTANCE_THRESHOLD || Math.abs(vx) > SWIPE_VELOCITY_THRESHOLD) {
          if (mx > 0) {
            onSwipeRight();
          } else {
            onSwipeLeft();
          }
        }

        // Reset position
        api.start({ x: 0, rotate: 0 });
      } else {
        // Update drag position with rotation
        const rotate = mx * ROTATION_FACTOR;
        api.start({ x: mx, rotate });
      }
    },
    {
      axis: 'x',
      bounds: { left: -200, right: 200 },
      rubberband: true,
      filterTaps: false, // Don't filter taps since we handle clicks in TrackCard
    }
  );

  return {
    bind,
    style: {
      x,
      rotate,
      touchAction: 'none' as const,
    },
    isDragging,
  };
}
