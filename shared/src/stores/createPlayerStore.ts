import { create } from 'zustand';
import type { Track } from '../api/builder';
import type { StorageAdapter } from './storage';

// Re-export Track for convenience
export type { Track };

export interface Device {
  id: string;
  name: string;
  connected_at: string;
  isActive: boolean;
}

export interface PlayContext {
  type: 'playlist' | 'track' | 'builder' | 'search' | 'comparison' | 'organizer';
  track_ids?: number[];
  playlist_id?: number;
  builder_id?: number;
  session_id?: string;
  bucket_id?: string;
  query?: string;
  start_index?: number;
  shuffle?: boolean;
}

interface PlaybackState {
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;
  trackStartedAt: number | null;
  positionMs: number;
  isPlaying: boolean;
  activeDeviceId: string | null;
  shuffleEnabled: boolean;
}

export interface PlayerState {
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;
  trackStartedAt: number | null;
  positionMs: number;
  isPlaying: boolean;
  isMuted: boolean;
  volume: number;
  shuffleEnabled: boolean;
  sortField: string | null;
  sortDirection: 'asc' | 'desc' | null;
  clockOffset: number;
  scrobbledThisPlaythrough: boolean;
  thisDeviceId: string;
  thisDeviceName: string;
  activeDeviceId: string | null;
  availableDevices: Device[];
  isThisDeviceActive: boolean;
  playbackError: string | null;
  nextTrackPreloadUrl: string | null;
  needsUserGesture: boolean;
  currentContext: PlayContext | null;
}

export interface PlayerActions {
  play: (track: Track, context: PlayContext) => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  next: () => Promise<void>;
  prev: () => Promise<void>;
  seek: (positionMs: number) => Promise<void>;
  setMuted: (muted: boolean) => void;
  setVolume: (volume: number) => void;
  toggleShuffle: () => void;
  toggleShuffleSmooth: () => Promise<void>;
  setSortOrder: (field: string, direction: 'asc' | 'desc') => Promise<void>;
  setActiveDevice: (deviceId: string) => Promise<void>;
  syncState: (state: PlaybackState & { serverTime: number; sortSpec?: { field: string; direction: 'asc' | 'desc' } | null; currentContext?: PlayContext | null }) => void;
  syncDevices: (devices: Device[]) => void;
  setPlaybackError: (error: string | null) => void;
  retryPlayback: () => void;
  preloadNextTrack: () => void;
  onTrackPlayed: (trackId: number, playedMs: number) => void;
  renameDevice: (name: string) => void;
  registerDevice: () => void;
  set: (partial: Partial<PlayerState>) => void;
}

export type PlayerStore = PlayerState & PlayerActions;

/** Platform-specific dependencies injected at app init */
export interface PlatformDeps {
  storage: StorageAdapter;
  apiBase: string;
  getDeviceName: () => string;
  generateDeviceId: () => string;
  preloadAudio?: (url: string) => void;
}

export function getCurrentPosition(state: PlayerState): number {
  if (!state.isPlaying || !state.trackStartedAt) return state.positionMs;
  return state.positionMs + (Date.now() + state.clockOffset - state.trackStartedAt);
}

