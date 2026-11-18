import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { startComparison, recordComparison, undoComparison } from '../api/comparisons';
import { ApiError } from '../api/client';
import { removeTrackFromPlaylist } from '../api/playlists';
import { prefetchWaveform } from '../api/tracks';
import { useComparisonStore } from '../stores/comparisonStore';
import { usePlayerStore } from '../stores/playerStore';
import type { ComparisonPair, ComparisonProgress, ComparisonResponse } from '../types';

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

/**
 * A response for `playlistId` still belongs on screen. False once the user has
 * moved to another playlist, so a late reply can't overwrite the new session.
 */
function isCurrentPlaylist(playlistId: number): boolean {
  return useComparisonStore.getState().selectedPlaylistId === playlistId;
}

const samePair = (x: ComparisonPair, y: ComparisonPair): boolean =>
  new Set([x.track_a.id, x.track_b.id, y.track_a.id, y.track_b.id]).size === 2;

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
    onSuccess: (response, { playlistId, pair, winnerId }) => {
      if (!isCurrentPlaylist(playlistId) || response.comparison_id == null) return;
      const winnerIsA = winnerId === pair.track_a.id;
      useComparisonStore.getState().recordComparison(response.pair, response.progress, {
        comparisonId: response.comparison_id,
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
 * A different pair without recording anything, or null when none turned up.
 * Pairing is random among the least-compared tracks, so retry a few times.
 * A null pair from the server isn't trusted as "complete" here: its anchor
 * choice is random and can miss pairs that are still open.
 */
async function fetchOtherPair(playlistId: number, current: ComparisonPair): Promise<ComparisonResponse | null> {
  for (let attempt = 0; attempt < 4; attempt++) {
    const response = await startComparison(playlistId);
    if (response.pair && !samePair(response.pair, current)) return response;
  }
  return null;
}

export function useSkipPair() {
  return useMutation({
    mutationFn: ({ playlistId, pair }: { playlistId: number; pair: ComparisonPair }) =>
      fetchOtherPair(playlistId, pair),
    onSuccess: (response, { playlistId }) => {
      if (!isCurrentPlaylist(playlistId)) return;
      if (!response) {
        toast.info('No other pair to compare right now');
        return;
      }
      useComparisonStore.getState().replacePair(response.pair, response.progress);
      primePair(response.pair, true);
    },
    onError: (error) => toast.error(`Skip failed: ${errorMessage(error)}`),
  });
}

interface RemoveInput {
  playlistId: number;
  trackId: number;
  title: string;
}

/**
 * After a removal, the next pair. A playlist left with under two tracks
 * can't be compared, so that ends the session instead of failing the removal.
 */
async function pairAfterRemoval(playlistId: number, progress: ComparisonProgress | null): Promise<ComparisonResponse> {
  try {
    return await startComparison(playlistId);
  } catch {
    return { pair: null, progress: progress ?? { compared: 0, total: 0, percentage: 0 } };
  }
}

export function useRemoveFromPlaylist() {
  return useMutation({
    mutationFn: async ({ playlistId, trackId }: RemoveInput) => {
      await removeTrackFromPlaylist(playlistId, trackId);
      return pairAfterRemoval(playlistId, useComparisonStore.getState().progress);
    },
    onSuccess: (response, { playlistId, title }) => {
      toast.success(`Removed "${title}" from playlist`);
      if (!isCurrentPlaylist(playlistId)) return;
      useComparisonStore.getState().replacePair(response.pair, response.progress);
      primePair(response.pair, true);
    },
    onError: (error, { title }) => toast.error(`Could not remove "${title}": ${errorMessage(error)}`),
  });
}

export function useUndoComparison() {
  return useMutation({
    mutationFn: ({ playlistId, comparisonId }: { playlistId: number; comparisonId: number }) =>
      undoComparison({ playlist_id: playlistId, comparison_id: comparisonId }),
    onSuccess: (response, { playlistId }) => {
      if (!isCurrentPlaylist(playlistId)) return;
      useComparisonStore.getState().undoComparison(response.pair, response.progress);
      primePair(response.pair, true);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        // Permanently un-undoable; drop it so Undo moves on to older picks
        useComparisonStore.getState().discardLatestPick();
        toast.error("Can't undo that pick: a newer pick or rating change already used it");
        return;
      }
      toast.error(`Undo failed: ${errorMessage(error)}`);
    },
  });
}
