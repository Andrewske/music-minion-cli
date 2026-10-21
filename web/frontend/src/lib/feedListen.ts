/**
 * Pure listen-time accounting for feed verdicts.
 *
 * Driven by the persistent player's real <audio> events, not the player
 * store: `progress` comes from `timeupdate`, `seek` from `seeking`/`seeked`.
 * Played time is the media position advanced between two progress events on
 * the same element and track, so buffering, stalls and blocked autoplay
 * (position never moves) count as nothing, and a seek never counts as
 * listening. Seek targets do count toward the furthest position reached,
 * capped at the track's length once that is known: the media element's own
 * duration wins over the library's `duration`.
 */

export type ListenEventKind = 'progress' | 'seek' | 'duration';

export interface ListenEvent {
  kind: ListenEventKind;
  /** Which audio element fired the event; each keeps its own cursor. */
  source: string;
  trackId: number;
  positionMs: number;
  /** The audio element's duration, when it has loaded metadata. */
  mediaDurationMs?: number;
  /** The library's duration for the track, used until the media's is known. */
  trackDurationMs?: number;
}

export interface ListenTally {
  listenedMs: number;
  /** Furthest position requested or played, uncapped; stats cap it. */
  maxPositionMs: number;
  mediaDurationMs?: number;
  trackDurationMs?: number;
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

function knownDuration(ms: number | undefined): number | undefined {
  return ms !== undefined && Number.isFinite(ms) && ms > 0 ? Math.round(ms) : undefined;
}

function mergeTally(prior: ListenTally, event: ListenEvent, playedMs: number): ListenTally {
  return {
    listenedMs: prior.listenedMs + playedMs,
    maxPositionMs: Math.max(prior.maxPositionMs, Math.round(event.positionMs)),
    mediaDurationMs: knownDuration(event.mediaDurationMs) ?? prior.mediaDurationMs,
    trackDurationMs: knownDuration(event.trackDurationMs) ?? prior.trackDurationMs,
  };
}

export function recordListenEvent(state: ListenState, event: ListenEvent): ListenState {
  const prior = state.tallies[event.trackId] ?? EMPTY_TALLY;
  const tally = mergeTally(prior, event, playedSince(state.cursors[event.source], event));
  return {
    tallies: { ...state.tallies, [event.trackId]: tally },
    cursors: { ...state.cursors, [event.source]: { trackId: event.trackId, positionMs: event.positionMs } },
  };
}

function toStats(tally: ListenTally): ListenStats {
  // A seek past the end lands at the end, so the furthest point is the length.
  const lengthMs = tally.mediaDurationMs ?? tally.trackDurationMs ?? Infinity;
  return {
    listenSeconds: Math.round(tally.listenedMs / 100) / 10,
    maxPositionMs: Math.min(tally.maxPositionMs, lengthMs),
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
