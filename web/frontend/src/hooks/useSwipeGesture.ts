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
        onTap();
        return;
      }

      if (!active) {
        // Determine if this was a swipe
        const triggerDistance = 100;
        const triggerVelocity = 0.5;

        if (Math.abs(mx) > triggerDistance && Math.abs(vx) > triggerVelocity) {
          if (xDir > 0) {
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