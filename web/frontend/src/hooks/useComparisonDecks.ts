import { useCallback } from 'react';
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

/** The pair track that isn't playing; track A when neither is. */
export function otherDeck(pair: ComparisonPair): TrackInfo {
  const currentId = usePlayerStore.getState().currentTrack?.id;
  return currentId === pair.track_a.id ? pair.track_b : pair.track_a;
}

export interface ComparisonDeckActions {
  isBusy: boolean;
  togglePlay: (track: TrackInfo) => void;
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

  // Fresh store reads so keyboard handlers never act on a stale pair
  const session = (): { pair: ComparisonPair; playlistId: number } | null => {
    const { currentPair, selectedPlaylistId } = useComparisonStore.getState();
    return currentPair && selectedPlaylistId ? { pair: currentPair, playlistId: selectedPlaylistId } : null;
  };

  const pick = useCallback((slot: 'a' | 'b'): void => {
    const s = session();
    if (!s || isBusy) return;
    const winner = slot === 'a' ? s.pair.track_a : s.pair.track_b;
    record.mutate({ playlistId: s.playlistId, pair: s.pair, winnerId: winner.id });
  }, [isBusy, record]);

  const skip = useCallback((): void => {
    const s = session();
    if (s && !isBusy) skipPair.mutate(s);
  }, [isBusy, skipPair]);

  const remove = useCallback((track: TrackInfo): void => {
    const s = session();
    if (s && !isBusy) removeTrack.mutate({ playlistId: s.playlistId, trackId: track.id, title: track.title });
  }, [isBusy, removeTrack]);

  const undo = useCallback((): void => {
    const { history, selectedPlaylistId } = useComparisonStore.getState();
    const last = history[0];
    if (!last || !selectedPlaylistId || isBusy) return;
    undoPick.mutate({ playlistId: selectedPlaylistId, trackAId: last.trackAId, trackBId: last.trackBId });
  }, [isBusy, undoPick]);

  const togglePlay = useCallback((track: TrackInfo): void => {
    const s = session();
    if (s) toggleDeck(s.pair, track);
  }, []);

  const flip = useCallback((): void => {
    const s = session();
    if (s) toggleDeck(s.pair, otherDeck(s.pair));
  }, []);

  return { isBusy, togglePlay, flip, pick, skip, remove, undo };
}
