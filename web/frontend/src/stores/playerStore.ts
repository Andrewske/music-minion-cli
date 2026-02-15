import { create } from 'zustand';
import type { Track } from '../api/builder';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

interface Device {
  id: string;
  name: string;
  connected_at: string;
  isActive: boolean;
}

interface PlayContext {
  type: 'playlist' | 'track' | 'builder' | 'search' | 'comparison';
  track_ids?: number[];
  playlist_id?: number;
  builder_id?: number;
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

interface PlayerState {
  // Playback
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;
  trackStartedAt: number | null;
  positionMs: number;
  isPlaying: boolean;
  isMuted: boolean;
  volume: number;
  shuffleEnabled: boolean;

  // Clock sync
  clockOffset: number;

  // Scrobble tracking
  scrobbledThisPlaythrough: boolean;

  // Devices
  thisDeviceId: string;
  thisDeviceName: string;
  activeDeviceId: string | null;
  availableDevices: Device[];

  // Derived
  isThisDeviceActive: boolean;

  // Error handling
  playbackError: string | null;

  // Gapless playback
  nextTrackPreloadUrl: string | null;

  // Mobile constraints
  needsUserGesture: boolean;
}

interface PlayerActions {
  play: (track: Track, context: PlayContext) => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  next: () => Promise<void>;
  prev: () => Promise<void>;
  seek: (positionMs: number) => Promise<void>;
  setMuted: (muted: boolean) => void;
  setVolume: (volume: number) => void;
  toggleShuffle: () => void;
  setActiveDevice: (deviceId: string) => void;
  syncState: (state: PlaybackState & { server_time: number }) => void;
  syncDevices: (devices: Device[]) => void;
  setPlaybackError: (error: string | null) => void;
  retryPlayback: () => void;
  preloadNextTrack: () => void;
  onTrackPlayed: (trackId: number, playedMs: number) => void;
  registerDevice: () => void;
  set: (partial: Partial<PlayerState>) => void;
}

type PlayerStore = PlayerState & PlayerActions;

function generateDeviceId(): string {
  const stored = localStorage.getItem('music-minion-device-id');
  if (stored) return stored;

  const uuid = crypto.randomUUID();
  localStorage.setItem('music-minion-device-id', uuid);
  return uuid;
}

function getDeviceName(): string {
  const ua = navigator.userAgent;
  let platform = 'Unknown';
  let browser = 'Unknown';

  // Detect platform
  if (/iPhone|iPad|iPod/.test(ua)) platform = 'iPhone';
  else if (/Android/.test(ua)) platform = 'Android';
  else if (/Macintosh/.test(ua)) platform = 'macOS';
  else if (/Windows/.test(ua)) platform = 'Windows';
  else if (/Linux/.test(ua)) platform = 'Linux';

  // Detect browser
  if (/Chrome/.test(ua) && !/Edg/.test(ua)) browser = 'Chrome';
  else if (/Safari/.test(ua) && !/Chrome/.test(ua)) browser = 'Safari';
  else if (/Firefox/.test(ua)) browser = 'Firefox';
  else if (/Edg/.test(ua)) browser = 'Edge';

  return `${platform} ${browser}`;
}

export function getCurrentPosition(state: PlayerState): number {
  if (!state.isPlaying || !state.trackStartedAt) return state.positionMs;
  return state.positionMs + (Date.now() + state.clockOffset - state.trackStartedAt);
}

const initialVolume = parseFloat(localStorage.getItem('music-minion-volume') ?? '1.0');

const initialState: PlayerState = {
  currentTrack: null,
  queue: [],
  queueIndex: 0,
  trackStartedAt: null,
  positionMs: 0,
  isPlaying: false,
  isMuted: JSON.parse(localStorage.getItem('music-minion-player-muted') ?? 'false'),
  volume: initialVolume,
  shuffleEnabled: true,
  clockOffset: 0,
  scrobbledThisPlaythrough: false,
  thisDeviceId: generateDeviceId(),
  thisDeviceName: getDeviceName(),
  activeDeviceId: null,
  availableDevices: [],
  isThisDeviceActive: false,
  playbackError: null,
  nextTrackPreloadUrl: null,
  needsUserGesture: false,
};

export const usePlayerStore = create<PlayerStore>((set, get) => ({
  ...initialState,

  play: async (track: Track, context: PlayContext) => {
    try {
      const response = await fetch(`${API_BASE}/player/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trackId: track.id,
          context,
          targetDeviceId: get().thisDeviceId,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start playback');
      }

      // State will be updated via WebSocket syncState
    } catch (error) {
      set({ playbackError: error instanceof Error ? error.message : 'Playback failed' });
    }
  },

  pause: async () => {
    try {
      const response = await fetch(`${API_BASE}/player/pause`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to pause');
      }
    } catch (error) {
      set({ playbackError: error instanceof Error ? error.message : 'Pause failed' });
    }
  },

  resume: async () => {
    try {
      const response = await fetch(`${API_BASE}/player/resume`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to resume');
      }
    } catch (error) {
      set({ playbackError: error instanceof Error ? error.message : 'Resume failed' });
    }
  },

  next: async () => {
    try {
      const response = await fetch(`${API_BASE}/player/next`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to skip to next track');
      }
    } catch (error) {
      set({ playbackError: error instanceof Error ? error.message : 'Skip failed' });
    }
  },

  prev: async () => {
    try {
      const response = await fetch(`${API_BASE}/player/prev`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to go to previous track');
      }
    } catch (error) {
      set({ playbackError: error instanceof Error ? error.message : 'Previous failed' });
    }
  },

  seek: async (positionMs: number) => {
    try {
      const response = await fetch(`${API_BASE}/player/seek`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_ms: positionMs }),
      });

      if (!response.ok) {
        throw new Error('Failed to seek');
      }
    } catch (error) {
      set({ playbackError: error instanceof Error ? error.message : 'Seek failed' });
    }
  },

  setMuted: (muted: boolean) => {
    localStorage.setItem('music-minion-player-muted', JSON.stringify(muted));
    set({ isMuted: muted });
  },

  setVolume: (volume: number) => {
    localStorage.setItem('music-minion-volume', volume.toString());
    set({ volume });
  },

  toggleShuffle: () => {
    const newShuffle = !get().shuffleEnabled;
    set({ shuffleEnabled: newShuffle });
    // Note: Client should call play() again with new shuffle value to re-fetch queue
  },

  setActiveDevice: (deviceId: string) => {
    // Simplified: just update active device preference
    set({ activeDeviceId: deviceId });
  },

  syncState: (state: PlaybackState & { server_time: number }) => {
    const prevTrackId = get().currentTrack?.id;
    const newTrackId = state.currentTrack?.id;

    // Reset scrobble tracking on track change
    const scrobbledThisPlaythrough = prevTrackId === newTrackId ? get().scrobbledThisPlaythrough : false;

    // Compute clock offset
    const clockOffset = state.server_time - Date.now();

    set({
      currentTrack: state.currentTrack,
      queue: state.queue,
      queueIndex: state.queueIndex,
      trackStartedAt: state.trackStartedAt,
      positionMs: state.positionMs,
      isPlaying: state.isPlaying,
      activeDeviceId: state.activeDeviceId,
      shuffleEnabled: state.shuffleEnabled,
      clockOffset,
      scrobbledThisPlaythrough,
      isThisDeviceActive: state.activeDeviceId === get().thisDeviceId,
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
      const preloadUrl = `${API_BASE}/tracks/${nextTrack.id}/stream`;
      set({ nextTrackPreloadUrl: preloadUrl });

      // Preload by creating a temporary audio element
      const audio = new Audio();
      audio.src = preloadUrl;
      audio.preload = 'auto';
    }
  },

  onTrackPlayed: async (trackId: number, playedMs: number) => {
    // Mark as scrobbled to prevent duplicates
    set({ scrobbledThisPlaythrough: true });

    // Send scrobble to backend (if endpoint exists)
    try {
      await fetch(`${API_BASE}/tracks/${trackId}/scrobble`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ played_ms: playedMs }),
      });
    } catch {
      // Ignore scrobble errors - not critical
    }
  },

  registerDevice: () => {
    // This will be called from the hook on mount
    // The WebSocket connection will handle the actual registration
  },

  set: (partial: Partial<PlayerState>) => {
    set(partial);
  },
}));
