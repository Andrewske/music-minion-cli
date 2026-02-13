import { create } from 'zustand';
import type { NowPlaying, TrackInfo } from '../api/radio';

interface RadioState {
  isMuted: boolean;
  nowPlaying: NowPlaying | null;
  isLoading: boolean;
  error: string | null;
}

interface RadioActions {
  setMuted: (muted: boolean) => void;
  toggleMute: () => void;
  setNowPlaying: (data: NowPlaying | null) => void;
  updateNowPlayingTrack: (track: TrackInfo) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

type RadioStore = RadioState & RadioActions;

const initialState: RadioState = {
  isMuted: JSON.parse(localStorage.getItem('music-minion-radio-muted') ?? 'true'),
  nowPlaying: null,
  isLoading: false,
  error: null,
};

export const useRadioStore = create<RadioStore>((set) => ({
  ...initialState,

  setMuted: (muted: boolean) => {
    localStorage.setItem('music-minion-radio-muted', JSON.stringify(muted));
    set({ isMuted: muted });
  },

  toggleMute: () => {
    set((state) => {
      const newMuted = !state.isMuted;
      localStorage.setItem('music-minion-radio-muted', JSON.stringify(newMuted));
      return { isMuted: newMuted };
    });
  },

  setNowPlaying: (data: NowPlaying | null) => {
    set({ nowPlaying: data, error: data === null ? null : undefined });
  },

  updateNowPlayingTrack: (track: TrackInfo) => {
    set((state) => {
      if (!state.nowPlaying) return state;
      return {
        ...state,
        nowPlaying: {
          ...state.nowPlaying,
          track,
        },
      };
    });
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));
