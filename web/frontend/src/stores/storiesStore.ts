import { create } from 'zustand';
import type { StoriesResponse } from '../api/stories';
import {
  createSession,
  storiesReducer,
  type StoriesAction,
  type StoriesSession,
} from '../components/stories/storiesQueue';

interface StoriesStore {
  /** Client snapshot of GET /stories; survives route changes until reset. */
  session: StoriesSession | null;
  start: (response: StoriesResponse, playingLocalTrackId?: number | null) => void;
  dispatch: (action: StoriesAction) => void;
  reset: () => void;
}

/** Thin Zustand shell around the pure reducer in components/stories/storiesQueue.ts. */
export const useStoriesStore = create<StoriesStore>((set) => ({
  session: null,
  start: (response, playingLocalTrackId = null) => set({ session: createSession(response, playingLocalTrackId) }),
  dispatch: (action) =>
    set((state) => (state.session ? { session: storiesReducer(state.session, action) } : state)),
  reset: () => set({ session: null }),
}));
