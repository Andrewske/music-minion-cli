/**
 * Pure listen-time accounting for feed verdicts.
 *
 * The player store is sampled about once a second. Played time is wall-clock
 * time between two consecutive playing samples of the same track, so seeking
 * ahead never counts as listening. Gaps longer than MAX_SAMPLE_GAP_MS (a
 * sleeping tab) are capped instead of trusted.
 */

export interface ListenSample {
  trackId: number | null;
  isPlaying: boolean;
  positionMs: number;
  at: number;
}

export interface ListenTally {
  listenedMs: number;
  maxPositionMs: number;
}

export interface ListenState {
  tallies: Readonly<Record<number, ListenTally>>;
  last: ListenSample | null;
}

export interface ListenStats {
  listenSeconds: number;
  maxPositionMs: number;
}

export const MAX_SAMPLE_GAP_MS = 5_000;
export const INITIAL_LISTEN_STATE: ListenState = { tallies: {}, last: null };
const EMPTY_TALLY: ListenTally = { listenedMs: 0, maxPositionMs: 0 };

function playedSince(last: ListenSample | null, sample: ListenSample): number {
  const continuous =
    last !== null && last.trackId === sample.trackId && last.isPlaying && sample.isPlaying;
  if (!continuous) return 0;
  return Math.min(Math.max(0, sample.at - last.at), MAX_SAMPLE_GAP_MS);
}

export function recordListenSample(state: ListenState, sample: ListenSample): ListenState {
  if (sample.trackId === null) return { ...state, last: sample };
  const prior = state.tallies[sample.trackId] ?? EMPTY_TALLY;
  const tally: ListenTally = {
    listenedMs: prior.listenedMs + playedSince(state.last, sample),
    maxPositionMs: sample.isPlaying
      ? Math.max(prior.maxPositionMs, Math.round(sample.positionMs))
      : prior.maxPositionMs,
  };
  return { tallies: { ...state.tallies, [sample.trackId]: tally }, last: sample };
}

/** Stats to send with a verdict; tracks never played report zero. */
export function listenStatsFor(state: ListenState, trackId: number | null): ListenStats {
  const tally = trackId === null ? EMPTY_TALLY : state.tallies[trackId] ?? EMPTY_TALLY;
  return {
    listenSeconds: Math.round(tally.listenedMs / 100) / 10,
    maxPositionMs: tally.maxPositionMs,
  };
}

export function formatListenTime(seconds: number | null): string {
  if (seconds === null) return '—';
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
