import { create } from 'zustand';
import type { Track } from '../api/builder';
import { fetchPlayerQueue } from '../api/player';
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
  type: 'playlist' | 'track' | 'builder' | 'search' | 'comparison' | 'organizer' | 'feed';
  track_ids?: number[];
  playlist_id?: number;
  builder_id?: number;
  session_id?: string;
  bucket_id?: string;
  query?: string;
  start_index?: number;
  shuffle?: boolean;
}

/**
 * Wire shape accepted by syncState().
 *
 * Slim `playback:state` broadcasts omit `queue` entirely — they carry
 * `queueVersion`/`queueLength` instead, and the store refetches
 * GET /player/queue when the version moves past what it holds. Fat payloads
 * (the `sync:full` message on WS connect, GET /player/state) include `queue`.
 */
export interface SyncStatePayload {
  currentTrack: Track | null;
  /** Present on fat payloads (sync:full) only; slim broadcasts omit it. */
  queue?: Track[];
  queueIndex: number;
  trackStartedAt: number | null;
  positionMs: number;
  isPlaying: boolean;
  activeDeviceId: string | null;
  shuffleEnabled: boolean;
  serverTime: number;
  sortSpec?: { field: string; direction: 'asc' | 'desc' } | null;
  currentContext?: PlayContext | null;
  /** Monotonic server counter for queue CONTENT changes. */
  queueVersion?: number;
  /** Total tracks in the server-side queue (slim payloads). */
  queueLength?: number;
  /** Monotonic per-broadcast sequence; late/stale broadcasts are dropped. */
  stateSeq?: number;
  // pruned_track_id is a broadcast-only snake_case hint (wire format), not part of the camelCase state.
  pruned_track_id?: number | null;
}

export interface PlayerState {
  currentTrack: Track | null;
  queue: Track[];
  /**
   * Server queue_version the stored `queue` array corresponds to. Slim
   * broadcasts with the SAME version keep the existing queue array identity
   * (memoized rows never re-render); a NEWER version triggers a single-flight
   * GET /player/queue refetch. Only advanced when queue content actually
   * lands (fat sync payload or completed fetch) so a failed fetch is retried
   * by the next broadcast.
   */
  queueVersion: number;
  /** Last applied broadcast stateSeq — older (late) broadcasts are dropped. */
  lastStateSeq: number;
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
  needsUserGesture: boolean;
  currentContext: PlayContext | null;
  lastSeekAt: number;
  /**
   * True between a local (client-side) queue advance — gapless advanceLocal()
   * on `ended` OR an optimistic button-next — and the next playback:state
   * broadcast. While set, duplicate advance triggers (a second `ended`, a
   * second optimistic next) must be suppressed.
   */
  pendingLocalAdvance: boolean;
  /**
   * Last dead track the server pruned from the queue (the broadcast-only
   * `pruned_track_id` hint on playback:state) plus when this client saw it.
   * The playback hooks' error-skip timers re-check these at fire time via
   * shouldSuppressPrunedSkip(): if the server already pruned (and advanced
   * past) the errored track, firing next() would double-advance and skip a
   * good track.
   */
  lastPrunedTrackId: number | null;
  lastPrunedAt: number | null;
}

export interface PlayerActions {
  play: (track: Track, context: PlayContext) => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  next: () => Promise<void>;
  /**
   * Optimistically advance to queue[queueIndex + 1] without waiting for the
   * server. Used for gapless playback on `ended`: the caller starts the
   * preloaded audio locally, then fires next() to reconcile with the server.
   * No-op if the queue is exhausted. Sets pendingLocalAdvance, which is
   * cleared by the first syncState after the advance — and which tells the
   * subsequent next() call NOT to apply its own optimistic advance (plain
   * button-next, called without a prior advanceLocal, advances itself).
   */
  advanceLocal: () => void;
  prev: () => Promise<void>;
  seek: (positionMs: number) => Promise<void>;
  setMuted: (muted: boolean) => void;
  setVolume: (volume: number) => void;
  toggleShuffle: () => void;
  toggleShuffleSmooth: () => Promise<void>;
  setSortOrder: (field: string, direction: 'asc' | 'desc') => Promise<void>;
  setActiveDevice: (deviceId: string) => Promise<void>;
  syncState: (state: SyncStatePayload) => void;
  syncDevices: (devices: Device[]) => void;
  setPlaybackError: (error: string | null) => void;
  retryPlayback: () => void;
  onTrackPlayed: (trackId: number, playedMs: number) => void;
  renameDevice: (name: string) => void;
  registerDevice: () => void;
  set: (partial: Partial<PlayerState>) => void;
}

