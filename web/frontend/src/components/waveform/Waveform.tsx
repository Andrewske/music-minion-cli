import { useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, MouseEvent, RefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getWaveformData, waveformQueryKey } from '../../api/tracks';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';
import { barCountFor, downsamplePeaks, drawBars } from './waveformBars';

/** Track the canvas's CSS width so bars stay crisp and fill it at a fixed pitch. */
function useCanvasWidth(canvasRef: RefObject<HTMLCanvasElement>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [canvasRef]);
  return width;
}

interface WaveformProps {
  localTrackId: number | null;
  durationMs: number;
  /**
   * Called when the waveform is clicked while this row is NOT the playing
   * track. Omit it for rows that can't be played; with it, the waveform is
   * clickable even before the row has a library track.
   */
  onActivate?: () => void;
  /** CSS height in px (default 40 for dense feed rows). */
  height?: number;
}

/**
 * The app's one waveform: feed rows, Stories, and every WaveformPlayer.
 * Fetches peaks once per track (staleTime Infinity — backend disk-caches
 * after the first fetch) and draws downsampled bars on a canvas. When this
 * is the playing track, an accent progress fill ticks along. Cheap enough to
 * render one per row of an infinite list.
 */
export function Waveform({
  localTrackId,
  durationMs,
  onActivate,
  height = 40,
}: WaveformProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cssWidth = useCanvasWidth(canvasRef);
  const [progress, setProgress] = useState(0);

  const isCurrent = usePlayerStore(
    (s) => s.currentTrack !== null && s.currentTrack.id === localTrackId
  );
  const seek = usePlayerStore((s) => s.seek);

  // Activation can materialize a track first, so it only needs a handler;
  // seeking needs the loaded library track.
  const playable = localTrackId !== null || onActivate !== undefined;

  const handleClick = (e: MouseEvent<HTMLCanvasElement>): void => {
    if (!playable) return;
    if (isCurrent && durationMs > 0) {
      const rect = e.currentTarget.getBoundingClientRect();
      const fraction = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      setProgress(fraction); // instant visual feedback; tick interval corrects drift
      void seek(fraction * durationMs);
    } else {
      onActivate?.();
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLCanvasElement>): void => {
    if (!playable) return;
    if (isCurrent && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
      event.preventDefault();
      const delta = event.key === 'ArrowRight' ? 5_000 : -5_000;
      const nextPosition = Math.min(
        durationMs,
        Math.max(0, getCurrentPosition(usePlayerStore.getState()) + delta)
      );
      setProgress(durationMs > 0 ? nextPosition / durationMs : 0);
      void seek(nextPosition);
      return;
    }
    if (!isCurrent && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      onActivate?.();
    }
  };

  const { data } = useQuery({
    queryKey: waveformQueryKey(localTrackId),
    queryFn: () => getWaveformData(localTrackId as number),
    enabled: localTrackId !== null,
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    retry: 1,
  });

  useEffect(() => {
    if (!isCurrent) return;
    const tick = (): void => {
      if (durationMs > 0) {
        const pos = getCurrentPosition(usePlayerStore.getState());
        setProgress(Math.min(1, pos / durationMs));
      }
    };
    tick();
    const interval = setInterval(tick, 500);
    return () => clearInterval(interval);
  }, [isCurrent, durationMs]);

  const bars = useMemo(
    () => (data && cssWidth > 0 ? downsamplePeaks(data.peaks, barCountFor(cssWidth)) : []),
    [data, cssWidth]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || bars.length === 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(height * dpr);
    drawBars(canvas, bars, isCurrent ? progress : 0);
  }, [bars, cssWidth, height, isCurrent, progress]);

  return (
    <canvas
      ref={canvasRef}
      style={{ height }}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={playable ? 'button' : undefined}
      tabIndex={playable ? 0 : undefined}
      aria-label={playable ? (isCurrent ? 'Seek with left and right arrow keys' : 'Play from here') : undefined}
      aria-hidden={playable ? undefined : 'true'}
      className={`block w-full ${playable ? 'cursor-pointer' : ''}`}
    />
  );
}
