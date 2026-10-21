import { create } from 'zustand';
import {
  INITIAL_LISTEN_STATE,
  listenStatsFor,
  playedListenStatsFor,
  recordListenEvent,
  type ListenEvent,
  type ListenState,
  type ListenStats,
} from '../lib/feedListen';

interface ListenStore extends ListenState {
  record: (event: ListenEvent) => void;
}

/**
 * Session-wide listen tallies, fed by the persistent player's audio elements
 * (see hooks/useAudioListenTracker.ts) so they survive route changes.
 */
export const useListenStore = create<ListenStore>((set) => ({
  ...INITIAL_LISTEN_STATE,
  record: (event) =>
    set((state) => recordListenEvent({ tallies: state.tallies, cursors: state.cursors }, event)),
}));

export function getListenStats(trackId: number | null): ListenStats {
  return listenStatsFor(useListenStore.getState(), trackId);
}

export function getPlayedListenStats(trackId: number | null): ListenStats | undefined {
  return playedListenStatsFor(useListenStore.getState(), trackId);
}
