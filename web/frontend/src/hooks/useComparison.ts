import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { startComparison, recordComparison, undoComparison } from '../api/comparisons';
import { removeTrackFromPlaylist } from '../api/playlists';
import { prefetchWaveform } from '../api/tracks';
import { useComparisonStore } from '../stores/comparisonStore';
import { usePlayerStore } from '../stores/playerStore';
import type { ComparisonPair, ComparisonResponse } from '../types';

/** Prefetch the new pair's waveforms and, when autoplay is on, start track A. */
function primePair(pair: ComparisonPair | null, autoplay: boolean): void {
  if (!pair) return;
  prefetchWaveform(pair.track_a.id);
  prefetchWaveform(pair.track_b.id);
  // Read autoplay at call time so a toggle mid-request is respected
  if (autoplay && useComparisonStore.getState().autoplay) {
    const trackIds = [pair.track_a.id, pair.track_b.id];
    void usePlayerStore.getState().play(pair.track_a, { type: 'comparison', track_ids: trackIds, shuffle: false });
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function useStartComparison() {
  const queryClient = useQueryClient();
  const { startComparison: setComparisonState } = useComparisonStore();

  return useMutation({
    mutationFn: (playlistId: number) => startComparison(playlistId),
    onSuccess: (response, playlistId) => {
      setComparisonState(playlistId, response.pair, response.progress);
      primePair(response.pair, false);
      queryClient.invalidateQueries({ queryKey: ['comparisons'] });
    },
  });
}

export interface PickWinnerInput {
  playlistId: number;
  pair: ComparisonPair;
  winnerId: number;
}

export function useRecordComparison() {
  return useMutation({
    mutationFn: ({ playlistId, pair, winnerId }: PickWinnerInput) =>
      recordComparison({
        playlist_id: playlistId,
        track_a_id: pair.track_a.id,
        track_b_id: pair.track_b.id,
        winner_id: winnerId,
      }),
    onSuccess: (response, { pair, winnerId }) => {
      const winnerIsA = winnerId === pair.track_a.id;
      useComparisonStore.getState().recordComparison(response.pair, response.progress, {
        trackAId: pair.track_a.id,
        trackBId: pair.track_b.id,
        winnerTitle: (winnerIsA ? pair.track_a : pair.track_b).title,
        loserTitle: (winnerIsA ? pair.track_b : pair.track_a).title,
        ratingDelta: response.rating_delta ?? null,
      });
      primePair(response.pair, true);
    },
    onError: (error) => toast.error(`Pick not saved: ${errorMessage(error)}`),
  });
}

/**
 * Fetch a different pair without recording anything. Pairing is random among
 * the least-compared tracks, so retry a couple of times if the same pair comes back.
 */
async function fetchOtherPair(playlistId: number, current: ComparisonPair): Promise<ComparisonResponse> {
  const sameIds = (pair: ComparisonPair | null): boolean =>
    pair !== null
    && new Set([pair.track_a.id, pair.track_b.id, current.track_a.id, current.track_b.id]).size === 2;
  let response = await startComparison(playlistId);
  for (let attempt = 0; attempt < 2 && sameIds(response.pair); attempt++) {
    response = await startComparison(playlistId);
  }
  return response;
}

export function useSkipPair() {
  return useMutation({
    mutationFn: ({ playlistId, pair }: { playlistId: number; pair: ComparisonPair }) =>
      fetchOtherPair(playlistId, pair),
    onSuccess: (response) => {
      useComparisonStore.getState().replacePair(response.pair, response.progress);
      primePair(response.pair, true);
    },
    onError: (error) => toast.error(`Skip failed: ${errorMessage(error)}`),
  });
}

export function useRemoveFromPlaylist() {
  return useMutation({
    mutationFn: async ({ playlistId, trackId }: { playlistId: number; trackId: number; title: string }) => {
      await removeTrackFromPlaylist(playlistId, trackId);
      return startComparison(playlistId);
    },
    onSuccess: (response, { title }) => {
      useComparisonStore.getState().replacePair(response.pair, response.progress);
      primePair(response.pair, true);
      toast.success(`Removed "${title}" from playlist`);
    },
    onError: (error, { title }) => toast.error(`Could not remove "${title}": ${errorMessage(error)}`),
  });
}

export function useUndoComparison() {
  return useMutation({
    mutationFn: ({ playlistId, trackAId, trackBId }: { playlistId: number; trackAId: number; trackBId: number }) =>
      undoComparison({ playlist_id: playlistId, track_a_id: trackAId, track_b_id: trackBId }),
    onSuccess: (response) => {
      useComparisonStore.getState().undoComparison(response.pair, response.progress);
      primePair(response.pair, true);
    },
    onError: (error) => toast.error(`Undo failed: ${errorMessage(error)}`),
  });
}
