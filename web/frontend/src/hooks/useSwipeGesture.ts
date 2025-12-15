 import { useDrag } from '@use-gesture/react';
 import { useSpring } from '@react-spring/web';
 import { useState, useEffect } from 'react';

interface UseSwipeGestureOptions {
  onSwipeRight: () => void;
  onSwipeLeft: () => void;
}

// Swipe gesture thresholds
const SWIPE_DISTANCE_THRESHOLD = 60; // px - minimum drag distance to register swipe
const SWIPE_VELOCITY_THRESHOLD = 2.0; // px/ms - minimum velocity for quick flicks
const ROTATION_FACTOR = 0.1; // degrees per pixel - visual rotation during drag

export function useSwipeGesture({ onSwipeRight, onSwipeLeft }: UseSwipeGestureOptions) {
  const [isDragging, setIsDragging] = useState(false);

  const [{ x, rotate }, api] = useSpring(() => ({
    x: 0,
    rotate: 0,
    config: { tension: 200, friction: 20 },
  }));

  useEffect(() => {
    api.set({ x: 0, rotate: 0 });
  }, [api]);

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

        // Reset position immediately
        api.start({ x: 0, rotate: 0, immediate: true });
      } else {
        // Update drag position immediately (no animation during drag)
        const rotate = mx * ROTATION_FACTOR;
        api.set({ x: mx, rotate });
      }
    },
    {
      axis: 'x',
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