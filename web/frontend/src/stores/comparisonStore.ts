import { create } from 'zustand';
import type { ComparisonPair, TrackInfo } from '../types';

interface ComparisonState {
  sessionId: string | null;
  currentPair: ComparisonPair | null;
  prefetchedPair: ComparisonPair | null;
  comparisonsCompleted: number;
  priorityPathPrefix: string | null;
  rankingMode: 'global' | 'playlist' | null;
  selectedPlaylistId: number | null;
  isComparisonMode: boolean;
  autoplay: boolean;               // Whether to auto-select track A when new pairs load
}

interface ComparisonActions {
  setSession: (sessionId: string, pair: ComparisonPair, prefetched?: ComparisonPair, priorityPathPrefix?: string, rankingMode?: 'global' | 'playlist', selectedPlaylistId?: number | null) => void;
  joinSession: (sessionId: string, pair: ComparisonPair, prefetched?: ComparisonPair) => void;  // Join existing session from another device
  incrementCompleted: () => void;
  reset: () => void;
  setCurrentPair: (pair: ComparisonPair, prefetched?: ComparisonPair) => void;
  advanceToNextPair: (nextPair: ComparisonPair, prefetched?: ComparisonPair) => void;
  setNextPairForComparison: (nextPair: ComparisonPair, prefetched?: ComparisonPair, sessionId?: string) => void;  // Update pair for comparison but keep current track playing
  setPriorityPath: (priorityPathPrefix: string | null) => void;
  setAutoplay: (enabled: boolean) => void;
  updateTrackInPair: (track: TrackInfo) => void;  // Update track data (e.g., emojis) while keeping pair
}

type ComparisonStore = ComparisonState & ComparisonActions;

const initialState: ComparisonState = {
  sessionId: null,
  currentPair: null,
  prefetchedPair: null,
  comparisonsCompleted: 0,
  priorityPathPrefix: null,
  rankingMode: null,
  selectedPlaylistId: null,
  isComparisonMode: false,
  autoplay: JSON.parse(localStorage.getItem('music-minion-autoplay') ?? 'true'),
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  setSession: (sessionId, pair, prefetched, priorityPathPrefix, rankingMode, selectedPlaylistId) => {
    set({
      sessionId,
      currentPair: pair,
      prefetchedPair: prefetched ?? null,
      comparisonsCompleted: 0,
      priorityPathPrefix: priorityPathPrefix ?? null,
      rankingMode: rankingMode ?? null,
      selectedPlaylistId: selectedPlaylistId ?? null,
      isComparisonMode: true,
    });
  },

  joinSession: (sessionId, pair, prefetched) => {
    // Join existing session from another device (e.g., phone joining desktop)
    // Only update if we don't already have an active session
    const current = get();
    if (current.sessionId && current.isComparisonMode) {
      // Already in a session, just update the pair
      set({
        currentPair: pair,
        prefetchedPair: prefetched ?? null,
      });
    } else {
      // No active session, join this one
      set({
        sessionId,
        currentPair: pair,
        prefetchedPair: prefetched ?? null,
        isComparisonMode: true,
      });
    }
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
      isComparisonMode: true, // Keep comparison mode active
    });
  },

  setPriorityPath: (priorityPathPrefix: string | null) => {
    set({ priorityPathPrefix });
  },

  setAutoplay: (enabled: boolean) => {
    localStorage.setItem('music-minion-autoplay', JSON.stringify(enabled));
    set({ autoplay: enabled });
  },

  setNextPairForComparison: (nextPair: ComparisonPair, prefetched?: ComparisonPair, sessionId?: string) => {
    // Update pair for comparison - playback state is now in playerStore
    set({
      currentPair: nextPair,
      prefetchedPair: prefetched ?? null,
      isComparisonMode: true, // Keep comparison mode active
      ...(sessionId && { sessionId }), // Update session ID if provided (for joining sessions)
    });
  },

  updateTrackInPair: (track: TrackInfo) => {
    const { currentPair } = get();
    if (!currentPair) return;

    // Update track in pair (track_a or track_b)
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
