import { create } from 'zustand';
import type { ComparisonPair, TrackInfo } from '../types';

interface ComparisonState {
  sessionId: string | null;
  currentPair: ComparisonPair | null;
  playingTrack: TrackInfo | null;
  comparisonsCompleted: number;
}

interface ComparisonActions {
  setSession: (sessionId: string, pair: ComparisonPair) => void;
  setPlaying: (track: TrackInfo | null) => void;
  incrementCompleted: () => void;
  reset: () => void;
  setCurrentPair: (pair: ComparisonPair) => void;
}

type ComparisonStore = ComparisonState & ComparisonActions;

const initialState: ComparisonState = {
  sessionId: null,
  currentPair: null,
  playingTrack: null,
  comparisonsCompleted: 0,
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  setSession: (sessionId, pair) => {
    set({
      sessionId,
      currentPair: pair,
      comparisonsCompleted: 0,
      playingTrack: null,
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

  setCurrentPair: (pair: ComparisonPair) => {
    set({ currentPair: pair });
  },
}));