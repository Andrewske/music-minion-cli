import { create } from 'zustand';
import type { ComparisonPair, TrackInfo } from '../types';

interface ComparisonState {
  sessionId: string | null;
  currentPair: ComparisonPair | null;
  prefetchedPair: ComparisonPair | null;
  playingTrack: TrackInfo | null;
  comparisonsCompleted: number;
  priorityPathPrefix: string | null;
  isComparisonMode: boolean;
}

interface ComparisonActions {
  setSession: (sessionId: string, pair: ComparisonPair, prefetched?: ComparisonPair, priorityPathPrefix?: string) => void;
  setPlaying: (track: TrackInfo | null) => void;
  incrementCompleted: () => void;
  reset: () => void;
  setCurrentPair: (pair: ComparisonPair, prefetched?: ComparisonPair) => void;
  advanceToNextPair: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => void;
  setPriorityPath: (priorityPathPrefix: string | null) => void;
}

type ComparisonStore = ComparisonState & ComparisonActions;

const initialState: ComparisonState = {
  sessionId: null,
  currentPair: null,
  prefetchedPair: null,
  playingTrack: null,
  comparisonsCompleted: 0,
  priorityPathPrefix: null,
  isComparisonMode: false,
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  setSession: (sessionId, pair, prefetched, priorityPathPrefix) => {
    set({
      sessionId,
      currentPair: pair,
      prefetchedPair: prefetched ?? null,
      comparisonsCompleted: 0,
      playingTrack: null,
      priorityPathPrefix: priorityPathPrefix ?? null,
      isComparisonMode: true,
    });
  },

  setPlaying: (track) => {
    set({ playingTrack: track });
  },

  incrementCompleted: () => {
    const current = get().comparisonsCompleted;
    set({ comparisonsCompleted: current + 1 });
  },

  reset: () => {
    set(initialState);
  },

  setCurrentPair: (pair: ComparisonPair, prefetched?: ComparisonPair) => {
    set({
      currentPair: pair,
      prefetchedPair: prefetched ?? null,
    });
  },

  advanceToNextPair: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => {
    // Optimistically advance - no loading state needed
    set({
      currentPair: nextPair,
      prefetchedPair: prefetched ?? null,
      playingTrack: null, // Reset playing when switching pairs
      isComparisonMode: true, // Keep comparison mode active
    });
  },

  setPriorityPath: (priorityPathPrefix: string | null) => {
    set({ priorityPathPrefix });
  },
}));
