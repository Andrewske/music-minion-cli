import { useCallback, useRef } from 'react';
import { useComparisonStore } from '../stores/comparisonStore';
import { usePlayerStore, getCurrentPosition, playFromPosition, type PlayContext } from '../stores/playerStore';
import type { ComparisonPair, TrackInfo } from '../types';
import {
  useRecordComparison,
  useRemoveFromPlaylist,
  useSkipPair,
  useUndoComparison,
} from './useComparison';

function comparisonContext(pair: ComparisonPair): PlayContext {
  return { type: 'comparison', track_ids: [pair.track_a.id, pair.track_b.id], shuffle: false };
}

/**
 * Play/pause `track`. Switching from the pair's other track starts this one
 * at the same position, so A/B listening compares the same part of each song.
 */
export function toggleDeck(pair: ComparisonPair, track: TrackInfo): void {
  const player = usePlayerStore.getState();
  const currentId = player.currentTrack?.id;
  if (currentId === track.id) {
    void (player.isPlaying ? player.pause() : player.resume());
    return;
  }
  const fromPair = currentId === pair.track_a.id || currentId === pair.track_b.id;
  const positionMs = fromPair ? getCurrentPosition(player) : 0;
  void playFromPosition(track, comparisonContext(pair), positionMs);
}

/**
 * `ended` finished playing. With autoplay on, the other deck plays from the
 * top, so an unattended pair loops A, B, A, ...; with it off, playback stops.
 */
export function finishDeck(pair: ComparisonPair, ended: TrackInfo): void {
  if (!useComparisonStore.getState().autoplay) return;
  const other = ended.id === pair.track_a.id ? pair.track_b : pair.track_a;
  void playFromPosition(other, comparisonContext(pair), 0);
}

/** The pair track that isn't playing; track A when neither is. */
export function otherDeck(pair: ComparisonPair): TrackInfo {
  const currentId = usePlayerStore.getState().currentTrack?.id;
  return currentId === pair.track_a.id ? pair.track_b : pair.track_a;
}

export interface ComparisonDeckActions {
  isBusy: boolean;
  togglePlay: (track: TrackInfo) => void;
  finish: (track: TrackInfo) => void;
  flip: () => void;
  pick: (slot: 'a' | 'b') => void;
  skip: () => void;
  remove: (track: TrackInfo) => void;
  undo: () => void;
}

/** Everything the decks and shortcuts can do to the current pair. */
export function useComparisonDecks(): ComparisonDeckActions {
  const record = useRecordComparison();
  const skipPair = useSkipPair();
  const removeTrack = useRemoveFromPlaylist();
  const undoPick = useUndoComparison();
  const isBusy = record.isPending || skipPair.isPending || removeTrack.isPending || undoPick.isPending;

  // isPending only updates on re-render; this ref blocks a second key press
  // that lands before it, so one pair can't be submitted twice.
  const inFlight = useRef(false);
  const guarded = useCallback((run: (done: () => void) => void): void => {
    if (inFlight.current) return;
    inFlight.current = true;
    run(() => { inFlight.current = false; });
  }, []);

  // Fresh store reads so keyboard handlers never act on a stale pair
  const session = (): { pair: ComparisonPair; playlistId: number } | null => {
    const { currentPair, selectedPlaylistId } = useComparisonStore.getState();
    return currentPair && selectedPlaylistId ? { pair: currentPair, playlistId: selectedPlaylistId } : null;
  };

  const pick = useCallback((slot: 'a' | 'b'): void => {
    const s = session();
    if (!s) return;
    const winner = slot === 'a' ? s.pair.track_a : s.pair.track_b;
    guarded((done) => record.mutate({ playlistId: s.playlistId, pair: s.pair, winnerId: winner.id }, { onSettled: done }));
  }, [guarded, record]);

  const skip = useCallback((): void => {
    const s = session();
    if (s) guarded((done) => skipPair.mutate(s, { onSettled: done }));
  }, [guarded, skipPair]);

  const remove = useCallback((track: TrackInfo): void => {
    const s = session();
    if (!s) return;
    const input = { playlistId: s.playlistId, trackId: track.id, title: track.title };
    guarded((done) => removeTrack.mutate(input, { onSettled: done }));
  }, [guarded, removeTrack]);

  const undo = useCallback((): void => {
    const { history, selectedPlaylistId } = useComparisonStore.getState();
    const last = history[0];
    if (!last || !selectedPlaylistId) return;
    const input = { playlistId: selectedPlaylistId, comparisonId: last.comparisonId };
    guarded((done) => undoPick.mutate(input, { onSettled: done }));
  }, [guarded, undoPick]);

  const togglePlay = useCallback((track: TrackInfo): void => {
    const s = session();
    if (s) toggleDeck(s.pair, track);
  }, []);

  const finish = useCallback((track: TrackInfo): void => {
    const s = session();
    if (s) finishDeck(s.pair, track);
  }, []);

  const flip = useCallback((): void => {
    const s = session();
    if (s) toggleDeck(s.pair, otherDeck(s.pair));
  }, []);

  return { isBusy, togglePlay, finish, flip, pick, skip, remove, undo };
}