export const createPlayerStore = (deps: PlatformDeps) => {
  const { storage, apiBase, getDeviceName: getDeviceNameFn, generateDeviceId: generateDeviceIdFn, preloadAudio } = deps;

  const apiPost = async <T = Record<string, unknown>>(endpoint: string, body?: unknown): Promise<T> => {
    const init: RequestInit = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) init.body = JSON.stringify(body);
    const response = await fetch(`${apiBase}${endpoint}`, init);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  };

  const initialVolume = parseFloat(storage.getItem('music-minion-volume') ?? '1.0');

  const initialState: PlayerState = {
    currentTrack: null,
    queue: [],
    queueIndex: 0,
    trackStartedAt: null,
    positionMs: 0,
    isPlaying: false,
    isMuted: JSON.parse(storage.getItem('music-minion-player-muted') ?? 'false'),
    volume: initialVolume,
    shuffleEnabled: JSON.parse(storage.getItem('music-minion-shuffle') ?? 'true'),
    sortField: null,
    sortDirection: null,
    clockOffset: 0,
    scrobbledThisPlaythrough: false,
    thisDeviceId: generateDeviceIdFn(),
    thisDeviceName: getDeviceNameFn(),
    activeDeviceId: null,
    availableDevices: [],
    isThisDeviceActive: false,
    playbackError: null,
    nextTrackPreloadUrl: null,
    needsUserGesture: false,
    currentContext: null,
  };

  return create<PlayerStore>()((set: (partial: Partial<PlayerStore> | ((state: PlayerStore) => Partial<PlayerStore>)) => void, get: () => PlayerStore) => ({
    ...initialState,

    play: async (track: Track, context: PlayContext) => {
      const { shuffleEnabled, thisDeviceId, activeDeviceId } = get();
      set({ playbackError: null });

      try {
        const response = await fetch(`${apiBase}/player/play`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            trackId: track.id,
            context: { ...context, shuffle: context.shuffle ?? shuffleEnabled },
            targetDeviceId: activeDeviceId ?? thisDeviceId,
          }),
        });

        if (!response.ok) {
          const errorBody = await response.json().catch(() => ({}));
          const detail = errorBody.detail || response.statusText;
          throw new Error(`Play failed: ${detail}`);
        }

        set({ currentContext: context });
      } catch (error) {
        set({ playbackError: error instanceof Error ? error.message : 'Playback failed' });
      }
    },

    pause: async () => {
      try {
        const response = await fetch(`${apiBase}/player/pause`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to pause');
      } catch (error) {
        set({ playbackError: error instanceof Error ? error.message : 'Pause failed' });
      }
    },

    resume: async () => {
      const { thisDeviceId, activeDeviceId } = get();
      try {
        const response = await fetch(`${apiBase}/player/resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_device_id: activeDeviceId ?? thisDeviceId }),
        });
        if (!response.ok) throw new Error('Failed to resume');
      } catch (error) {
        set({ playbackError: error instanceof Error ? error.message : 'Resume failed' });
      }
    },

    next: async () => {
      try {
        const response = await fetch(`${apiBase}/player/next`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to skip to next track');
      } catch (error) {
        set({ playbackError: error instanceof Error ? error.message : 'Skip failed' });
      }
    },

    prev: async () => {
      try {
        const response = await fetch(`${apiBase}/player/prev`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to go to previous track');
      } catch (error) {
        set({ playbackError: error instanceof Error ? error.message : 'Previous failed' });
      }
    },

    seek: async (positionMs: number) => {
      try {
        const response = await fetch(`${apiBase}/player/seek`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ positionMs: Math.round(positionMs) }),
        });
        if (!response.ok) throw new Error('Failed to seek');
      } catch (error) {
        set({ playbackError: error instanceof Error ? error.message : 'Seek failed' });
      }
    },

    setMuted: (muted: boolean) => {
      storage.setItem('music-minion-player-muted', JSON.stringify(muted));
      set({ isMuted: muted });
    },

    setVolume: (volume: number) => {
      storage.setItem('music-minion-volume', volume.toString());
      set({ volume });
    },

    toggleShuffle: () => {
      const { shuffleEnabled, currentContext, currentTrack } = get();
      const newShuffleEnabled = !shuffleEnabled;

      storage.setItem('music-minion-shuffle', JSON.stringify(newShuffleEnabled));
      set({ shuffleEnabled: newShuffleEnabled });

      if (currentContext && currentTrack) {
        fetch(`${apiBase}/player/play`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            trackId: currentTrack.id,
            context: { ...currentContext, shuffle: newShuffleEnabled },
          }),
        });
      }
    },

    toggleShuffleSmooth: async () => {
      try {
        const result = await apiPost<{ shuffle_enabled: boolean }>('/player/toggle-shuffle');
        set({
          shuffleEnabled: result.shuffle_enabled,
          sortField: null,
          sortDirection: null,
        });
      } catch (error) {
        set({ playbackError: (error as Error).message });
      }
    },

    setSortOrder: async (field: string, direction: 'asc' | 'desc') => {
      try {
        await apiPost('/player/set-sort', { field, direction });
        set({
          sortField: field,
          sortDirection: direction,
          shuffleEnabled: false,
        });
      } catch (error) {
        set({ playbackError: (error as Error).message });
      }
    },

    setActiveDevice: async (deviceId: string) => {
      try {
        await fetch(`${apiBase}/player/transfer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_id: deviceId }),
        });
      } catch {
        // Transfer errors are non-critical
      }
    },

    syncState: (state: PlaybackState & { serverTime: number; sortSpec?: { field: string; direction: 'asc' | 'desc' } | null; currentContext?: PlayContext | null }) => {
      // Skip if state is already in sync (prevents WebSocket echo causing stutter)
      const current = get();
      if (
        current.currentTrack?.id === state.currentTrack?.id &&
        current.isPlaying === state.isPlaying &&
        current.activeDeviceId === state.activeDeviceId &&
        Math.abs((current.positionMs ?? 0) - (state.positionMs ?? 0)) < 2000
      ) {
        return;
      }

      const prevTrackId = get().currentTrack?.id;
      const newTrackId = state.currentTrack?.id;
      const scrobbledThisPlaythrough = prevTrackId === newTrackId ? get().scrobbledThisPlaythrough : false;
      const currentTrack = prevTrackId === newTrackId && prevTrackId != null
        ? get().currentTrack
        : state.currentTrack;
      const clockOffset = state.serverTime - Date.now();
      const sortField = state.sortSpec?.field ?? null;
      const sortDirection = state.sortSpec?.direction ?? null;

      set({
        currentTrack,
        queue: state.queue,
        queueIndex: state.queueIndex,
        trackStartedAt: state.trackStartedAt,
        positionMs: state.positionMs,
        isPlaying: state.isPlaying,
        activeDeviceId: state.activeDeviceId,
        shuffleEnabled: state.shuffleEnabled,
        sortField,
        sortDirection,
        clockOffset,
        scrobbledThisPlaythrough,
        isThisDeviceActive: state.activeDeviceId === get().thisDeviceId,
        currentContext: state.currentContext ?? get().currentContext,
      });
    },

    syncDevices: (devices: Device[]) => {
      set({
        availableDevices: devices,
        isThisDeviceActive: devices.find((d) => d.id === get().thisDeviceId)?.isActive ?? false,
      });
    },

    setPlaybackError: (error: string | null) => {
      set({ playbackError: error });
    },

    retryPlayback: () => {
      const { currentTrack } = get();
      if (currentTrack) {
        set({ playbackError: null });
        get().play(currentTrack, { type: 'track' });
      }
    },

    preloadNextTrack: () => {
      const { queue, queueIndex } = get();
      if (queueIndex + 1 < queue.length) {
        const nextTrack = queue[queueIndex + 1];
        const preloadUrl = `${apiBase}/tracks/${nextTrack.id}/stream`;
        set({ nextTrackPreloadUrl: preloadUrl });
        preloadAudio?.(preloadUrl);
      }
    },

    onTrackPlayed: async (trackId: number, playedMs: number) => {
      set({ scrobbledThisPlaythrough: true });
      try {
        await fetch(`${apiBase}/tracks/${trackId}/scrobble`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ played_ms: playedMs }),
        });
      } catch {
        // Ignore scrobble errors
      }
    },

    renameDevice: (name: string) => {
      const trimmed = name.trim();
      if (trimmed) {
        storage.setItem('music-minion-device-name', trimmed);
      } else {
        storage.removeItem('music-minion-device-name');
      }
      set({ thisDeviceName: trimmed || getDeviceNameFn() });
    },

    registerDevice: () => {
      // WebSocket connection handles the actual registration
    },

    set: (partial: Partial<PlayerState>) => {
      set(partial);
    },
  }));
};
