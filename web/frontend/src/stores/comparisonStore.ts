import { create } from 'zustand';
import type { ComparisonPair, TrackInfo } from '../types';

interface ComparisonState {
  sessionId: string | null;
  currentPair: ComparisonPair | null;
  prefetchedPair: ComparisonPair | null;
  currentTrack: TrackInfo | null;  // Which track is loaded/selected
  isPlaying: boolean;              // Is audio currently playing
  comparisonsCompleted: number;
  priorityPathPrefix: string | null;
  rankingMode: 'global' | 'playlist' | null;
  selectedPlaylistId: number | null;
  isComparisonMode: boolean;
}

interface ComparisonActions {
  setSession: (sessionId: string, pair: ComparisonPair, prefetched?: ComparisonPair, priorityPathPrefix?: string, rankingMode?: 'global' | 'playlist', selectedPlaylistId?: number | null) => void;
  setCurrentTrack: (track: TrackInfo | null) => void;
  setIsPlaying: (playing: boolean) => void;
  togglePlaying: () => void;
  selectAndPlay: (track: TrackInfo) => void;
  incrementCompleted: () => void;
  reset: () => void;
  setCurrentPair: (pair: ComparisonPair, prefetched?: ComparisonPair) => void;
  advanceToNextPair: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => void;
  setNextPairForComparison: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => void;  // Update pair for comparison but keep current track playing
  setPriorityPath: (priorityPathPrefix: string | null) => void;
}

type ComparisonStore = ComparisonState & ComparisonActions;

const initialState: ComparisonState = {
  sessionId: null,
  currentPair: null,
  prefetchedPair: null,
  currentTrack: null,
  isPlaying: false,
  comparisonsCompleted: 0,
  priorityPathPrefix: null,
  rankingMode: null,
  selectedPlaylistId: null,
  isComparisonMode: false,
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  setSession: (sessionId, pair, prefetched, priorityPathPrefix, rankingMode, selectedPlaylistId) => {
    console.log('ComparisonStore setSession called with:', {
      sessionId,
      rankingMode,
      selectedPlaylistId,
      priorityPathPrefix,
      hasPair: !!pair,
      hasPrefetched: !!prefetched
    });
    set({
      sessionId,
      currentPair: pair,
      prefetchedPair: prefetched ?? null,
      currentTrack: pair.track_a,  // Load track A
      isPlaying: false,            // But don't play yet
      comparisonsCompleted: 0,
      priorityPathPrefix: priorityPathPrefix ?? null,
      rankingMode: rankingMode ?? null,
      selectedPlaylistId: selectedPlaylistId ?? null,
      isComparisonMode: true,
    });
  },

  togglePlaying: () => {
    const { isPlaying, currentTrack, currentPair } = get();
    if (!currentTrack && currentPair) {
      // No track loaded, load track A and play
      set({ currentTrack: currentPair.track_a, isPlaying: true });
    } else {
      set({ isPlaying: !isPlaying });
    }
  },

  selectAndPlay: (track) => {
    set({ currentTrack: track, isPlaying: true });
  },

  setCurrentTrack: (track) => {
    set({ currentTrack: track });
  },

  setIsPlaying: (playing) => {
    set({ isPlaying: playing });
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
      currentTrack: nextPair.track_a,  // Load track A
      isPlaying: false,                // Wait for user action
      isComparisonMode: true, // Keep comparison mode active
    });
  },

  setPriorityPath: (priorityPathPrefix: string | null) => {
    set({ priorityPathPrefix });
  },

  setNextPairForComparison: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => {
    // Update pair for comparison but keep current track and playing state
    set({
      currentPair: nextPair,
      prefetchedPair: prefetched ?? null,
      isComparisonMode: true, // Keep comparison mode active
    });
  },
}));
