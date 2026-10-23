/**
 * Pure helpers for the mobile comparison session.
 * Kept out of the screen so they can be unit-tested without React Native.
 */
import type { ComparisonPair, PlayContext, Playlist } from '@music-minion/shared';

export type CardPlayState = 'playing' | 'paused' | 'idle';

/**
 * Playlists worth ranking: manual only (smart playlists like "All" are
 * query results, not curated sets) with at least two tracks to pair.
 */
export function selectComparablePlaylists(playlists: readonly Playlist[] | undefined): Playlist[] {
  return (playlists ?? []).filter((p) => p.type === 'manual' && p.track_count >= 2);
}

/** Session progress label: counts votes cast since the session started. */
export function formatSessionProgress(voteCount: number): string {
  if (voteCount <= 0) return 'No votes yet';
  return voteCount === 1 ? '1 vote this session' : `${voteCount} votes this session`;
}

/** Play context matching web ComparisonView: queue is just the current pair. */
export function buildComparisonContext(pair: ComparisonPair): PlayContext {
  return {
    type: 'comparison',
    track_ids: [pair.track_a.id, pair.track_b.id],
    shuffle: false,
  };
}

/** Which state a card should show given the global player's current track. */
export function getCardPlayState(
  trackId: number,
  currentTrackId: number | null | undefined,
  isPlaying: boolean,
): CardPlayState {
  if (currentTrackId !== trackId) return 'idle';
  return isPlaying ? 'playing' : 'paused';
}

/** Playback fraction in [0, 1]; 0 when duration is unknown. */
export function playbackFraction(positionMs: number, durationSec: number | undefined): number {
  if (!durationSec || durationSec <= 0) return 0;
  return Math.min(1, Math.max(0, positionMs / (durationSec * 1000)));
}

/** "m:ss" for a duration in seconds, "--:--" when unknown. */
export function formatDuration(seconds: number | undefined): string {
  if (!seconds) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

const pairHas = (pair: ComparisonPair, trackId: number): boolean =>
  pair.track_a.id === trackId || pair.track_b.id === trackId;

/**
 * After a vote loads the next pair: auto-play the new track A only when the
 * player is actively playing a track from the previous pair. Paused, idle,
 * unrelated playback, or a track that carried over into the new pair are
 * left alone.
 */
export function shouldAutoPlayNextPair(
  prevPair: ComparisonPair,
  nextPair: ComparisonPair,
  currentTrackId: number | null | undefined,
  isPlaying: boolean,
): boolean {
  if (!isPlaying || currentTrackId == null) return false;
  return pairHas(prevPair, currentTrackId) && !pairHas(nextPair, currentTrackId);
}
