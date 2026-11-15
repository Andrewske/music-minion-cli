/**
 * Up-next list for the full player: the tracks after the current queue
 * position, capped so the sheet stays short.
 */
import type { Track } from '@music-minion/shared';

export const UP_NEXT_LIMIT = 10;

export interface UpNextRow {
  track: Track;
  /** 1-based position in the whole queue. */
  position: number;
}

export interface UpNext {
  rows: UpNextRow[];
  /** Tracks after the shown rows. */
  remaining: number;
}

/**
 * Slice of the queue from `upcomingStart` (the shared store's
 * upcomingStart(): the index after the current track, or the cursor itself
 * when the current track was displaced from the queue), at most `limit` rows.
 */
export function upNextSlice(queue: readonly Track[], upcomingStart: number, limit: number = UP_NEXT_LIMIT): UpNext {
  const start = Math.max(0, upcomingStart);
  const after = queue.slice(start);
  const rows = after.slice(0, Math.max(0, limit)).map((track, i) => ({ track, position: start + i + 1 }));
  return { rows, remaining: after.length - rows.length };
}

/** "3 / 40 in queue". Maestro flows parse this exact shape. */
export function queueInfoLabel(queueIndex: number, queueLength: number): string {
  return `${queueIndex + 1} / ${queueLength} in queue`;
}
