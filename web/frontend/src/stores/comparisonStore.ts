import { create } from 'zustand';
import type { ComparisonPair } from '../types';

interface ComparisonState {
  sessionId: string | null;
  currentPair: ComparisonPair | null;
  playingTrackId: number | null;
  comparisonsCompleted: number;
  targetComparisons: number;
}

interface ComparisonActions {
  setSession: (sessionId: string, pair: ComparisonPair, targetComparisons: number) => void;
  setPlaying: (trackId: number | null) => void;
  incrementCompleted: () => void;
  reset: () => void;
  setCurrentPair: (pair: ComparisonPair) => void;
}

type ComparisonStore = ComparisonState & ComparisonActions;

const initialState: ComparisonState = {
  sessionId: null,
  currentPair: null,
  playingTrackId: null,
  comparisonsCompleted: 0,
  targetComparisons: 15,
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  setSession: (sessionId, pair, targetComparisons) => {
    set({
      sessionId,
      currentPair: pair,
      targetComparisons,
      comparisonsCompleted: 0,
      playingTrackId: null,
    });
  },

  setPlaying: (trackId) => {
    set({ playingTrackId: trackId });
  },

  incrementCompleted: () => {
    const current = get().comparisonsCompleted;
    set({ comparisonsCompleted: current + 1 });
  },

  reset: () => {
    set(initialState);
  },

  setCurrentPair: (pair: ComparisonPair) => {
    set({ currentPair: pair });
  },
}));