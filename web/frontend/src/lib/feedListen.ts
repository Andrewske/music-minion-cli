/**
 * Pure listen-time accounting for feed verdicts.
 *
 * Driven by the persistent player's real <audio> events, not the player
 * store: `progress` comes from `timeupdate`, `seek` from `seeking`/`seeked`.
 * Played time is the media position advanced between two progress events on
 * the same element and track, so buffering, stalls and blocked autoplay
 * (position never moves) count as nothing, and a seek never counts as
 * listening. Seek targets do count toward the furthest position reached.
 */

export type ListenEventKind = 'progress' | 'seek';

export interface ListenEvent {
  kind: ListenEventKind;
  /** Which audio element fired the event; each keeps its own cursor. */
  source: string;
  trackId: number;
  positionMs: number;
}

export interface ListenTally {
  listenedMs: number;
  maxPositionMs: number;
}

interface ListenCursor {
  trackId: number;
  positionMs: number;
}

export interface ListenState {
  tallies: Readonly<Record<number, ListenTally>>;
  cursors: Readonly<Record<string, ListenCursor>>;
}

export interface ListenStats {
  listenSeconds: number;
  maxPositionMs: number;
}

/** timeupdate fires every ~250ms; a larger jump without a seek event is not trusted. */
export const MAX_PROGRESS_STEP_MS = 5_000;
export const INITIAL_LISTEN_STATE: ListenState = { tallies: {}, cursors: {} };
const EMPTY_TALLY: ListenTally = { listenedMs: 0, maxPositionMs: 0 };

function playedSince(cursor: ListenCursor | undefined, event: ListenEvent): number {
  if (event.kind !== 'progress' || cursor?.trackId !== event.trackId) return 0;
  const advanced = event.positionMs - cursor.positionMs;
  return advanced > 0 && advanced <= MAX_PROGRESS_STEP_MS ? advanced : 0;
}

export function recordListenEvent(state: ListenState, event: ListenEvent): ListenState {
  const prior = state.tallies[event.trackId] ?? EMPTY_TALLY;
  const tally: ListenTally = {
    listenedMs: prior.listenedMs + playedSince(state.cursors[event.source], event),
    maxPositionMs: Math.max(prior.maxPositionMs, Math.round(event.positionMs)),
  };
  return {
    tallies: { ...state.tallies, [event.trackId]: tally },
    cursors: { ...state.cursors, [event.source]: { trackId: event.trackId, positionMs: event.positionMs } },
  };
}

function toStats(tally: ListenTally): ListenStats {
  return {
    listenSeconds: Math.round(tally.listenedMs / 100) / 10,
    maxPositionMs: tally.maxPositionMs,
  };
}

/** Stats to send with a verdict; tracks never played report zero. */
export function listenStatsFor(state: ListenState, trackId: number | null): ListenStats {
  return toStats(trackId === null ? EMPTY_TALLY : state.tallies[trackId] ?? EMPTY_TALLY);
}

/** Stats only when the track played this session, so re-rates can carry old ones forward. */
export function playedListenStatsFor(state: ListenState, trackId: number | null): ListenStats | undefined {
  const tally = trackId === null ? undefined : state.tallies[trackId];
  return tally && (tally.listenedMs > 0 || tally.maxPositionMs > 0) ? toStats(tally) : undefined;
}

export function formatListenTime(seconds: number | null): string {
  if (seconds === null) return '—';
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}
