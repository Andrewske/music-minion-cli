const BAR_WIDTH = 2;
const BAR_GAP = 1;
const MIN_BAR = 0.08;
// >1 pushes quiet passages down so intros and breakdowns read against the drop.
const CONTRAST_CURVE = 1.5;
// Share of the height used by the main bars; the rest is a faded reflection.
const TOP_SHARE = 0.7;
const BAR_COLOR = 'rgba(255, 255, 255, 0.35)';
const PROGRESS_COLOR = '#1DB954';
const REFLECTION_ALPHA = 0.35;

/** Number of bars that fit a CSS width at the bar+gap pitch. */
export function barCountFor(cssWidth: number): number {
  return Math.max(1, Math.floor(cssWidth / (BAR_WIDTH + BAR_GAP)));
}

/** Average |peak| per bar, so a single transient doesn't flatten its whole span. */
function averageBars(peaks: number[], count: number): number[] {
  const step = peaks.length / count;
  return Array.from({ length: count }, (_, i) => {
    const start = Math.floor(i * step);
    const end = Math.max(start + 1, Math.floor((i + 1) * step));
    let sum = 0;
    for (let j = start; j < end; j++) sum += Math.abs(peaks[j] ?? 0);
    return sum / (end - start);
  });
}

/**
 * Downsample interleaved min/max peaks to `count` bars in [MIN_BAR, 1].
 * Contrast-stretches between the quietest 5% and the loudest bar: mastered
 * tracks sit near full scale, so plain max-normalising draws a flat block.
 */
export function downsamplePeaks(peaks: number[], count: number): number[] {
  if (peaks.length === 0) return [];
  const bars = averageBars(peaks, count);
  const sorted = [...bars].sort((a, b) => a - b);
  const floor = sorted[Math.floor(sorted.length * 0.05)] * 0.8;
  const range = sorted[sorted.length - 1] - floor;
  if (range <= 0) return bars.map(() => 1);
  return bars.map(
    (b) => MIN_BAR + (1 - MIN_BAR) * Math.max(0, (b - floor) / range) ** CONTRAST_CURVE
  );
}

export function drawBars(
  canvas: HTMLCanvasElement,
  bars: number[],
  progress: number
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  const pitch = width / bars.length;
  const barWidth = Math.max(1, pitch * (BAR_WIDTH / (BAR_WIDTH + BAR_GAP)));
  const axis = Math.round(height * TOP_SHARE);
  const progressX = progress * width;
  bars.forEach((value, i) => {
    const x = i * pitch;
    ctx.fillStyle = x < progressX ? PROGRESS_COLOR : BAR_COLOR;
    const top = value * axis;
    ctx.fillRect(x, axis - top, barWidth, top);
    ctx.globalAlpha = REFLECTION_ALPHA;
    ctx.fillRect(x, axis + 1, barWidth, value * (height - axis - 1));
    ctx.globalAlpha = 1;
  });
}
