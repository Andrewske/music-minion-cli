import { create } from 'zustand';
import type { ComparisonPair, ComparisonProgress, TrackInfo } from '../types';

interface ComparisonState {
  selectedPlaylistId: number | null;
  currentPair: ComparisonPair | null;
  currentTrack: TrackInfo | null;
  isPlaying: boolean;
  comparisonsCompleted: number;
  priorityPathPrefix: string | null;
  isComparisonMode: boolean;
  autoplay: boolean;
  progress: ComparisonProgress | null;
}

interface ComparisonActions {
  startComparison: (playlistId: number, pair: ComparisonPair | null, progress: ComparisonProgress) => void;
  recordComparison: (pair: ComparisonPair | null, progress: ComparisonProgress) => void;
  reset: () => void;
  setPriorityPath: (priorityPathPrefix: string | null) => void;
  setAutoplay: (enabled: boolean) => void;
  updateTrackInPair: (track: TrackInfo) => void;
}

type ComparisonStore = ComparisonState & ComparisonActions;

const initialState: ComparisonState = {
  selectedPlaylistId: null,
  currentPair: null,
  currentTrack: null,
  isPlaying: false,
  comparisonsCompleted: 0,
  priorityPathPrefix: null,
  isComparisonMode: false,
  autoplay: JSON.parse(localStorage.getItem('music-minion-autoplay') ?? 'true'),
  progress: null,
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  startComparison: (playlistId, pair, progress) => {
    set({
      selectedPlaylistId: playlistId,
      currentPair: pair,
      progress,
      isComparisonMode: true,
    });
  },

  recordComparison: (pair, progress) => {
    set({
      currentPair: pair,
      progress,
      comparisonsCompleted: get().comparisonsCompleted + 1,
      isComparisonMode: pair !== null, // Exit comparison mode if no more pairs
    });
  },

  reset: () => {
    set(initialState);
  },

  setPriorityPath: (priorityPathPrefix: string | null) => {
    set({ priorityPathPrefix });
  },

  setAutoplay: (enabled: boolean) => {
    localStorage.setItem('music-minion-autoplay', JSON.stringify(enabled));
    set({ autoplay: enabled });
  },

  updateTrackInPair: (track: TrackInfo) => {
    const { currentPair } = get();
    if (!currentPair) return;

    const updatedPair = {
      ...currentPair,
      track_a: currentPair.track_a.id === track.id ? track : currentPair.track_a,
      track_b: currentPair.track_b.id === track.id ? track : currentPair.track_b,
    };

    set({
      currentPair: updatedPair,
    });
  },
}));