export type PlayerStore = PlayerState & PlayerActions;

/** Platform-specific dependencies injected at app init */
export interface PlatformDeps {
  storage: StorageAdapter;
  /** String or thunk for dynamic resolution (e.g. user-configured URL). */
  apiBase: string | (() => string);
  getDeviceName: () => string;
  generateDeviceId: () => string;
}

export function getCurrentPosition(state: PlayerState): number {
  if (!state.isPlaying || !state.trackStartedAt) return state.positionMs;
  return state.positionMs + (Date.now() + state.clockOffset - state.trackStartedAt);
}

/**
 * Optimistic transport actions (pause/resume/seek/next/prev) are only allowed
 * when the audio is LOCAL: this device is active, or nothing is active yet.
 * When remote-controlling another device the UI keeps round-trip behavior —
 * the audio isn't here, so snappy-but-wrong is worse than laggy-but-right.
 */
function canActOptimistically(state: PlayerState): boolean {
  return state.isThisDeviceActive || state.activeDeviceId == null;
}

/** Typed field copy — lets the rollback snapshot loop stay `any`-free. */
function copyField<K extends keyof PlayerState>(
  src: PlayerState,
  dst: Partial<PlayerState>,
  key: K,
): void {
  dst[key] = src[key];
}

type RollbackFn = () => void;

