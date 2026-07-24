import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createPlayerStore, getCurrentPosition } from '../stores/createPlayerStore.js';
import { createMemoryStorageAdapter } from '../stores/storage.js';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

const makeDeps = () => ({
  storage: createMemoryStorageAdapter(),
  apiBase: 'http://test:8642/api',
  getDeviceName: () => 'Test Device',
  generateDeviceId: () => 'test-device-123',
});

describe('createPlayerStore', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('creates a store with initial state', () => {
    const store = createPlayerStore(makeDeps());
    const state = store.getState();

    expect(state.currentTrack).toBeNull();
    expect(state.isPlaying).toBe(false);
    expect(state.thisDeviceId).toBe('test-device-123');
    expect(state.thisDeviceName).toBe('Test Device');
    expect(state.queue).toEqual([]);
  });

  it('reads initial volume from storage', () => {
    const deps = makeDeps();
    deps.storage.setItem('music-minion-volume', '0.75');
    const store = createPlayerStore(deps);
    expect(store.getState().volume).toBe(0.75);
  });

  it('reads initial shuffle from storage', () => {
    const deps = makeDeps();
    deps.storage.setItem('music-minion-shuffle', 'false');
    const store = createPlayerStore(deps);
    expect(store.getState().shuffleEnabled).toBe(false);
  });

  it('persists volume changes to storage', () => {
    const deps = makeDeps();
    const store = createPlayerStore(deps);
    store.getState().setVolume(0.5);
    expect(deps.storage.getItem('music-minion-volume')).toBe('0.5');
    expect(store.getState().volume).toBe(0.5);
  });

  it('persists mute state to storage', () => {
    const deps = makeDeps();
    const store = createPlayerStore(deps);
    store.getState().setMuted(true);
    expect(deps.storage.getItem('music-minion-player-muted')).toBe('true');
    expect(store.getState().isMuted).toBe(true);
  });

  it('renames device and persists to storage', () => {
    const deps = makeDeps();
    const store = createPlayerStore(deps);
    store.getState().renameDevice('My Phone');
    expect(store.getState().thisDeviceName).toBe('My Phone');
    expect(deps.storage.getItem('music-minion-device-name')).toBe('My Phone');
  });
});

describe('syncState', () => {
  it('passes through queue-only updates', () => {
    const store = createPlayerStore(makeDeps());
    const track = { id: 1, title: 'Song', artist: 'Artist' };
    const queue = [track, { id: 2, title: 'Song 2', artist: 'Artist' }];

    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 1000,
      trackStartedAt: Date.now() - 1000,
      queue,
      queueIndex: 0,
      serverTime: Date.now(),
    } as any);

    expect(store.getState().queueIndex).toBe(0);

    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 1000,
      trackStartedAt: Date.now() - 1000,
      queue,
      queueIndex: 1,
      serverTime: Date.now(),
    } as any);

    expect(store.getState().queueIndex).toBe(1);
  });
});

describe('syncState prune hint', () => {
  it('records pruned_track_id + timestamp from a prune broadcast', () => {
    const store = createPlayerStore(makeDeps());
    const before = Date.now();

    store.getState().syncState({
      currentTrack: { id: 2, title: 'Next Song', artist: 'Artist' },
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: Date.now(),
      queue: [{ id: 2, title: 'Next Song', artist: 'Artist' }],
      queueIndex: 0,
      serverTime: Date.now(),
      pruned_track_id: 42,
    } as any);

    expect(store.getState().lastPrunedTrackId).toBe(42);
    expect(store.getState().lastPrunedAt).toBeGreaterThanOrEqual(before);
  });

  it('leaves the prune hint untouched on broadcasts without one', () => {
    const store = createPlayerStore(makeDeps());

    store.getState().syncState({
      currentTrack: { id: 1, title: 'Song', artist: 'Artist' },
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: Date.now(),
      queue: [{ id: 1, title: 'Song', artist: 'Artist' }],
      queueIndex: 0,
      serverTime: Date.now(),
    } as any);

    expect(store.getState().lastPrunedTrackId).toBeNull();
    expect(store.getState().lastPrunedAt).toBeNull();
  });
});

