import { beforeEach, describe, expect, it } from 'vitest';
import { useComparisonStore, type ComparisonHistoryEntry } from './comparisonStore';
import type { ComparisonPair, ComparisonProgress, TrackInfo } from '../types';

const track = (id: number): TrackInfo => ({
  id, title: `T${id}`, rating: 1500, comparison_count: 0, wins: 0, losses: 0, has_waveform: false,
});
const pair = (a: number, b: number): ComparisonPair => ({ track_a: track(a), track_b: track(b) });
const progress: ComparisonProgress = { compared: 1, total: 10, percentage: 10 };
const entry = (a: number, b: number): ComparisonHistoryEntry => ({
  comparisonId: a * 100 + b, trackAId: a, trackBId: b, winnerTitle: `T${a}`, loserTitle: `T${b}`, ratingDelta: 16,
});

describe('comparisonStore history', () => {
  beforeEach(() => {
    useComparisonStore.getState().reset();
    useComparisonStore.getState().startComparison(7, pair(1, 2), progress);
  });

  it('records picks newest first and counts them', () => {
    const store = useComparisonStore.getState();
    store.recordComparison(pair(3, 4), progress, entry(1, 2));
    store.recordComparison(pair(5, 6), progress, entry(3, 4));
    const state = useComparisonStore.getState();
    expect(state.history.map((h) => h.trackAId)).toEqual([3, 1]);
    expect(state.comparisonsCompleted).toBe(2);
  });

  it('undo restores the pair and drops only the newest entry', () => {
    const store = useComparisonStore.getState();
    store.recordComparison(pair(3, 4), progress, entry(1, 2));
    store.recordComparison(pair(5, 6), progress, entry(3, 4));
    store.undoComparison(pair(3, 4), progress);
    const state = useComparisonStore.getState();
    expect(state.currentPair?.track_a.id).toBe(3);
    expect(state.history.map((h) => h.trackAId)).toEqual([1]);
    expect(state.comparisonsCompleted).toBe(1);
  });

  it('replacing the pair (skip/remove) does not count a pick', () => {
    useComparisonStore.getState().replacePair(pair(8, 9), progress);
    const state = useComparisonStore.getState();
    expect(state.currentPair?.track_a.id).toBe(8);
    expect(state.comparisonsCompleted).toBe(0);
    expect(state.history).toEqual([]);
  });

  it('keeps history when the same playlist restarts, clears it for another', () => {
    const store = useComparisonStore.getState();
    store.recordComparison(pair(3, 4), progress, entry(1, 2));
    store.startComparison(7, pair(3, 4), progress);
    expect(useComparisonStore.getState().history).toHaveLength(1);
    store.startComparison(8, pair(10, 11), progress);
    expect(useComparisonStore.getState().history).toEqual([]);
  });
});
