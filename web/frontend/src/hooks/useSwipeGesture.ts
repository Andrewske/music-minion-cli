 import { useDrag } from '@use-gesture/react';
 import type { FullGestureState } from '@use-gesture/react';
 import { useSpring } from '@react-spring/web';
 import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

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

  // Fix stale closure: Store current callbacks in ref so useDrag always uses latest values
  const callbacksRef = useRef({ onSwipeRight, onSwipeLeft });
  useEffect(() => {
    callbacksRef.current = { onSwipeRight, onSwipeLeft };
  }, [onSwipeRight, onSwipeLeft]);

  // Track the last movement value during drag to check on release
  const lastMovementRef = useRef({ mx: 0, vx: 0 });

  const [{ x, rotate }, api] = useSpring(() => ({
    x: 0,
    rotate: 0,
    config: { tension: 200, friction: 20 },
  }));

  // Reset spring state to ensure clean state between gesture instances
  useEffect(() => {
    api.set({ x: 0, rotate: 0 });
  }, [api]);

  // Stabilize handler identity to prevent useDrag from recreating bindings on every render
  const handler = useCallback(
    (state: FullGestureState<'drag'>) => {
      const { active, movement: [mx], velocity: [vx] } = state;
      setIsDragging(active);

      if (active) {
        // During drag: store movement values for checking on release
        lastMovementRef.current = { mx, vx };

        // Update drag position immediately (no animation during drag)
        const rotate = mx * ROTATION_FACTOR;
        api.set({ x: mx, rotate });
      } else {
        // On release: use stored values (mx/vx from params are often 0 due to bounds)
        const { mx: lastMx, vx: lastVx } = lastMovementRef.current;

        // Accept swipes that meet EITHER distance OR velocity threshold
        // This supports both mobile (fast flicks) and desktop (slow drags)
        if (Math.abs(lastMx) > SWIPE_DISTANCE_THRESHOLD || Math.abs(lastVx) > SWIPE_VELOCITY_THRESHOLD) {
          if (lastMx > 0) {
            callbacksRef.current.onSwipeRight();
          } else {
            callbacksRef.current.onSwipeLeft();
          }
        }

        // Reset position immediately
        api.start({ x: 0, rotate: 0, immediate: true });

        // Reset tracking
        lastMovementRef.current = { mx: 0, vx: 0 };
      }
    },
    [api] // Only api dependency - stable from useSpring
  );

  // Stabilize config object to prevent useDrag from seeing it as changed
  const config = useMemo(
    () => ({
      axis: 'x' as const,
      bounds: { left: -150, right: 150 },
      rubberband: 0.3,
      filterTaps: false,
    }),
    [] // Config is static constants
  );

  const bind = useDrag(handler, config);

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