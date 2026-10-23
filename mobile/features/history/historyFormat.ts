/**
 * Pure display helpers for the History screen.
 */
import type { HistoryEntry } from '@music-minion/shared';

const MINUTE_MS = 60_000;

/** "just now" / "5m ago" / "3h ago" / "2d ago". Future times clamp to "just now". */
export const formatRelativeTime = (iso: string, now: number): string => {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '';
  const diffMins = Math.floor((now - then) / MINUTE_MS);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

export const formatDuration = (ms: number): string => {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
};

/**
 * Right-hand label for a history row. The newest open entry is the track
 * playing now; any other row under a second long was skipped.
 */
export const describeListen = (
  entry: Pick<HistoryEntry, 'ended_at' | 'duration_ms'>,
  isNewest: boolean
): string => {
  if (isNewest && entry.ended_at === null) return 'Now playing';
  if (entry.duration_ms < 1000) return 'skipped';
  return formatDuration(entry.duration_ms);
};
