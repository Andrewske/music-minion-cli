import { create } from 'zustand';
import type { DimensionPair } from '../types/quicktag';

const API_BASE = '/api/quicktag';

interface QuickTagState {
  dimensions: DimensionPair[];
  currentDimensionIndex: number;
  isLoading: boolean;
  error: string | null;
}

interface QuickTagActions {
  loadDimensions: () => Promise<void>;
  vote: (trackId: number, vote: -1 | 0 | 1) => Promise<void>;
  nextDimension: () => void;
  prevDimension: () => void;
}

type QuickTagStore = QuickTagState & QuickTagActions;

const initialState: QuickTagState = {
  dimensions: [],
  currentDimensionIndex: 0,
  isLoading: false,
  error: null,
};

export const useQuickTagStore = create<QuickTagStore>((set, get) => ({
  ...initialState,

  loadDimensions: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/dimensions`);
      if (!res.ok) throw new Error('Failed to load dimensions');
      const data = await res.json();
      set({ dimensions: data, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: err instanceof Error ? err.message : 'Unknown error' });
    }
  },

  vote: async (trackId: number, vote: -1 | 0 | 1) => {
    const { dimensions, currentDimensionIndex } = get();
    const dimension = dimensions[currentDimensionIndex];
    if (!dimension) return;

    try {
      const res = await fetch(`${API_BASE}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trackId, dimensionId: dimension.id, vote }),
      });
      if (!res.ok) throw new Error('Failed to save vote');
      get().nextDimension();
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Vote failed' });
    }
  },

  nextDimension: () => {
    const { dimensions, currentDimensionIndex } = get();
    if (dimensions.length === 0) return;
    set({ currentDimensionIndex: (currentDimensionIndex + 1) % dimensions.length });
  },

  prevDimension: () => {
    const { dimensions, currentDimensionIndex } = get();
    if (dimensions.length === 0) return;
    set({
      currentDimensionIndex:
        (currentDimensionIndex - 1 + dimensions.length) % dimensions.length,
    });
  },
}));