describe('syncState queue delta sync (slim broadcasts)', () => {
  const track = (id: number) => ({ id, title: `Track ${id}`, artist: 'Artist' });

  /** Fat payload — what sync:full delivers on WS connect. */
  const fatPayload = (queue: any[], version: number, seq: number, extra: Record<string, unknown> = {}) => ({
    currentTrack: queue[0] ?? null,
    isPlaying: true,
    activeDeviceId: 'test-device-123',
    positionMs: 0,
    trackStartedAt: Date.now(),
    queue,
    queueIndex: 0,
    queueVersion: version,
    queueLength: queue.length,
    stateSeq: seq,
    serverTime: Date.now(),
    ...extra,
  });

  /** Slim payload — what playback:state broadcasts deliver (no queue array). */
  const slimPayload = (version: number, seq: number, extra: Record<string, unknown> = {}) => ({
    currentTrack: track(1),
    isPlaying: true,
    activeDeviceId: 'test-device-123',
    positionMs: 0,
    trackStartedAt: Date.now(),
    queueIndex: 0,
    queueVersion: version,
    queueLength: 2,
    stateSeq: seq,
    serverTime: Date.now(),
    ...extra,
  });

  const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

  it('fat payload applies queue and records queueVersion', () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1), track(2)], 3, 1) as any);

    expect(store.getState().queue.map((t) => t.id)).toEqual([1, 2]);
    expect(store.getState().queueVersion).toBe(3);
    expect(store.getState().lastStateSeq).toBe(1);
  });

  it('slim broadcast with SAME queueVersion preserves queue array identity', () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1), track(2)], 3, 1) as any);
    const queueBefore = store.getState().queue;

    store.getState().syncState(slimPayload(3, 2, { queueIndex: 1, currentTrack: track(2) }) as any);

    expect(store.getState().queueIndex).toBe(1);
    expect(store.getState().queue).toBe(queueBefore); // identity preserved
    expect(mockFetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/player/queue'),
    );
  });

  it('slim broadcast with NEWER queueVersion applies slim fields immediately and fetches the queue', async () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1), track(2)], 3, 1) as any);

    const newQueue = [track(1), track(3)];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ version: 4, total: 2, offset: 0, tracks: newQueue }),
    });

    store.getState().syncState(slimPayload(4, 2, { isPlaying: false }) as any);

    // Slim fields applied immediately, before the fetch resolves
    expect(store.getState().isPlaying).toBe(false);

    await flush();
    expect(mockFetch).toHaveBeenCalledWith(
      'http://test:8642/api/player/queue?offset=0&limit=2',
    );
    expect(store.getState().queue.map((t) => t.id)).toEqual([1, 3]);
    expect(store.getState().queueVersion).toBe(4);
  });

  it('drops a stale slim broadcast (stateSeq <= last applied)', () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1), track(2)], 3, 5) as any);
    store.getState().syncState(slimPayload(3, 6, { queueIndex: 1, currentTrack: track(2) }) as any);

    // Late broadcast from before the advance (seq 4 < 6) must not regress
    store.getState().syncState(slimPayload(3, 4, { queueIndex: 0, currentTrack: track(1) }) as any);

    expect(store.getState().queueIndex).toBe(1);
    expect(store.getState().currentTrack?.id).toBe(2);
    expect(store.getState().lastStateSeq).toBe(6);
  });

  it('drops a slim broadcast whose queueVersion regressed', () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1), track(2)], 3, 5) as any);

    store.getState().syncState(slimPayload(2, 6, { queueIndex: 1 }) as any);

    expect(store.getState().queueIndex).toBe(0);
    expect(store.getState().queueVersion).toBe(3);
  });

  it('keeps the stale queue when the version-gap fetch fails; next broadcast re-triggers', async () => {
    vi.useFakeTimers();
    try {
      const store = createPlayerStore(makeDeps());
      store.getState().syncState(fatPayload([track(1), track(2)], 3, 1) as any);
      const queueBefore = store.getState().queue;

      mockFetch.mockRejectedValueOnce(new Error('network down'));
      store.getState().syncState(slimPayload(4, 2, { isPlaying: false }) as any);
      await vi.advanceTimersByTimeAsync(0);

      // Fetch failed: queue + version unchanged, slim fields still applied
      expect(store.getState().queue).toBe(queueBefore);
      expect(store.getState().queueVersion).toBe(3);
      expect(store.getState().isPlaying).toBe(false);

      // Next broadcast (version still ahead of stored 3) re-triggers the fetch
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ version: 4, total: 1, offset: 0, tracks: [track(3)] }),
      });
      store.getState().syncState(slimPayload(4, 3, { positionMs: 5000 }) as any);
      await vi.advanceTimersByTimeAsync(0);

      expect(store.getState().queue.map((t) => t.id)).toEqual([3]);
      expect(store.getState().queueVersion).toBe(4);
    } finally {
      vi.useRealTimers();
    }
  });

  it('ignores an out-of-date fetch response (version already surpassed)', async () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1)], 3, 1) as any);

    // Slow fetch for v4 kicks off...
    let resolveFetch: (value: unknown) => void = () => {};
    mockFetch.mockReturnValueOnce(new Promise((resolve) => { resolveFetch = resolve; }));
    store.getState().syncState(slimPayload(4, 2) as any);

    // ...meanwhile a fat sync:full (reconnect) lands with v6
    store.getState().syncState(fatPayload([track(9)], 6, 3) as any);
    const queueAfterFat = store.getState().queue;

    // The v4 response finally arrives — must NOT clobber the v6 queue
    resolveFetch({
      ok: true,
      json: async () => ({ version: 4, total: 1, offset: 0, tracks: [track(2)] }),
    });
    await flush();

    expect(store.getState().queue).toBe(queueAfterFat);
    expect(store.getState().queueVersion).toBe(6);
  });

  it('clears pendingLocalAdvance on a slim reconcile broadcast', () => {
    const store = createPlayerStore(makeDeps());
    store.getState().syncState(fatPayload([track(1), track(2)], 3, 1) as any);

    store.getState().advanceLocal();
    expect(store.getState().pendingLocalAdvance).toBe(true);

    // Server reconcile: slim broadcast echoing the advance (same version)
    store.getState().syncState(slimPayload(3, 2, { queueIndex: 1, currentTrack: track(2) }) as any);
    expect(store.getState().pendingLocalAdvance).toBe(false);
    expect(store.getState().queueIndex).toBe(1);
  });
});

