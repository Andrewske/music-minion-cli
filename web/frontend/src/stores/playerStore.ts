import { create } from 'zustand';
import type { Track } from '../api/builder';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

interface Device {
  id: string;
  name: string;
  connected_at: string;
  isActive: boolean;
}

export interface PlayContext {
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

  // Sort state
  sortField: string | null;
  sortDirection: 'asc' | 'desc' | null;

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

  // Context tracking
  currentContext: PlayContext | null;
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
  toggleShuffleSmooth: () => Promise<void>;
  setSortOrder: (field: string, direction: 'asc' | 'desc') => Promise<void>;
  setActiveDevice: (deviceId: string) => void;
  syncState: (state: PlaybackState & { serverTime: number }) => void;
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

// Helper function for API POST requests
async function apiPost<T = any>(endpoint: string, body?: any): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    ...(body && { body: JSON.stringify(body) }),
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.statusText}`);
  }

  return response.json();
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
  shuffleEnabled: JSON.parse(localStorage.getItem('music-minion-shuffle') ?? 'true'),
  sortField: null,
  sortDirection: null,
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
  currentContext: null,
};

export const usePlayerStore = create<PlayerStore>((set, get) => ({
  ...initialState,

  play: async (track: Track, context: PlayContext) => {
    const { shuffleEnabled, thisDeviceId, activeDeviceId } = get();

    // Show loading state while waiting for backend
    set({ playbackError: null });

    try {
      // Call backend to resolve context to queue (shuffle handled server-side)
      const response = await fetch(`${API_BASE}/player/play`, {
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

      // Store context for shuffle toggle re-fetch
      // Actual playback state comes via WebSocket broadcast - no optimistic update
      set({ currentContext: context });
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
        body: JSON.stringify({ positionMs: Math.round(positionMs) }),
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
    const { shuffleEnabled, currentContext, currentTrack } = get();
    const newShuffleEnabled = !shuffleEnabled;

    // Persist preference
    localStorage.setItem('music-minion-shuffle', JSON.stringify(newShuffleEnabled));
    set({ shuffleEnabled: newShuffleEnabled });

    // Re-fetch queue with new shuffle setting
    // NOTE: This resets position to 0 - known v1 limitation
    // Future: Add /api/player/toggle-shuffle endpoint to reorder without interruption
    if (currentContext && currentTrack) {
      fetch(`${API_BASE}/player/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trackId: currentTrack.id,
          context: { ...currentContext, shuffle: newShuffleEnabled },
        }),
      });
      // State will be updated via WebSocket broadcast
    }
  },

  toggleShuffleSmooth: async () => {
    try {
      const { shuffle_enabled } = await apiPost('/player/toggle-shuffle');

      // Optimistic update (will be confirmed via WebSocket)
      set({
        shuffleEnabled: shuffle_enabled,
        sortField: null,
        sortDirection: null,
      });

      console.log(`Shuffle ${shuffle_enabled ? 'enabled' : 'disabled'} (smooth toggle)`);
    } catch (error) {
      console.error('Error toggling shuffle:', error);
      set({ playbackError: (error as Error).message });
    }
  },

  setSortOrder: async (field: string, direction: 'asc' | 'desc') => {
    try {
      await apiPost('/player/set-sort', { field, direction });

      // Optimistic update
      set({
        sortField: field,
        sortDirection: direction,
        shuffleEnabled: false, // Sort disables shuffle
      });

      console.log(`Queue sorted by ${field} ${direction}`);
    } catch (error) {
      console.error('Error setting sort order:', error);
      set({ playbackError: (error as Error).message });
    }
  },

  setActiveDevice: (deviceId: string) => {
    // Simplified: just update active device preference
    set({ activeDeviceId: deviceId });
  },

  syncState: (state: PlaybackState & { serverTime: number; sortSpec?: { field: string; direction: 'asc' | 'desc' } | null }) => {
    const prevTrackId = get().currentTrack?.id;
    const newTrackId = state.currentTrack?.id;

    // Reset scrobble tracking on track change
    const scrobbledThisPlaythrough = prevTrackId === newTrackId ? get().scrobbledThisPlaythrough : false;

    // Compute clock offset
    const clockOffset = state.serverTime - Date.now();

    // Extract sort spec from backend state
    const sortField = state.sortSpec?.field ?? null;
    const sortDirection = state.sortSpec?.direction ?? null;

    set({
      currentTrack: state.currentTrack,
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