export const createPlayerStore = (deps: PlatformDeps) => {
  const { storage, apiBase, getDeviceName: getDeviceNameFn, generateDeviceId: generateDeviceIdFn } = deps;
  const getApiBase = (): string => (typeof apiBase === 'function' ? apiBase() : apiBase);

  const apiPost = async <T = Record<string, unknown>>(endpoint: string, body?: unknown): Promise<T> => {
    const init: RequestInit = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) init.body = JSON.stringify(body);
    const response = await fetch(`${getApiBase()}${endpoint}`, init);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  };

  const initialVolume = parseFloat(storage.getItem('music-minion-volume') ?? '1.0');

  const initialState: PlayerState = {
    currentTrack: null,
    queue: [],
    queueVersion: 0,
    lastStateSeq: 0,
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
    needsUserGesture: false,
    currentContext: null,
    lastSeekAt: 0,
    pendingLocalAdvance: false,
    lastPrunedTrackId: null,
    lastPrunedAt: null,
  };

  return create<PlayerStore>()((set: (partial: Partial<PlayerStore> | ((state: PlayerStore) => Partial<PlayerStore>)) => void, get: () => PlayerStore) => {
    // ── Queue refetch (slim broadcasts carry no queue array) ──
    // Single-flight: at most one GET /player/queue in the air; a newer version
    // requested mid-flight is coalesced and fetched right after. Out-of-order
    // responses are guarded by version: only pages strictly newer than what
    // the store holds are applied.
    let queueFetchInflight = false;
    let pendingQueueFetch: { version: number; length: number } | null = null;

    const requestQueueRefresh = (version: number, length: number, isRetry = false): void => {
      if (queueFetchInflight) {
        if (!pendingQueueFetch || version > pendingQueueFetch.version) {
          pendingQueueFetch = { version, length };
        }
        return;
      }
      queueFetchInflight = true;
      void (async (): Promise<void> => {
        try {
          const limit = Math.max(1, Math.min(length || 100, 500));
          const page = await fetchPlayerQueue(getApiBase(), 0, limit);
          if (page.version > get().queueVersion) {
            set({ queue: page.tracks, queueVersion: page.version });
          }
        } catch {
          // Keep the stale queue — the slim state fields were already applied
          // so currentTrack/index are correct. queueVersion was NOT advanced,
          // so the next broadcast (still ahead of what we hold) re-triggers
          // this refresh. One short retry covers the no-further-broadcast case.
          if (!isRetry) {
            setTimeout(() => {
              if (version > get().queueVersion) {
                requestQueueRefresh(version, length, true);
              }
            }, 2000);
          }
        } finally {
          queueFetchInflight = false;
          const pending = pendingQueueFetch;
          pendingQueueFetch = null;
          if (pending && pending.version > get().queueVersion) {
            requestQueueRefresh(pending.version, pending.length);
          }
        }
      })();
    };

    // ── Optimistic transport actions ─────────────────────────────────────
    // Each transport action (pause/resume/seek/next/prev) applies its state
    // change locally BEFORE the POST when the audio is local (see
    // canActOptimistically), snapshotting the fields it touched. Broadcast
    // interleaving windows, in arrival order relative to the optimistic apply:
    //
    //  1. Stale broadcast (stateSeq <= lastStateSeq): dropped by syncState's
    //     guard — optimistic state AND the armed rollback both stay intact.
    //  2. Fresh broadcast from ANOTHER mutation that predates our POST landing
    //     on the server: server truth wins unconditionally (syncState applies
    //     it), so the optimistic change may visually regress until our
    //     action's own reconcile broadcast arrives. Applying it bumps
    //     lastStateSeq, which DISARMS the rollback — the state is no longer
    //     ours to restore, and rolling back later would clobber server truth.
    //  3. Our action's own reconcile broadcast: matches the optimistic state
    //     (we mirror the server's math), so echo-suppression absorbs it — no
    //     double-toggle/flicker. It still bumps lastStateSeq first, correctly
    //     disarming the rollback (the server confirmed the action).
    //
    // POST failure: rollback() restores the exact pre-action values of the
    // touched fields IF no broadcast has applied since apply time
    // (lastStateSeq unchanged — note even echo-suppressed broadcasts bump it,
    // which is right: an absorbed echo means the server already agrees).
    // Rollback also bumps lastSeekAt so the audio engines' seek effect
    // re-syncs the element to the restored position.
    //
    // Overlapping optimistic actions compose: each snapshot is taken at its
    // own apply time, so e.g. seek-then-pause with a failed pause rolls back
    // to the post-seek (not pre-seek) position.
    const applyOptimistic = (updates: Partial<PlayerState>): RollbackFn => {
      const before = get();
      const seqAtApply = before.lastStateSeq;
      const snapshot: Partial<PlayerState> = {};
      for (const key of Object.keys(updates) as Array<keyof PlayerState>) {
        copyField(before, snapshot, key);
      }
      set(updates);
      return () => {
        if (get().lastStateSeq !== seqAtApply) return; // server truth landed — don't regress it
        set({ ...snapshot, lastSeekAt: Date.now() });
      };
    };

    /**
     * The optimistic queue-advance update, mirroring the server's
     * advance_queue: position 0, clock rebased, isPlaying PRESERVED (the
     * server does not force play on /next — skipping while paused stays
     * paused). Null when the local queue window has no next track.
     */
    const buildAdvanceUpdates = (state: PlayerState): Partial<PlayerState> | null => {
      const nextTrack = state.queue[state.queueIndex + 1];
      if (!nextTrack) return null;
      return {
        currentTrack: nextTrack,
        queueIndex: state.queueIndex + 1,
        // trackStartedAt is server-clock based; approximate via clockOffset so
        // getCurrentPosition() reads ~0 until the broadcast delivers truth.
        trackStartedAt: Date.now() + state.clockOffset,
        positionMs: 0,
        isPlaying: state.isPlaying,
        scrobbledThisPlaythrough: false,
        pendingLocalAdvance: true,
      };
    };

    return {
    ...initialState,

    play: async (track: Track, context: PlayContext) => {
      const { shuffleEnabled, thisDeviceId, activeDeviceId, availableDevices } = get();
      set({ playbackError: null });

      // A persisted activeDeviceId can outlive its device (backend restart,
      // missed disconnect). Only route to it if it's still connected —
      // otherwise claim playback for this device so audio actually starts.
      const activeIsConnected =
        activeDeviceId != null && availableDevices.some((d) => d.id === activeDeviceId);

      try {
        const response = await fetch(`${getApiBase()}/player/play`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            trackId: track.id,
            context: { ...context, shuffle: context.shuffle ?? shuffleEnabled },
            targetDeviceId: activeIsConnected ? activeDeviceId : thisDeviceId,
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
      const state = get();
      let rollback: RollbackFn | null = null;
      if (canActOptimistically(state) && state.isPlaying) {
        // Mirror the server's pause math: freeze positionMs at the live value
        // (base + elapsed) and stop the clock. The reconcile broadcast carries
        // the same frozen position (± RTT) → echo-suppression absorbs it.
        rollback = applyOptimistic({
          isPlaying: false,
          positionMs: getCurrentPosition(state),
          trackStartedAt: null,
        });
      }
      try {
        const response = await fetch(`${getApiBase()}/player/pause`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to pause');
      } catch (error) {
        rollback?.();
        set({ playbackError: error instanceof Error ? error.message : 'Pause failed' });
      }
    },

    resume: async () => {
      const state = get();
      const { thisDeviceId, activeDeviceId, availableDevices } = state;
      // Same stale-device guard as play(): don't route to a disconnected id.
      const activeIsConnected =
        activeDeviceId != null && availableDevices.some((d) => d.id === activeDeviceId);
      let rollback: RollbackFn | null = null;
      if (canActOptimistically(state) && !state.isPlaying && state.currentTrack) {
        // Mirror the server: keep positionMs, rebase trackStartedAt to "now"
        // (server clock, approximated via clockOffset). When no device is
        // active yet, the server will activate the target we send — reflect
        // that too so the local audio engine actually starts.
        rollback = applyOptimistic({
          isPlaying: true,
          trackStartedAt: Date.now() + state.clockOffset,
          ...(!activeIsConnected
            ? { activeDeviceId: thisDeviceId, isThisDeviceActive: true }
            : {}),
        });
      }
      try {
        const response = await fetch(`${getApiBase()}/player/resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_device_id: activeIsConnected ? activeDeviceId : thisDeviceId,
          }),
        });
        if (!response.ok) throw new Error('Failed to resume');
      } catch (error) {
        rollback?.();
        set({ playbackError: error instanceof Error ? error.message : 'Resume failed' });
      }
    },

    next: async () => {
      const state = get();
      let rollback: RollbackFn | null = null;
      // Optimistic advance — but NOT when pendingLocalAdvance is already set:
      // the web gapless `ended` path calls advanceLocal() (which sets the
      // flag) immediately before next(), so advancing again here would skip
      // two tracks. Plain button-next arrives with the flag clear and gets
      // the optimistic advance; a double-tap's second next() sees the flag
      // from the first and stays server-driven (no local double-skip).
      if (canActOptimistically(state) && !state.pendingLocalAdvance) {
        const updates = buildAdvanceUpdates(state);
        if (updates) rollback = applyOptimistic(updates);
      }
      try {
        const response = await fetch(`${getApiBase()}/player/next`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to skip to next track');
      } catch (error) {
        // POST failed → no reconcile broadcast is coming. Roll back our own
        // optimistic advance (no-op if a broadcast superseded it), and always
        // clear pendingLocalAdvance — leaving it set would suppress every
        // future `ended` advance and stall playback (this also covers the
        // gapless path, whose advance we did NOT apply and don't roll back:
        // its audio is already playing the next track).
        rollback?.();
        set({
          playbackError: error instanceof Error ? error.message : 'Skip failed',
          pendingLocalAdvance: false,
        });
      }
    },

    advanceLocal: () => {
      const updates = buildAdvanceUpdates(get());
      if (updates) set(updates);
    },

    prev: async () => {
      const state = get();
      let rollback: RollbackFn | null = null;
      if (canActOptimistically(state) && state.queue.length > 0) {
        // Mirror the server /prev handler exactly (web/backend/routers/player.py):
        //   - stored position_ms > 3000 → restart the current track at 0.
        //     NOTE: the server compares its stored BASE position (last
        //     seek/pause/resume rebase), NOT the live elapsed position — the
        //     store's positionMs mirrors that same base, so compare it raw.
        //   - else step back one index (floor 0); at index 0 → restart at 0.
        // isPlaying is preserved; trackStartedAt rebased only when playing.
        const restartedAt = state.isPlaying ? Date.now() + state.clockOffset : null;
        if (state.positionMs > 3000 || state.queueIndex === 0) {
          rollback = applyOptimistic({
            positionMs: 0,
            trackStartedAt: restartedAt,
            // Restart is a seek-to-0 from the audio engine's perspective.
            lastSeekAt: Date.now(),
          });
        } else {
          const prevTrack = state.queue[state.queueIndex - 1];
          if (prevTrack) {
            rollback = applyOptimistic({
              currentTrack: prevTrack,
              queueIndex: state.queueIndex - 1,
              positionMs: 0,
              trackStartedAt: restartedAt,
              scrobbledThisPlaythrough: false,
            });
          }
        }
      }
      try {
        const response = await fetch(`${getApiBase()}/player/prev`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to go to previous track');
      } catch (error) {
        rollback?.();
        set({ playbackError: error instanceof Error ? error.message : 'Previous failed' });
      }
    },

    seek: async (positionMs: number) => {
      const state = get();
      const target = Math.round(positionMs);
      let rollback: RollbackFn | null = null;
      if (canActOptimistically(state) && state.currentTrack) {
        // Mirror the server: positionMs = target, trackStartedAt rebased to
        // "now" when playing (null when paused). getCurrentPosition() reads
        // the target immediately — no snap-back while the POST is in flight —
        // and lastSeekAt makes the audio engines apply the seek right away.
        rollback = applyOptimistic({
          positionMs: target,
          trackStartedAt: state.isPlaying ? Date.now() + state.clockOffset : null,
          lastSeekAt: Date.now(),
        });
      }
      try {
        const response = await fetch(`${getApiBase()}/player/seek`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ positionMs: target }),
        });
        if (!response.ok) throw new Error('Failed to seek');
        // Remote-control path (non-optimistic): keep the original round-trip
        // behavior — bump lastSeekAt only after the server accepted the seek.
        if (!rollback) set({ lastSeekAt: Date.now() });
      } catch (error) {
        rollback?.();
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
        fetch(`${getApiBase()}/player/play`, {
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
        await fetch(`${getApiBase()}/player/transfer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_id: deviceId }),
        });
      } catch {
        // Transfer errors are non-critical
      }
    },

    syncState: (state: SyncStatePayload) => {
      const current = get();
      // Fat payloads (sync:full on connect, GET /state) carry the queue;
      // slim playback:state broadcasts omit it.
      const fullQueue = state.queue;
      const isSlim = fullQueue === undefined;

      // Sequencing: drop slim broadcasts that arrive out of order — a late,
      // older snapshot must never regress newer state. Fat payloads always
      // apply and re-baseline the guard (the server may have restarted and
      // reset its counters).
      if (isSlim && state.stateSeq != null && state.stateSeq <= current.lastStateSeq) {
        return;
      }
      // Version regression on a slim broadcast = stale message; drop it too.
      if (isSlim && state.queueVersion != null && state.queueVersion < current.queueVersion) {
        return;
      }
      // Bump lastStateSeq even when echo-suppression skips the body below:
      // armed optimistic rollbacks compare against this to detect "a broadcast
      // applied since I snapshotted" — an absorbed echo counts (the server
      // already agrees with the optimistic state, so rolling back would lie).
      if (state.stateSeq != null) {
        set({ lastStateSeq: state.stateSeq });
      }

      // First broadcast after a local advance ends the pending window, even
      // when echo-suppression skips the rest of the sync below.
      if (current.pendingLocalAdvance) {
        set({ pendingLocalAdvance: false });
      }

      // Server pruned a dead track from the queue (broadcast-only hint).
      // Record it BEFORE echo-suppression so pending error-skip timers can
      // cancel themselves at fire time instead of double-advancing.
      if (state.pruned_track_id != null) {
        set({ lastPrunedTrackId: state.pruned_track_id, lastPrunedAt: Date.now() });
      }

      // Queue-content comparison by version (NOT length — a same-length
      // change like one-pruned-one-refilled must not be suppressed).
      // Legacy fat payloads without a version fall back to length compare.
      const queueInSync = state.queueVersion != null
        ? state.queueVersion === current.queueVersion
        : isSlim || fullQueue.length === current.queue.length;

      // Skip if state is already in sync (prevents WebSocket echo causing stutter)
      if (
        current.currentTrack?.id === state.currentTrack?.id &&
        current.isPlaying === state.isPlaying &&
        current.activeDeviceId === state.activeDeviceId &&
        Math.abs((current.positionMs ?? 0) - (state.positionMs ?? 0)) < 2000 &&
        current.queueIndex === state.queueIndex &&
        queueInSync
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

      // Detect remote seek: same track but position jumped >3s
      const isRemoteSeek = prevTrackId === newTrackId &&
        Math.abs((current.positionMs ?? 0) - (state.positionMs ?? 0)) > 3000;

      set({
        currentTrack,
        // Fat payload: take the queue wholesale. Slim payload: keep the
        // existing array identity (memoized queue rows don't re-render).
        ...(fullQueue !== undefined
          ? { queue: fullQueue, queueVersion: state.queueVersion ?? 0 }
          : {}),
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
        lastSeekAt: isRemoteSeek ? Date.now() : current.lastSeekAt,
      });

      // Slim broadcast advertising newer queue content than we hold: the slim
      // fields above are already applied (currentTrack/index update now); the
      // queue list itself lags one fetch behind.
      if (isSlim && state.queueVersion != null && state.queueVersion > current.queueVersion) {
        requestQueueRefresh(state.queueVersion, state.queueLength ?? current.queue.length);
      }
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
      const { currentTrack, currentContext } = get();
      if (currentTrack) {
        set({ playbackError: null });
        // Preserve the play context so the queue survives the retry; a bare
        // track context would collapse the queue to this single track.
        get().play(currentTrack, currentContext ?? { type: 'track' });
      }
    },

    onTrackPlayed: async (trackId: number, playedMs: number) => {
      set({ scrobbledThisPlaythrough: true });
      try {
        await fetch(`${getApiBase()}/tracks/${trackId}/scrobble`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ played_ms: Math.round(playedMs) }),
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
    };
  });
};