describe('optimistic transport actions', () => {
  const track = (id: number) => ({ id, title: `Track ${id}`, artist: 'Artist' });

  /** Seed a store playing queue[index] on THIS device via a fat sync payload. */
  const seedStore = (
    overrides: Record<string, unknown> = {},
  ) => {
    const store = createPlayerStore(makeDeps());
    const queue = [track(1), track(2), track(3)];
    store.getState().syncState({
      currentTrack: queue[0],
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: Date.now() - 10_000,
      queue,
      queueIndex: 0,
      queueVersion: 1,
      queueLength: queue.length,
      stateSeq: 1,
      serverTime: Date.now(),
      ...overrides,
    } as any);
    return store;
  };

  /** A fetch that never resolves — freezes the store mid-POST. */
  const pendingFetch = () => mockFetch.mockReturnValue(new Promise(() => {}));

  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('pause applies optimistically before the POST resolves (position frozen, clock stopped)', () => {
    const store = seedStore();
    pendingFetch();

    void store.getState().pause();

    const s = store.getState();
    expect(s.isPlaying).toBe(false);
    expect(s.trackStartedAt).toBeNull();
    // Frozen at the live position (~10s elapsed since trackStartedAt)
    expect(s.positionMs).toBeGreaterThanOrEqual(9_500);
    expect(s.positionMs).toBeLessThanOrEqual(10_500);
    expect(getCurrentPosition(s)).toBe(s.positionMs);
  });

  it('pause rolls back on POST failure', async () => {
    const store = seedStore();
    const startedAtBefore = store.getState().trackStartedAt;
    mockFetch.mockRejectedValueOnce(new Error('network down'));

    await store.getState().pause();

    const s = store.getState();
    expect(s.isPlaying).toBe(true);
    expect(s.trackStartedAt).toBe(startedAtBefore);
    expect(s.positionMs).toBe(0); // base position restored
    expect(s.playbackError).toBe('network down');
    expect(s.lastSeekAt).toBeGreaterThan(0); // engines re-sync to restored position
  });

  it('pause rollback is disarmed when a broadcast applied in between', async () => {
    const store = seedStore();
    let rejectPost: (err: Error) => void = () => {};
    mockFetch.mockReturnValueOnce(new Promise((_, reject) => { rejectPost = reject; }));

    const pausePromise = store.getState().pause();
    expect(store.getState().isPlaying).toBe(false);

    // Server broadcast lands before the POST settles (here: the reconcile
    // echo confirming the pause — bumps lastStateSeq even when absorbed).
    store.getState().syncState({
      currentTrack: track(1),
      isPlaying: false,
      activeDeviceId: 'test-device-123',
      positionMs: store.getState().positionMs,
      trackStartedAt: null,
      queueIndex: 0,
      queueVersion: 1,
      queueLength: 3,
      stateSeq: 2,
      serverTime: Date.now(),
    } as any);

    rejectPost(new Error('late failure'));
    await pausePromise;

    // Server truth (paused) must NOT be rolled back
    expect(store.getState().isPlaying).toBe(false);
    expect(store.getState().playbackError).toBe('late failure');
  });

  it('resume applies optimistically (clock rebased, position kept)', () => {
    const store = seedStore({ isPlaying: false, trackStartedAt: null, positionMs: 42_000 });
    pendingFetch();
    const before = Date.now();

    void store.getState().resume();

    const s = store.getState();
    expect(s.isPlaying).toBe(true);
    expect(s.positionMs).toBe(42_000);
    expect(s.trackStartedAt).toBeGreaterThanOrEqual(before - 50); // clockOffset ~0 in tests
    const pos = getCurrentPosition(s);
    expect(pos).toBeGreaterThanOrEqual(42_000);
    expect(pos).toBeLessThan(43_000);
  });

  it('resume rolls back on POST failure', async () => {
    const store = seedStore({ isPlaying: false, trackStartedAt: null, positionMs: 42_000 });
    mockFetch.mockRejectedValueOnce(new Error('boom'));

    await store.getState().resume();

    const s = store.getState();
    expect(s.isPlaying).toBe(false);
    expect(s.trackStartedAt).toBeNull();
    expect(s.positionMs).toBe(42_000);
    expect(s.playbackError).toBe('boom');
  });

  it('seek applies target position + lastSeekAt immediately; no snap-back', () => {
    const store = seedStore();
    pendingFetch();

    void store.getState().seek(90_000);

    const s = store.getState();
    expect(s.positionMs).toBe(90_000);
    expect(s.lastSeekAt).toBeGreaterThan(0);
    const pos = getCurrentPosition(s);
    expect(pos).toBeGreaterThanOrEqual(90_000);
    expect(pos).toBeLessThan(91_000);
  });

  it('seek rolls back position and clock on POST failure', async () => {
    const store = seedStore();
    const startedAtBefore = store.getState().trackStartedAt;
    mockFetch.mockRejectedValueOnce(new Error('seek down'));

    await store.getState().seek(90_000);

    const s = store.getState();
    expect(s.positionMs).toBe(0);
    expect(s.trackStartedAt).toBe(startedAtBefore);
    expect(s.playbackError).toBe('seek down');
    expect(s.lastSeekAt).toBeGreaterThan(0); // engines snap audio back
  });

  it('plain next() advances optimistically via the advanceLocal updates', () => {
    const store = seedStore();
    pendingFetch();

    void store.getState().next();

    const s = store.getState();
    expect(s.queueIndex).toBe(1);
    expect(s.currentTrack?.id).toBe(2);
    expect(s.positionMs).toBe(0);
    expect(s.pendingLocalAdvance).toBe(true);
    expect(s.isPlaying).toBe(true); // preserved, not forced
    expect(mockFetch).toHaveBeenCalledWith(
      'http://test:8642/api/player/next',
      { method: 'POST' },
    );
  });

  it('next() after advanceLocal() does NOT double-advance (gapless path)', () => {
    const store = seedStore();
    pendingFetch();

    store.getState().advanceLocal();
    expect(store.getState().queueIndex).toBe(1);

    void store.getState().next();

    expect(store.getState().queueIndex).toBe(1); // still 1, not 2
    expect(store.getState().currentTrack?.id).toBe(2);
  });

  it('next() preserves paused state on optimistic advance (server does not force play)', () => {
    const store = seedStore({ isPlaying: false, trackStartedAt: null });
    pendingFetch();

    void store.getState().next();

    expect(store.getState().queueIndex).toBe(1);
    expect(store.getState().isPlaying).toBe(false);
  });

  it('next() rolls back the advance and clears pendingLocalAdvance on POST failure', async () => {
    const store = seedStore();
    mockFetch.mockRejectedValueOnce(new Error('skip down'));

    await store.getState().next();

    const s = store.getState();
    expect(s.queueIndex).toBe(0);
    expect(s.currentTrack?.id).toBe(1);
    expect(s.pendingLocalAdvance).toBe(false);
    expect(s.playbackError).toBe('skip down');
  });

  it('prev() with base position <= 3s steps back a track optimistically', () => {
    const store = seedStore({ queueIndex: 1, currentTrack: track(2), positionMs: 0 });
    pendingFetch();

    void store.getState().prev();

    const s = store.getState();
    expect(s.queueIndex).toBe(0);
    expect(s.currentTrack?.id).toBe(1);
    expect(s.positionMs).toBe(0);
  });

  it('prev() with stored base position > 3s restarts the current track (server semantics)', () => {
    const store = seedStore({ queueIndex: 1, currentTrack: track(2), positionMs: 20_000 });
    pendingFetch();

    void store.getState().prev();

    const s = store.getState();
    expect(s.queueIndex).toBe(1); // same track
    expect(s.currentTrack?.id).toBe(2);
    expect(s.positionMs).toBe(0); // restarted
    expect(s.lastSeekAt).toBeGreaterThan(0); // engines seek to 0
  });

  it('prev() at queue start restarts instead of stepping back', () => {
    const store = seedStore({ queueIndex: 0, positionMs: 0 });
    pendingFetch();

    void store.getState().prev();

    expect(store.getState().queueIndex).toBe(0);
    expect(store.getState().currentTrack?.id).toBe(1);
    expect(store.getState().positionMs).toBe(0);
  });

  it('prev() rolls back the step-back on POST failure', async () => {
    const store = seedStore({ queueIndex: 1, currentTrack: track(2), positionMs: 0 });
    mockFetch.mockRejectedValueOnce(new Error('prev down'));

    await store.getState().prev();

    expect(store.getState().queueIndex).toBe(1);
    expect(store.getState().currentTrack?.id).toBe(2);
    expect(store.getState().playbackError).toBe('prev down');
  });

  describe('remote-device guard (another device is active)', () => {
    const remoteSeed = (overrides: Record<string, unknown> = {}) =>
      seedStore({ activeDeviceId: 'other-device', ...overrides });

    it('pause stays non-optimistic', () => {
      const store = remoteSeed();
      pendingFetch();
      void store.getState().pause();
      expect(store.getState().isPlaying).toBe(true); // unchanged until broadcast
    });

    it('resume stays non-optimistic', () => {
      const store = remoteSeed({ isPlaying: false, trackStartedAt: null });
      pendingFetch();
      void store.getState().resume();
      expect(store.getState().isPlaying).toBe(false);
    });

    it('seek stays non-optimistic until the server accepts (round-trip lastSeekAt)', async () => {
      const store = remoteSeed();
      mockFetch.mockResolvedValueOnce({ ok: true });

      const seekPromise = store.getState().seek(90_000);
      expect(store.getState().positionMs).toBe(0); // not applied optimistically
      expect(store.getState().lastSeekAt).toBe(0);

      await seekPromise;
      expect(store.getState().positionMs).toBe(0); // still server-owned
      expect(store.getState().lastSeekAt).toBeGreaterThan(0); // original behavior kept
    });

    it('next/prev stay non-optimistic', () => {
      const store = remoteSeed({ queueIndex: 1, currentTrack: track(2) });
      pendingFetch();
      void store.getState().next();
      expect(store.getState().queueIndex).toBe(1);
      void store.getState().prev();
      expect(store.getState().queueIndex).toBe(1);
    });
  });

  it('resume with NO active device claims this device optimistically', () => {
    const store = seedStore({ isPlaying: false, trackStartedAt: null, activeDeviceId: null });
    pendingFetch();

    void store.getState().resume();

    const s = store.getState();
    expect(s.isPlaying).toBe(true);
    expect(s.activeDeviceId).toBe('test-device-123');
    expect(s.isThisDeviceActive).toBe(true);
  });
});

