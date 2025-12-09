import { useDrag } from '@use-gesture/react';
import { useSpring } from '@react-spring/web';
import { useState } from 'react';

interface UseSwipeGestureOptions {
  onSwipeRight: () => void;
  onSwipeLeft: () => void;
  onTap: () => void;
}

export function useSwipeGesture({ onSwipeRight, onSwipeLeft, onTap }: UseSwipeGestureOptions) {
  const [isDragging, setIsDragging] = useState(false);

  const [{ x, rotate }, api] = useSpring(() => ({
    x: 0,
    rotate: 0,
    config: { tension: 300, friction: 30 },
  }));

  const bind = useDrag(
    ({ active, movement: [mx], direction: [xDir], velocity: [vx], tap }) => {
      setIsDragging(active);

      if (tap) {
        console.log('Tap detected, calling onTap callback');
        onTap();
        return;
      }

      if (!active) {
        // Determine if this was a swipe
        const triggerDistance = 100;
        const triggerVelocity = 2.0;

        // Accept swipes that meet EITHER distance OR velocity threshold
        // This supports both mobile (fast flicks) and desktop (slow drags)
        if (Math.abs(mx) > triggerDistance || Math.abs(vx) > triggerVelocity) {
          console.log(`Swipe registered: distance=${Math.abs(mx).toFixed(0)}px, velocity=${Math.abs(vx).toFixed(2)}, xDir=${xDir.toFixed(2)}, mx=${mx.toFixed(2)}`);
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
        const rotate = mx * 0.1;
        api.start({ x: mx, rotate });
      }
    },
    {
      axis: 'x',
      bounds: { left: -200, right: 200 },
      rubberband: true,
      filterTaps: true,
      tapsThreshold: 10,
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