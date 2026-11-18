import { create } from 'zustand';
import type { ComparisonPair, ComparisonProgress, TrackInfo } from '../types';

/** One recorded pick, newest first in `history`; the head is what Undo rewinds. */
export interface ComparisonHistoryEntry {
  trackAId: number;
  trackBId: number;
  winnerTitle: string;
  loserTitle: string;
  ratingDelta: number | null;
}

const MAX_HISTORY = 10;

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
  history: ComparisonHistoryEntry[];
}

interface ComparisonActions {
  startComparison: (playlistId: number, pair: ComparisonPair | null, progress: ComparisonProgress) => void;
  recordComparison: (pair: ComparisonPair | null, progress: ComparisonProgress, entry: ComparisonHistoryEntry) => void;
  /** Replace the pair without counting a pick (skip, remove from playlist). */
  replacePair: (pair: ComparisonPair | null, progress: ComparisonProgress) => void;
  /** Put the undone pair back and drop the newest history entry. */
  undoComparison: (pair: ComparisonPair | null, progress: ComparisonProgress) => void;
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
  history: [],
};

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  ...initialState,

  startComparison: (playlistId, pair, progress) => {
    const samePlaylist = get().selectedPlaylistId === playlistId;
    set({
      selectedPlaylistId: playlistId,
      currentPair: pair,
      progress,
      isComparisonMode: true,
      history: samePlaylist ? get().history : [],
    });
  },

  recordComparison: (pair, progress, entry) => {
    set({
      currentPair: pair,
      progress,
      comparisonsCompleted: get().comparisonsCompleted + 1,
      isComparisonMode: pair !== null, // Exit comparison mode if no more pairs
      history: [entry, ...get().history].slice(0, MAX_HISTORY),
    });
  },

  replacePair: (pair, progress) => {
    set({ currentPair: pair, progress, isComparisonMode: pair !== null });
  },

  undoComparison: (pair, progress) => {
    set({
      currentPair: pair,
      progress,
      comparisonsCompleted: Math.max(0, get().comparisonsCompleted - 1),
      isComparisonMode: pair !== null,
      history: get().history.slice(1),
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