describe('getCurrentPosition', () => {
  it('returns positionMs when not playing', () => {
    const state = {
      isPlaying: false,
      trackStartedAt: null,
      positionMs: 5000,
      clockOffset: 0,
    } as any;
    expect(getCurrentPosition(state)).toBe(5000);
  });

  it('computes position from clock when playing', () => {
    const now = Date.now();
    const state = {
      isPlaying: true,
      trackStartedAt: now - 2000,
      positionMs: 1000,
      clockOffset: 0,
    } as any;
    const pos = getCurrentPosition(state);
    // Should be approximately 3000 (1000 + 2000 elapsed)
    expect(pos).toBeGreaterThanOrEqual(2900);
    expect(pos).toBeLessThanOrEqual(3100);
  });
});

describe('syncState clock offset (seconds vs milliseconds regression)', () => {
  it('preserves correct position after queue-change re-sync', () => {
    const store = createPlayerStore(makeDeps());
    const track = { id: 1, title: 'Song', artist: 'Artist' };
    const now = Date.now();

    // Initial sync — simulates backend sending ms timestamps (post-fix)
    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: now - 30_000,
      queue: [track, { id: 2, title: 'Song 2', artist: 'Artist' }],
      queueIndex: 0,
      serverTime: now,
      shuffleEnabled: true,
    } as any);

    const posAfterInitial = getCurrentPosition(store.getState());
    expect(posAfterInitial).toBeGreaterThanOrEqual(29_000);
    expect(posAfterInitial).toBeLessThanOrEqual(31_000);

    // Re-sync with changed queue (bucket assignment removes a track)
    // serverTime advances slightly, trackStartedAt unchanged — both in ms
    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: now - 30_000,
      queue: [track],
      queueIndex: 0,
      serverTime: now + 50,
      shuffleEnabled: true,
    } as any);

    const posAfterResync = getCurrentPosition(store.getState());
    // Position must stay ~30s, not drop to ~30ms
    expect(posAfterResync).toBeGreaterThanOrEqual(29_000);
    expect(posAfterResync).toBeLessThanOrEqual(31_500);
  });

  it('would produce wrong position if timestamps were in seconds', () => {
    const store = createPlayerStore(makeDeps());
    const track = { id: 1, title: 'Song', artist: 'Artist' };
    const nowSeconds = Date.now() / 1000;

    // Simulate pre-fix backend: seconds instead of ms
    store.getState().syncState({
      currentTrack: track,
      isPlaying: true,
      activeDeviceId: 'test-device-123',
      positionMs: 0,
      trackStartedAt: nowSeconds - 30,
      queue: [track],
      queueIndex: 0,
      serverTime: nowSeconds,
      shuffleEnabled: true,
    } as any);

    const pos = getCurrentPosition(store.getState());
    // With seconds, position would be ~30ms not ~30000ms — clearly broken
    expect(pos).toBeLessThan(1000);
  });
});
