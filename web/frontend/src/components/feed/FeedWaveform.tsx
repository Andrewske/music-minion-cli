import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, MouseEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getWaveformData } from '../../api/tracks';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';

const BAR_COUNT = 120;
const BAR_COLOR = 'rgba(255, 255, 255, 0.25)';
const PROGRESS_COLOR = '#1DB954';

/** Downsample interleaved min/max peaks to BAR_COUNT max-abs bars in [0, 1]. */
function downsamplePeaks(peaks: number[]): number[] {
  if (peaks.length === 0) return [];
  const bars: number[] = [];
  const chunk = Math.max(1, Math.floor(peaks.length / BAR_COUNT));
  let maxAbs = 0;
  for (let i = 0; i < BAR_COUNT; i++) {
    let peak = 0;
    const start = i * chunk;
    for (let j = start; j < Math.min(start + chunk, peaks.length); j++) {
      peak = Math.max(peak, Math.abs(peaks[j]));
    }
    bars.push(peak);
    maxAbs = Math.max(maxAbs, peak);
  }
  return maxAbs > 0 ? bars.map((b) => b / maxAbs) : bars;
}

function drawBars(
  canvas: HTMLCanvasElement,
  bars: number[],
  progress: number
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  const barWidth = width / bars.length;
  const progressX = progress * width;
  bars.forEach((value, i) => {
    const barHeight = Math.max(2, value * height);
    const x = i * barWidth;
    ctx.fillStyle = x < progressX ? PROGRESS_COLOR : BAR_COLOR;
    ctx.fillRect(x, (height - barHeight) / 2, Math.max(1, barWidth - 1), barHeight);
  });
}

interface FeedWaveformProps {
  localTrackId: number | null;
  durationMs: number;
  /** Called when the waveform is clicked while this row is NOT the playing track. */
  onActivate?: () => void;
}

/**
 * Static-canvas waveform for feed rows. Fetches peaks once per track
 * (staleTime Infinity — backend disk-caches after the first SC fetch) and
 * draws downsampled bars. When this row is the playing track, an accent
 * progress fill ticks along. NOT wavesurfer — one instance per row of that
 * would sink an infinite list.
 */
export function FeedWaveform({
  localTrackId,
  durationMs,
  onActivate,
}: FeedWaveformProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const barsRef = useRef<number[]>([]);
  const [progress, setProgress] = useState(0);

  const isCurrent = usePlayerStore(
    (s) => s.currentTrack !== null && s.currentTrack.id === localTrackId
  );
  const seek = usePlayerStore((s) => s.seek);

  const playable = localTrackId !== null;

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
    queryKey: ['feed-waveform', localTrackId],
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

  useEffect(() => {
    if (!data || !canvasRef.current) return;
    barsRef.current = downsamplePeaks(data.peaks);
    drawBars(canvasRef.current, barsRef.current, isCurrent ? progress : 0);
  }, [data, isCurrent, progress]);

  return (
    <canvas
      ref={canvasRef}
      width={480}
      height={40}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={playable ? 'button' : undefined}
      tabIndex={playable ? 0 : undefined}
      aria-label={playable ? (isCurrent ? 'Seek with left and right arrow keys' : 'Play from here') : undefined}
      aria-hidden={playable ? undefined : 'true'}
      className={`w-full h-10 ${playable ? 'cursor-pointer' : ''}`}
    />
  );
}
